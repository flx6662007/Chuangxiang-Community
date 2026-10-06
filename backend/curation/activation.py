"""Activate the release's team targets and learning resources in the existing models."""
from collections import Counter
from datetime import date, datetime
import hashlib
import re

from django.db import transaction
from django.utils import timezone
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competitions.services import save_competition, save_source, publish_competition_direct
from competitions.recruitment_policy import target, target_code
from competition_catalog.models import CatalogBinding, CatalogEntry
from resources.models import Resource, ResourceTaxonomy, ResourceRevision, ResourceCompetition
from resources.services import publish_resource
from .models import KnowledgeDocument, DocumentRevision, DocumentLink, ImportedObject
from .importer import checked_save, entity_state, stamp_object, require_actor
from .package import digest, require

PACKAGE = 'competition-knowledge-activation-v1'


def _owned(kind, obj):
    if obj is None:
        return
    stamp = ImportedObject.objects.select_for_update().filter(kind=kind, code=obj.code).first()
    require(stamp is not None and stamp.package_id == PACKAGE, f'{obj.code} 不属于统一资料导入。')
    require(stamp.state_hash == digest(entity_state(kind, obj)), f'{obj.code} 已由维护人员修改，请核对后更新。')


def _category(model, code, name):
    obj = model.objects.filter(kind='category', code=code).first()
    if obj is None:
        obj = model.objects.filter(kind='category', name=name).first()
    return obj or checked_save(model(code=code, name=name, kind='category'))


def _stamp(kind, obj, payload, actor):
    payload = {**payload, 'code': obj.code}
    stamp = ImportedObject.objects.filter(kind=kind, code=obj.code).first()
    if stamp and stamp.payload_hash == digest(payload) and stamp.state_hash == digest(entity_state(kind, obj)):
        return
    stamp_object(kind, obj, payload, PACKAGE, actor)


def _latest(records):
    # Editions are compared only within a catalog; parallel tracks in the latest year remain separate.
    def year(r):
        years = re.findall(r'20\d{2}|19\d{2}', r.get('edition', ''))
        return max(map(int, years), default=0)
    years = {}
    for r in records:
        years[r['catalog_code']] = max(years.get(r['catalog_code'], 0), year(r))
    return [r for r in records if year(r) == years[r['catalog_code']]]


def _competition(record, actor, now, category):
    policy = target(record, now)
    code = target_code(record, now)
    obj = Competition.objects.filter(code=code).first()
    _owned('competition', obj)
    if obj and obj.publication_status == 'withdrawn':
        return obj
    next_edition = policy['kind'] == 'next_edition'
    fields = {} if next_edition else record['fields']
    description = '\n\n'.join(s['text'] for s in record['sections'])
    if next_edition:
        description = '面向下一届参赛目标组织队伍。\n参考资料届次：' + record['edition']
    payload = {'record_id': record['id'], 'content_hash': record['content_hash'], 'target': policy['kind']}
    if obj is None:
        title = record['title']
        if next_edition:
            title = re.sub(r'[（(]?20\d{2}年?[）)]?', '', title).strip()
            title = re.sub(r'第[零一二三四五六七八九十百〇两0-9]+届', '', title).strip()
        obj = save_competition(Competition(code=code, title=title, edition=policy['edition'] or '届次未注明',
            summary=record['summary'] if not next_edition else '面向下一届比赛寻找队友。',
            description=description, category=category, level=record.get('level','unknown'),
            participation_type=fields.get('participation_type','unknown')), actor=actor)
        source=record['sources'][0]
        save_source(CompetitionSource(competition=obj, source_type='official', source_name=source['title'],
                    source_url=source['url'], is_primary=True), actor=actor)
        for entry in CatalogEntry.objects.filter(code__in=record['catalog_codes']):
            CatalogBinding.objects.get_or_create(entry=entry, competition=obj,
                defaults={'basis':'统一赛事资料：' + record['id'] + '；组队目标：' + policy['kind']})
        obj=publish_competition_direct(obj.pk, actor=actor, reason='统一赛事资料及提前组队规则')
    changed = False
    values = {key:fields.get(key, '') for key in ('eligibility','organizer','tracks','registration_method','registration_url')}
    values.update(description=description, participation_type=fields.get('participation_type','unknown'),
                  team_size_min=fields.get('team_size_min'), team_size_max=fields.get('team_size_max'),
                  registration_deadline=date.fromisoformat(fields['registration_deadline']) if fields.get('registration_deadline') else None,
                  submission_deadline=date.fromisoformat(fields['submission_deadline']) if fields.get('submission_deadline') else None,
                  recruitment_enabled=policy['open'], recruitment_deadline=None,
                  recruitment_note=policy['reason'])
    instant=fields.get('registration_deadline_at')
    values['registration_deadline_at']=datetime.fromisoformat(instant) if instant else None
    values['registration_deadline_timezone']= instant[-6:] if instant else ''
    if instant:
        # Model date and source-local precise time must describe the same day (24:00 is next day).
        values['registration_deadline']=datetime.fromisoformat(instant).date()
    for key,value in values.items():
        if getattr(obj,key)!=value:
            setattr(obj,key,value);changed=True
    if changed:
        obj=save_competition(obj,actor=actor)
    _stamp('competition',obj,payload,actor)
    return obj


def _resource_document(resource, catalogs, actor):
    code='learning-'+resource.code.removeprefix('knowledge-resource-')
    doc=KnowledgeDocument.objects.filter(code=code).select_related('current_revision').first()
    metadata={'origin':PACKAGE,'resource_version':resource.content_version}
    content={'title':resource.title,'body':resource.description,'catalogs':sorted(catalogs),'url':resource.access_url,'metadata':metadata}
    hashed=digest(content)
    if doc and doc.current_revision.content_hash==hashed:
        return
    if doc:
        require(doc.current_revision.metadata.get('origin')==PACKAGE, '学习资料文档归属不一致。')
        if doc.review_status=='withdrawn':
            return
    else:
        doc=checked_save(KnowledgeDocument(code=code,title=resource.title))
    revision=checked_save(DocumentRevision(document=doc,version=(doc.current_revision.version+1 if doc.current_revision else 1),
        title=resource.title,body=resource.description,sources=[{'url':resource.access_url,'title':resource.title}],
        content_hash=hashed,metadata=metadata,created_by=actor))
    checked_save(DocumentLink(revision=revision,resource=resource))
    for entry in CatalogEntry.objects.filter(code__in=catalogs):
        checked_save(DocumentLink(revision=revision,catalog=entry))
    doc.current_revision=revision;doc.title=resource.title;doc.review_status='published';checked_save(doc)


@transaction.atomic
def activate_release(records, *, actor, now=None):
    require_actor(actor)
    now=now or timezone.now()
    counts=Counter()
    category=_category(CompetitionTaxonomy,'knowledge-competition','赛事资料')
    resource_category=_category(ResourceTaxonomy,'knowledge-learning','赛事学习资料')
    targets={}
    for record in _latest(records):
        obj=_competition(record,actor,now,category)
        targets[record['id']]=obj
        counts['team_targets']+=1
        counts['open_team_targets']+=int(obj.is_recruitment_open)
        counts['next_edition_targets']+=int(target(record,now)['kind']=='next_edition')
    # Stop only owned, obsolete targets; keep their teams and membership history intact.
    for stamp in ImportedObject.objects.filter(package_id=PACKAGE,kind='competition'):
        obj=Competition.objects.get(code=stamp.code)
        if obj.pk not in {x.pk for x in targets.values()} and obj.recruitment_enabled:
            _owned('competition',obj)
            obj.recruitment_enabled=False;obj=save_competition(obj,actor=actor)
            _stamp('competition',obj,{'retired_target':True},actor)
    resources={}
    for record in records:
        for item in record.get('learning_resources',[]):
            entry=resources.setdefault(item['url'],{'item':item,'catalogs':set(),'competitions':set()})
            entry['catalogs'].update(record['catalog_codes'])
            obj=targets.get(record['id'])
            if obj and obj.publication_status=='published':entry['competitions'].add(obj.pk)
    for url,entry in resources.items():
        item=entry['item'];code='knowledge-resource-'+hashlib.sha256(url.encode()).hexdigest()[:24]
        resource=Resource.objects.filter(code=code).first();_owned('resource',resource)
        if resource and (resource.publication_status=='withdrawn' or resource.availability!='available'):
            continue
        if resource is None:
            resource=checked_save(Resource(code=code,title=item['title'],description=item['summary'],access_url=url,
                category=resource_category,created_by=actor,updated_by=actor))
        changed=resource.title!=item['title'] or resource.description!=item['summary']
        desired=set(entry['competitions']);current=set(resource.competitions.values_list('pk',flat=True))
        if changed or desired!=current:
            resource.title=item['title'];resource.description=item['summary']
            resource.content_version+=1;resource.updated_by=actor;resource.last_edited_at=now;checked_save(resource)
            ResourceCompetition.objects.filter(resource=resource).exclude(competition_id__in=desired).delete()
            for pk in desired-current:checked_save(ResourceCompetition(resource=resource,competition_id=pk))
            snapshot={'code':code,'title':resource.title,'description':resource.description,'access_url':url,
                'content_version':resource.content_version,'competitions':sorted(desired)}
            checked_save(ResourceRevision(resource=resource,version=resource.content_version,snapshot=snapshot,created_by=actor))
        if resource.publication_status=='draft':resource=publish_resource(resource.pk,actor=actor)
        _resource_document(resource,entry['catalogs'],actor)
        _stamp('resource',resource,{'item':item,'catalogs':sorted(entry['catalogs'])},actor)
        counts['learning_resources']+=1
    return dict(counts)


@transaction.atomic
def refresh_team_targets(*, now=None):
    """Advance imported targets after a cutoff using the existing maintenance job."""
    from information_library.competition_search import database_corpus
    now = now or timezone.now()
    stamps = ImportedObject.objects.select_for_update().filter(package_id=PACKAGE, kind='competition')
    first = stamps.first()
    if first is None:
        return {}
    records = database_corpus()['records']
    desired = {target_code(record, now) for record in _latest(records)}
    existing = set(stamps.values_list('code', flat=True))
    active = set(Competition.objects.filter(code__in=existing, recruitment_enabled=True).values_list('code', flat=True))
    if desired <= existing and active <= desired:
        return {}
    audit = first.revisions.select_related('created_by').order_by('-version').first()
    require(audit is not None, '组队目标缺少导入记录。')
    return activate_release(records, actor=audit.created_by, now=now)
