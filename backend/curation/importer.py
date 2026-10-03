"""经审核资料的离线事务导入；预览整个事务后回滚，不发布任何对象。"""
from collections import Counter
from datetime import date, datetime

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from competition_catalog.models import CatalogEntry, CatalogBinding
from competitions.models import Competition, CompetitionSource
from competitions.services import save_competition, save_source
from resources.models import Resource, ResourceCompetition, ResourceRevision
from .models import KnowledgeDocument, DocumentRevision, DocumentLink, ImportedObject, ImportedObjectRevision, ImportRun
from .package import COMPETITION_FIELDS, RESOURCE_FIELDS, PackageError, digest, require


def checked_save(obj):
    obj.full_clean()
    obj.save()
    return obj


def entity_state(kind, obj):
    if kind == 'competition':
        return {
            'fields': {name: getattr(obj, name) for name in COMPETITION_FIELDS},
            'category': obj.category_id, 'status': obj.publication_status,
            'recruitment': [obj.recruitment_enabled, obj.recruitment_deadline, obj.recruitment_note],
            'tags': sorted(obj.tags.values_list('pk', flat=True)),
            'sources': list(obj.sources.order_by('source_url').values(
                'source_type', 'source_name', 'source_url', 'is_primary', 'source_published_on')),
            'catalogs': sorted(obj.catalog_bindings.values_list('entry__code', flat=True)),
        }
    if kind == 'resource':
        return {'fields': {name: getattr(obj, name) for name in RESOURCE_FIELDS},
                'status': obj.publication_status, 'category': obj.category_id,
                'tags': sorted(obj.tags.values_list('pk', flat=True)),
                'directions': sorted(obj.directions.values_list('pk', flat=True)),
                'version': obj.content_version,
                'competitions': sorted(obj.competitions.values_list('code', flat=True))}
    return {'title': obj.title, 'review_status': obj.review_status,
            'revision': obj.current_revision_id}


def decision(kind, model, row, package_id, counts):
    obj = model.objects.select_for_update().filter(code=row['code']).first()
    stamp = ImportedObject.objects.select_for_update().filter(kind=kind, code=row['code']).first()
    if obj:
        require(stamp is not None and stamp.package_id == package_id, f'{kind}/{row["code"]} 已存在但不属于本资料包。')
        require(stamp.state_hash == digest(entity_state(kind, obj)), f'{kind}/{row["code"]} 已被人工修改，拒绝覆盖。')
        if stamp.payload_hash == digest(row):
            counts[f'{kind}_unchanged'] += 1
            return obj, False
        status = obj.review_status if kind == 'document' else obj.publication_status
        require(status == 'draft', f'{kind}/{row["code"]} 已审核或已发布，需另行审核更新。')
    counts[f'{kind}_{"updated" if obj else "created"}'] += 1
    return obj, True


def stamp_object(kind, obj, row, package_id, actor):
    # Record database-normalized values: PostgreSQL returns aware datetimes in UTC,
    # which may differ in representation from the source offset after save().
    obj.refresh_from_db()
    state = entity_state(kind, obj)
    stamp, _ = ImportedObject.objects.update_or_create(kind=kind, code=row['code'], defaults={
        'package_id': package_id, 'payload_hash': digest(row), 'state_hash': digest(state),
    })
    version = (stamp.revisions.aggregate(value=Max('version'))['value'] or 0) + 1
    checked_save(ImportedObjectRevision(imported_object=stamp, version=version,
        payload=row, state=state, created_by=actor))


def require_actor(actor):
    permissions = [
        'curation.add_importrun', 'curation.add_knowledgedocument',
        'competitions.add_competition', 'competitions.change_competition',
        'competitions.add_competitionsource', 'resources.add_resource', 'resources.change_resource',
    ]
    if not actor or not actor.is_active or not actor.is_staff or not actor.has_perms(permissions):
        raise PermissionDenied('需要有效管理员及人工资料导入、赛事、来源和资源维护权限。')


def link_references(data, actor, catalogs, counts):
    """Only append catalog bindings; the original package continues to own each object."""
    for kind, model in [('competitions', Competition), ('resources', Resource)]:
        entity_kind = 'competition' if kind == 'competitions' else 'resource'
        for row in data.get('references', {}).get(kind, []):
            obj = model.objects.select_for_update().filter(code=row['code']).first()
            stamp = ImportedObject.objects.select_for_update().filter(kind=entity_kind, code=row['code']).first()
            require(obj is not None and stamp is not None, f'复用对象缺失：{row["code"]}；请先导入依赖包。')
            require(stamp.package_id == row['package_id'] and stamp.payload_hash == row['payload_hash'],
                    f'复用对象来源或版本不一致：{row["code"]}')
            require(stamp.state_hash == digest(entity_state(entity_kind, obj)), f'复用对象已被人工修改：{row["code"]}')
            if kind == 'competitions':
                missing = [catalogs[c] for c in row['catalog_codes'] if c in catalogs
                           and not obj.catalog_bindings.filter(entry=catalogs[c]).exists()]
                if missing:
                    require(obj.publication_status == 'draft', f'复用赛事已发布，不能增补目录：{row["code"]}')
                    previous = stamp.revisions.order_by('-version').first()
                    require(previous is not None and digest(previous.payload) == stamp.payload_hash,
                            f'复用赛事缺少原始载荷版本：{row["code"]}')
                    for entry in missing:
                        CatalogBinding.objects.create(entry=entry, competition=obj, basis='人工资料包复用同一赛事届次；保留原包所有目录关联。')
                    stamp_object(entity_kind, obj, previous.payload, stamp.package_id, actor)
                    counts['referenced_catalog_links_created'] += len(missing)
            counts[f'{entity_kind}_referenced'] += 1


@transaction.atomic
def import_package(data, *, actor, apply=False):
    require_actor(actor)
    require(not apply or data.get('review', {}).get('status') == 'approved', '资料包尚未审核；只能预览。')
    if apply:
        require(data['review'].get('reviewed_by') and data['review'].get('reviewed_on'), '缺少审核人或审核日期。')
    # 所有本命令的写入串行化；行锁和唯一约束仍保护实际对象。
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [2026131255])
    counts = Counter()
    package_id = data['package_id']
    catalogs = {}
    for row in data['catalog']:
        obj = CatalogEntry.objects.select_for_update().filter(code=row['code']).first()
        if obj:
            require(obj.name == row['name'] and obj.version == 2026, f'目录身份不一致：{row["code"]}')
        else:
            obj = checked_save(CatalogEntry(**{k: row[k] for k in ('code', 'name', 'grade', 'levels', 'departments', 'source_url')}, version=2026))
            counts['catalog_created'] += 1
        catalogs[row['code']] = obj
    link_references(data, actor, catalogs, counts)
    for row in data['competitions']:
        obj, changed = decision('competition', Competition, row, package_id, counts)
        if changed:
            obj = obj or Competition(code=row['code'])
            for key in COMPETITION_FIELDS:
                value = row['fields'].get(key, obj._meta.get_field(key).get_default())
                if key.endswith('_deadline') and value:
                    value = date.fromisoformat(value)
                elif key.endswith('_deadline_at') and value:
                    value = datetime.fromisoformat(value)
                setattr(obj, key, value)
            obj = save_competition(obj, actor=actor)
            # 只更新本导入拥有的草稿；完整来源列表替换前的变更已通过指纹检查。
            obj.sources.all().delete()
            for source in row['sources']:
                values = dict(source)
                if values.get('source_published_on'):
                    values['source_published_on'] = date.fromisoformat(values['source_published_on'])
                save_source(CompetitionSource(competition=obj, **values), actor=actor, verified=False)
        linked = False
        for entry in CatalogEntry.objects.filter(code__in=row['catalog_codes']):
            if not obj.catalog_bindings.filter(entry=entry).exists():
                require(obj.publication_status == 'draft', f'{row["code"]} 已发布，不能增补目录关联。')
                CatalogBinding.objects.create(entry=entry, competition=obj,
                    basis='人工资料包关联；身份待审核项不得生成赛事记录。见对应资料档案。')
                linked = True
        if changed or linked:
            obj.catalog_bindings.exclude(entry__code__in=row['catalog_codes']).delete()
            stamp_object('competition', obj, row, package_id, actor)
    for row in data['resources']:
        obj, changed = decision('resource', Resource, row, package_id, counts)
        if changed:
            creating = obj is None
            obj = obj or Resource(code=row['code'], created_by=actor)
            for key in RESOURCE_FIELDS:
                value = row['fields'].get(key, obj._meta.get_field(key).get_default())
                setattr(obj, key, value)
            obj.updated_by = actor
            if not creating:
                obj.content_version += 1
            obj.last_edited_at = timezone.now()
            checked_save(obj)
        # 跨批次共享资源的关联可逐批补齐；不把缺少未导入赛事误报为丢失资料。
        links_changed = False
        obsolete = ResourceCompetition.objects.filter(resource=obj).exclude(competition__code__in=row.get('competition_codes', []))
        if obsolete.exists():
            require(obj.publication_status == 'draft', f'{row["code"]} 已发布，不能修改关联。')
            obsolete.delete()
            links_changed = True
        for competition in Competition.objects.filter(code__in=row.get('competition_codes', [])):
            if not ResourceCompetition.objects.filter(resource=obj, competition=competition).exists():
                require(obj.publication_status == 'draft', f'{row["code"]} 已发布，不能增补关联。')
                checked_save(ResourceCompetition(resource=obj, competition=competition))
                counts['resource_links_created'] += 1
                links_changed = True
        if links_changed and not changed:
            obj.content_version += 1
            obj.last_edited_at = timezone.now()
            obj.updated_by = actor
            checked_save(obj)
            counts['resource_unchanged'] -= 1
            counts['resource_updated'] += 1
        if changed or links_changed:
            checked_save(ResourceRevision(resource=obj, version=obj.content_version, created_by=actor,
                snapshot={**row['fields'], 'code': obj.code, 'content_version': obj.content_version,
                          'competitions': sorted(obj.competitions.values_list('code', flat=True))}))
            stamp_object('resource', obj, row, package_id, actor)
    for row in data['documents']:
        obj, changed = decision('document', KnowledgeDocument, row, package_id, counts)
        if obj and not changed:
            expected = set()
            for field, model, key in [('catalog', CatalogEntry, 'catalog_codes'),
                                      ('competition', Competition, 'competition_codes'),
                                      ('resource', Resource, 'resource_codes')]:
                expected.update((field, pk) for pk in model.objects.filter(code__in=row.get(key, [])).values_list('pk', flat=True))
            actual = set()
            for link in obj.current_revision.links.all():
                actual.update((field, getattr(link, field + '_id')) for field in ('catalog', 'competition', 'resource')
                              if getattr(link, field + '_id') is not None)
            if actual != expected:
                require(obj.review_status == 'draft', f'{row["code"]} 已审核，不能增补关联。')
                changed = True
                counts['document_unchanged'] -= 1
                counts['document_updated'] += 1
        if not changed:
            continue
        obj = obj or checked_save(KnowledgeDocument(code=row['code'], title=row['title']))
        version = (obj.revisions.aggregate(value=Max('version'))['value'] or 0) + 1
        revision = checked_save(DocumentRevision(document=obj, version=version, title=row['title'],
            body=row['body'], edition=row.get('edition', ''), sources=row['sources'],
            attachments=row.get('attachments', []), metadata={**row.get('metadata', {}),
                'package_id': package_id, 'package_root': data['_root']},
            content_hash=digest(row), created_by=actor))
        for field, model, key in [('catalog', CatalogEntry, 'catalog_codes'),
                                   ('competition', Competition, 'competition_codes'),
                                   ('resource', Resource, 'resource_codes')]:
            for target in model.objects.filter(code__in=row.get(key, [])):
                checked_save(DocumentLink(revision=revision, **{field: target}))
        obj.title, obj.current_revision, obj.review_status = row['title'], revision, 'draft'
        checked_save(obj)
        stamp_object('document', obj, row, package_id, actor)
    if apply:
        ImportRun.objects.create(package_id=package_id, package_hash=data['_hash'],
                                 batches=data['_batches'], counts=dict(counts), actor=actor)
    else:
        transaction.set_rollback(True)
    return dict(counts)
