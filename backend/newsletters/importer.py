"""Reviewed issue packages: read-only planning, idempotent transactional imports."""
import json
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competitions.services import save_competition, save_source, publish_competition_direct
from resources.models import Resource, ResourceTaxonomy
from resources.services import publish_resource
from .models import Newsletter, NewsletterRevision, NewsletterItem
from .presentation import public_link
from .services import require_editor, publish_issue

DEFAULT_PACKAGE = Path(__file__).parent / 'data' / '2026-10.json'


def load_package(path=DEFAULT_PACKAGE):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    date.fromisoformat(data['source_published_on'])
    date.fromisoformat(data['checked_on'])
    if not data.get('items'):
        raise ValidationError('资料包不能为空。')
    Newsletter._meta.get_field('code').clean(data['code'], None)
    for field in ('title', 'introduction', 'credits'):
        NewsletterRevision._meta.get_field(field).clean(data[field], None)
    seen = set()
    for row in data['items']:
        if row['kind'] not in ('competition', 'resource') or (row['kind'], row['code']) in seen:
            raise ValidationError('本导入器只接受不重复的赛事和资源。')
        seen.add((row['kind'], row['code']))
        model = Competition if row['kind'] == 'competition' else Resource
        model._meta.get_field('code').clean(row['code'], None)
        if not public_link(row['source_url']) or not row['body'].strip():
            raise ValidationError('正文及公开来源必须完整、安全。')
        for field, value in (('title_snapshot', row['title']), ('summary_snapshot', row['body']),
                             ('group_title', row.get('group_title', ''))):
            NewsletterItem._meta.get_field(field).clean(value, None)
        if row['kind'] == 'competition':
            model._meta.get_field('edition').clean(row['edition'], None)
            if row.get('registration_url') and not public_link(row['registration_url']):
                raise ValidationError('报名链接不安全。')
            if row.get('registration_deadline'):
                date.fromisoformat(row['registration_deadline'])
    return data


def normalized_url(value):
    parsed = urlsplit(value)
    return (parsed.hostname or '').lower() + parsed.path.rstrip('/') + '?' + parsed.query + '#' + parsed.fragment


def find_target(row):
    model = Competition if row['kind'] == 'competition' else Resource
    query = model.objects.all()
    if row['kind'] == 'competition':
        # Same official domain across years is not evidence of the same edition.
        query = query.filter(Q(code=row['code']) | Q(edition__in=[row['edition'], *row.get('edition_aliases', [])]))
        query = query.prefetch_related('sources')
    matches = []
    titles = {row['title'], *row.get('title_aliases', [])}
    source = normalized_url(row['source_url'])
    for target in query:
        urls = [s.source_url for s in target.sources.all()] if row['kind'] == 'competition' else [target.access_url]
        if target.code == row['code'] or target.title in titles or source in [normalized_url(url) for url in urls]:
            matches.append(target)
    if len(matches) > 1:
        raise ValidationError(f"{row['title']} 匹配多条记录，请先消歧，未写入。")
    if matches:
        target = matches[0]
        urls = [s.source_url for s in target.sources.all()] if row['kind'] == 'competition' else [target.access_url]
        if target.publication_status == 'withdrawn':
            raise ValidationError(f"{row['title']} 已撤下，不能通过导入重新公开。")
        if row['kind'] == 'resource' and target.availability != 'available':
            raise ValidationError(f"{row['title']} 已标为不可用，请人工复核。")
        if source not in [normalized_url(url) for url in urls]:
            raise ValidationError(f"{row['title']} 已有记录的来源不同，请人工对齐，不覆盖原记录。")
        if row['kind'] == 'competition' and target.edition not in [row['edition'], *row.get('edition_aliases', [])]:
            raise ValidationError('稳定编码对应其他届次，不能复用。')
        if target.publication_status == 'draft' and not managed_draft(target, row):
            raise ValidationError(f"{row['title']} 是其他流程的草稿，请由原维护流程先发布。")
        return target
    return None


def managed_draft(target, row):
    body = target.description
    return target.code == row['code'] and target.title == row['title'] and body == row['body']


def revision_values(data):
    return dict(title=data['title'], introduction=data['introduction'], credits=data['credits'],
                source_published_on=date.fromisoformat(data['source_published_on']))


def existing_revision(data, targets):
    issue = Newsletter.objects.filter(code=data['code']).first()
    if not issue:
        return None, None
    if issue.publication_status == 'withdrawn':
        raise ValidationError('本期已撤下，不允许导入恢复。')
    revisions = NewsletterRevision.objects.filter(newsletter=issue)
    revision = issue.current_revision if issue.publication_status == 'published' else revisions.filter(status='draft').first()
    if not revision or revision.newsletter_id != issue.pk or revisions.count() != 1:
        raise ValidationError('本期已进入其他编辑流程，请人工处理。')
    if any(getattr(revision, key) != value for key, value in revision_values(data).items()):
        raise ValidationError('资料包与已有版本不同，不覆盖已保存内容；请走新版本更正流程。')
    items = list(NewsletterItem.objects.filter(revision=revision).order_by('position'))
    if len(items) != len(data['items']):
        raise ValidationError('已有版本条目数量不同，不能重复导入。')
    for position, (item, row, target) in enumerate(zip(items, data['items'], targets), 1):
        expected = dict(position=position, kind=row['kind'], title_snapshot=row['title'],
                        summary_snapshot=row['body'], group_title=row.get('group_title', ''),
                        source_url=target_source(target, row))
        if not target or getattr(item, row['kind'] + '_id') != target.pk or any(
                getattr(item, key) != value for key, value in expected.items()):
            raise ValidationError('已有条目与资料包不同，不能改写。')
    return issue, revision


def plan_import(data):
    targets = [find_target(row) for row in data['items']]
    issue, revision = existing_revision(data, targets)
    return dict(code=data['code'], title=data['title'], status=issue.publication_status if issue else 'new',
                sourcePublishedOn=data['source_published_on'],
                items=[dict(title=row['title'], kind=row['kind'], action='reuse' if target else 'create',
                            targetCode=target.code if target else row['code'],
                            status=target.publication_status if target else 'new')
                       for row, target in zip(data['items'], targets)])


def clean_save(obj):
    obj.full_clean()
    obj.save()
    return obj


def category_for(model, code, name, actor):
    matches = list(model.objects.filter(Q(code=code) | Q(kind='category', name=name)))
    if len(matches) > 1:
        raise ValidationError('分类存在歧义，请先处理。')
    if matches:
        category = matches[0]
        if category.kind != 'category' or not category.is_active:
            raise ValidationError('分类已停用或用途不匹配。')
        return category
    if not actor.has_perm(f'{model._meta.app_label}.add_{model._meta.model_name}'):
        raise PermissionDenied('缺少新增分类权限。')
    return clean_save(model(code=code, kind='category', name=name))


def target_source(target, row):
    if not target:
        return row['source_url']
    urls = [s.source_url for s in target.sources.all()] if row['kind'] == 'competition' else [target.access_url]
    return next(url for url in urls if normalized_url(url) == normalized_url(row['source_url']))


def create_target(row, data, actor):
    if row['kind'] == 'resource':
        if not actor.has_perm('resources.add_resource'):
            raise PermissionDenied('缺少新增资源权限。')
        category = category_for(ResourceTaxonomy, 'newsletter-tools', '科创与开发工具', actor)
        checked_at = timezone.make_aware(datetime.combine(date.fromisoformat(data['checked_on']), time.min))
        return clean_save(Resource(code=row['code'], title=row['title'], description=row['body'],
            access_url=row['source_url'], category=category, created_by=actor, updated_by=actor,
            last_verified_at=checked_at if row.get('verified') else None,
            source_note='创享快讯人工整理；核验范围及限制见当期来源记录。'))
    category = category_for(CompetitionTaxonomy, 'newsletter-competitions', '科创赛事', actor)
    target = save_competition(Competition(code=row['code'], title=row['title'], edition=row['edition'],
        description=row['body'], summary=row['title'], category=category,
        registration_url=row.get('registration_url', ''),
        registration_deadline=date.fromisoformat(row['registration_deadline']) if row.get('registration_deadline') else None,
        deadline_notes='各赛道时间见快讯及官方通知；未核实的统一截止日期不写入。'), actor=actor)
    save_source(CompetitionSource(competition=target, source_type='official', source_name='赛事官方入口',
                                 source_url=row['source_url'], is_primary=True), actor=actor)
    target.refresh_from_db()
    return target


@transaction.atomic
def import_issue(data, *, actor, publish=False):
    require_editor(actor)
    # Database unique codes + one transaction prevent partial imports on concurrent races.
    plan_import(data)
    targets = []
    for row in data['items']:
        target = find_target(row)
        if target:
            target = type(target).objects.select_for_update().get(pk=target.pk)
            if target.publication_status == 'draft' and not managed_draft(target, row):
                raise ValidationError('引用草稿在预览后发生变化，请重新核对。')
        else:
            target = create_target(row, data, actor)
        targets.append(target)
    issue, revision = existing_revision(data, targets)
    if issue:
        issue = Newsletter.objects.select_for_update().get(pk=issue.pk)
    if issue and issue.publication_status == 'published':
        return issue, False
    if not issue:
        issue = clean_save(Newsletter(code=data['code'], created_by=actor))
        revision = clean_save(NewsletterRevision(newsletter=issue, version=1, created_by=actor,
                             updated_by=actor, **revision_values(data)))
        for position, (row, target) in enumerate(zip(data['items'], targets), 1):
            clean_save(NewsletterItem(revision=revision, position=position, kind=row['kind'],
                title_snapshot=row['title'], summary_snapshot=row['body'], group_title=row.get('group_title', ''),
                source_url=target_source(target, row), **{row['kind']: target},
                source_updated_at=target.updated_at if row['kind'] == 'competition' else None,
                source_version=target.content_version if row['kind'] == 'resource' else None))
    if publish:
        for position, (row, target) in enumerate(zip(data['items'], targets), 1):
            if target.publication_status == 'draft':
                if row['kind'] == 'competition':
                    publish_competition_direct(target.pk, actor=actor, reason='发布已整理的快讯关联赛事；核验范围见当期来源记录。')
                else:
                    publish_resource(target.pk, actor=actor)
                # Only our own publication changes may advance draft source markers.
                # Unrelated edits between draft and publish are rejected by publish_issue.
                target.refresh_from_db()
                item = NewsletterItem.objects.select_for_update().get(revision=revision, position=position)
                if row['kind'] == 'competition':
                    item.source_updated_at = target.updated_at
                else:
                    item.source_version = target.content_version
                clean_save(item)
        issue = publish_issue(issue.pk, actor=actor)
    return issue, True
