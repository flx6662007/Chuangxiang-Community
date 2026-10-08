"""只读聚合与字段白名单。来源正文始终是数据，不能作为模型或系统指令执行。"""
from django.conf import settings
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.utils import timezone

# 兼容既有调用路径；新业务代码直接从 common.public_content 导入。
from common.public_content import public_text, safe_source_url

from competitions.models import Competition, CompetitionSource
from competitions.scope import apply_competition_scope
from newsletters.models import Newsletter, NewsletterItem, NewsletterRevision
from research.models import ResearchOpportunity, ResearchSource

EDITORIAL_PATH = Path(__file__).parent / 'data' / 'editorial.json'
KINDS = {'competition': '赛事', 'research': '项目招募', 'newsletter': '快讯'}
PERMISSIONS = {
    'competition': ('competitions.view_competition', 'competitions.change_competition'),
    'research': ('research.view_researchopportunity', 'research.change_researchopportunity'),
    'newsletter': ('newsletters.view_newsletter', 'newsletters.change_newsletter'),
}
STATUSES = {'published': '已发布', 'draft': '草稿', 'withdrawn': '已撤下'}
KNOWLEDGE_FIELDS = (
    'id', 'kind', 'title', 'text', 'source_urls', 'source_dates', 'verified_at',
    'updated_at', 'published_at', 'publication_status', 'content_status', 'status_note',
    'version', 'dates',
)


def iso(value):
    return value.isoformat() if value else None


def editorial_date(value):
    try:
        return date.fromisoformat(value).isoformat() if value else None
    except (TypeError, ValueError):
        return None


def is_demo(code, title=''):
    return str(code).startswith('demo-') or '【虚构样例】' in title


def allowed_kinds(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return []
    return [kind for kind, permissions in PERMISSIONS.items() if any(user.has_perm(p) for p in permissions)]


def _record(kind, identifier, title, text, status, urls, source_dates=None, verified_at=None,
            updated_at=None, published_at=None, dates=None, content_status='unknown', status_note='',
            maintenance='', has_evidence=False, version=None):
    row = {
        'id': identifier, 'kind': kind, 'title': public_text(title), 'text': public_text(text),
        'source_urls': list(dict.fromkeys(url for value in urls if (url := safe_source_url(value)))),
        'source_dates': source_dates or [], 'verified_at': iso(verified_at) if not isinstance(verified_at, str) else verified_at,
        'updated_at': iso(updated_at), 'published_at': iso(published_at),
        'publication_status': status, 'content_status': content_status, 'status_note': status_note,
        'dates': dates or {},
    }
    # 每个允许的来源都显示日期缺项；不能因某条补充来源有日期而漏掉主链接。
    supplied_dates = {item.get('url'): item for item in row['source_dates']}
    row['source_dates'] = [{'url': url, 'published_on': supplied_dates.get(url, {}).get('published_on')}
                           for url in row['source_urls']]
    content_hash = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    row['version'] = f'{version}:{content_hash[:16]}' if version is not None else f'sha256:{content_hash}'
    row['_ai_ready'] = bool(status == 'published' and row['source_urls'] and row['title'] and row['text'] and has_evidence)
    row['_maintenance'] = maintenance
    row['kind_label'] = KINDS[kind]
    row['status_label'] = STATUSES.get(status, status)
    return row


def _competition(item):
    sources = [s for s in item.library_sources
               if (s.last_verified_at or item.publication_method == 'direct') and safe_source_url(s.source_url)]
    precise = item.registration_deadline_at or (item.submission_deadline_at if not item.registration_deadline else None)
    day = item.registration_deadline or item.submission_deadline
    expired = precise <= timezone.now() if precise else bool(day and day < timezone.localdate())
    status = 'expired' if expired else ('dated' if day or precise else 'unknown')
    note = '已超过所记录截止时间；作为历史信息，不代表可报名。' if expired else '以官方规则为准；信息收录不等于可报名或已获参赛资格。'
    body = [item.summary, item.description, item.tracks, item.eligibility,
            f'主办方：{item.organizer}' if item.organizer else '', f'届次：{item.edition}',
            f'参赛形式：{item.get_participation_type_display()}',
            f'官方团队人数下限：{item.team_size_min}' if item.team_size_min is not None else '',
            f'官方团队人数上限：{item.team_size_max}' if item.team_size_max is not None else '',
            item.registration_method, item.deadline_notes]
    row = _record(
        'competition', f'db-{item.pk}', item.title,
        '\n'.join(filter(None, body)),
        item.publication_status, [s.source_url for s in sources],
        [{'url': safe_source_url(s.source_url), 'published_on': iso(s.source_published_on)} for s in sources],
        verified_at=item.last_verified_at or max((s.last_verified_at for s in sources if s.last_verified_at), default=None),
        updated_at=item.updated_at, published_at=item.published_at,
        dates={'registration_deadline': iso(item.registration_deadline), 'registration_deadline_at': iso(item.registration_deadline_at),
               'registration_deadline_timezone': item.registration_deadline_timezone or None,
               'submission_deadline': iso(item.submission_deadline), 'submission_deadline_at': iso(item.submission_deadline_at),
               'submission_deadline_timezone': item.submission_deadline_timezone or None,
               'campus_deadline': iso(item.campus_deadline), 'campus_deadline_at': iso(item.campus_deadline_at),
               'campus_deadline_timezone': item.campus_deadline_timezone or None},
        content_status=status, status_note=note, maintenance='既有赛事管理 / competitions.Competition；信息库只读。',
        has_evidence=bool(sources),
    )
    row['_pending_sources'] = [url for s in item.library_sources if not s.last_verified_at
                               and (url := safe_source_url(s.source_url))]
    return row


def _research(item, sources):
    from research.knowledge import research_facts
    summary = item.summary or item.description
    if not item.card_details:
        summary = '\n'.join(dict.fromkeys(filter(None, (item.summary, item.description))))
    facts = research_facts(summary=summary, institution=item.institution or item.recruiting_entity,
        details=item.card_details, primary_url=item.official_url,
        verified_at=iso(item.last_verified_at), published_on=iso(item.source_published_on), sources=sources,
        legacy={'eligibility': item.eligibility, 'work': item.work_content, 'commitment': item.duration_text},
        closed=item.is_closed)
    verified_sources = [s for s in sources if s.verified_at and safe_source_url(s.source_url)]
    urls = ([item.official_url] if item.last_verified_at else []) + [s.source_url for s in verified_sources]
    if item.is_closed:
        content_status, note = 'expired', '该条招募已结束或超过截止时间，仅供历史查阅。'
    elif item.needs_reverification:
        content_status, note = 'needs_review', '长期或未注明截止的招募超过复核周期，当前接收安排须重新确认。'
    else:
        content_status, note = 'unconfirmed_availability', '请以官方最新招募安排为准；收录不保证当前名额。'
    row = _record(
        'research', f'db-{item.pk}', item.title,
        '\n'.join(block['text'] for block in facts['evidence_blocks']),
        item.publication_status, urls,
        [{'url': safe_source_url(s.source_url), 'published_on': iso(s.published_on)} for s in verified_sources],
        verified_at=item.last_verified_at, updated_at=item.updated_at, published_at=item.published_at,
        dates={'deadline_on': iso(item.deadline_on), 'deadline_at': iso(item.deadline_at),
               'deadline_timezone': item.deadline_timezone or None},
        content_status=content_status, status_note=note,
        maintenance='research.ResearchOpportunity 既有记录；在线编辑与发布流程尚待接入。',
        has_evidence=bool(item.last_verified_at and safe_source_url(item.official_url)), version=item.content_version,
    )
    row['_pending_sources'] = [url for value in ([item.official_url] if not item.last_verified_at else [])
                               + [s.source_url for s in sources if not s.verified_at]
                               if (url := safe_source_url(value))]
    row.update(facts)
    row['version'] = str(row['version']) + ':' + facts['facts_version']
    row['source_published_on'] = iso(item.source_published_on)
    if item.card_details:
        row['status_note'] = '历史批次' if facts['has_recruitment_source'] and not facts['recruitment_active'] else ''
        row['content_status'] = 'historical' if row['status_note'] else 'research_material'
    return row


def _editorial_rows(kind):
    # 这是由公共接口读取的人工补充资料，不得在此存储私有草稿、账号或审核记录。
    data = json.loads(EDITORIAL_PATH.read_text(encoding='utf-8'))
    for item in data.get('laboratories' if kind == 'research' else 'newsletters', []):
        identifier, title = str(item.get('id', '')), item.get('title', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', identifier) or is_demo(identifier, title):
            continue
        # 文件约定只存已公开内容；异常写入隐藏状态时宁可不纳入信息库/AI。
        if item.get('publication_status', 'published') != 'published':
            continue
        verified = editorial_date(item.get('verifiedOn'))
        source_date = editorial_date(item.get('date'))
        urls = [item.get('sourceUrl', '')]
        note = '人工整理的公开科研线索；历史说明不等于当前仍有名额，接收安排须向课题组确认。' if kind == 'research' else '人工整理的公开快讯，原文与后续更正为准。'
        yield _record(kind, 'editorial-' + identifier, title,
                      '\n'.join(filter(None, [item.get('summary'), item.get('unit'), item.get('participation')])),
                      'published', urls,
                      [{'url': url, 'published_on': source_date} for value in urls if (url := safe_source_url(value))],
                      verified_at=verified, content_status='unconfirmed_availability' if kind == 'research' else 'editorial',
                      status_note=note, has_evidence=bool(verified),
                      maintenance='backend/information_library/data/editorial.json（公开共享内容，前后台共用；尚不支持在线编辑）。')


def _newsletter(item, revision, items, public_records):
    valid_items, urls, source_dates, invalid_count = [], [], [], 0
    for child in items:
        if child.revision_id != revision.pk:
            continue
        source = safe_source_url(child.source_url)
        if child.kind in ('competition', 'research'):
            target = public_records.get((child.kind, f'db-{getattr(child, child.kind + "_id")}'))
            same_version = (child.source_updated_at == child.competition.updated_at if child.kind == 'competition'
                            else child.source_version == child.research.content_version)
            if not target or not target['_ai_ready'] or not same_version or source not in target['source_urls']:
                invalid_count += 1
                continue
            valid_items.append(target['title'] + '\n' + target['text'])
            urls.extend(target['source_urls'])
            source_dates.extend(target['source_dates'])
        elif child.kind == 'activity' and source and not is_demo('', child.title_snapshot):
            valid_items.append(public_text(child.title_snapshot + '\n' + child.summary_snapshot))
            urls.append(source)
        else:
            # 当前库不支持资源正文；宁可标记待复核，不带入未校验引用或历史快照。
            invalid_count += 1
    confirmed_current = bool(revision.status == 'confirmed' and revision.newsletter_id == item.pk
                             and item.current_revision_id == revision.pk)
    # 任何下架/过时引用都使整期退出 AI 检索；也不展示可能残留旧引用的导读。
    introduction = public_text(revision.introduction) if not invalid_count else ''
    body = '\n\n'.join(filter(None, [introduction, *valid_items]))
    note = f'{invalid_count} 条引用已隐藏（已撤下、内容更新或无法核验）；整期待复核，不进入 AI 检索。' if invalid_count else '仅使用当前公开版本及仍有效的来源引用。'
    return _record('newsletter', f'db-{item.pk}', revision.title, body, item.publication_status,
                   urls, source_dates, verified_at=revision.confirmed_at, updated_at=revision.updated_at,
                   published_at=item.published_at, content_status='needs_review' if invalid_count else 'current',
                   status_note=note, version=revision.version,
                   has_evidence=bool(confirmed_current and valid_items and not invalid_count),
                   maintenance='newsletters.Newsletter 当前版本；在线编辑与确认发布流程尚待接入。')


def collect_records(kinds=None, *, include_unpublished=False):
    selected = set(KINDS if kinds is None else kinds)
    if not selected <= set(KINDS):
        raise ValueError('未知信息类型。')
    rows, public_records = [], {}
    # 快讯引用必须查询其真实当前对象，不能仅凭旧快照的 published 标签判断。
    needed = selected | ({'competition', 'research'} if 'newsletter' in selected else set())
    if 'competition' in needed:
        queryset = Competition.objects.exclude(Q(code__startswith='demo-') | Q(title__contains='【虚构样例】'))
        if not include_unpublished:
            queryset = apply_competition_scope(queryset.filter(publication_status='published'))
        for item in queryset.prefetch_related(Prefetch('sources', queryset=CompetitionSource.objects.all(), to_attr='library_sources')):
            row = _competition(item)
            public_records[('competition', row['id'])] = row
            if 'competition' in selected:
                rows.append(row)
    if 'research' in needed and (include_unpublished or settings.PUBLIC_RESEARCH_ENABLED):
        queryset = ResearchOpportunity.objects.exclude(Q(code__startswith='demo-') | Q(title__contains='【虚构样例】'))
        if not include_unpublished:
            queryset = queryset.filter(publication_status='published')
        sources = {}
        for source in ResearchSource.objects.filter(opportunity_id__in=queryset.values('pk')):
            sources.setdefault(source.opportunity_id, []).append(source)
        for item in queryset:
            row = _research(item, sources.get(item.pk, []))
            public_records[('research', row['id'])] = row
            if 'research' in selected:
                rows.append(row)
        if 'research' in selected:
            # Database state also suppresses editorial copies of drafts/withdrawals.
            reserved = {safe_source_url(url).rstrip('/') for url in ResearchOpportunity.objects.values_list('official_url', flat=True)}
            rows.extend(row for row in _editorial_rows('research')
                        if not any(url.rstrip('/') in reserved for url in row['source_urls']))
    if 'newsletter' in selected:
        queryset = Newsletter.objects.exclude(code__startswith='demo-').select_related('current_revision')
        if not include_unpublished:
            queryset = queryset.filter(publication_status='published')
        for item in queryset:
            revision = item.current_revision
            if revision is None and include_unpublished:
                revision = NewsletterRevision.objects.filter(newsletter=item, status='draft').order_by('-version').first()
            if revision is None or is_demo(item.code, revision.title):
                continue
            items = NewsletterItem.objects.filter(revision=revision).select_related('competition', 'research')
            rows.append(_newsletter(item, revision, items, public_records))
        rows.extend(_editorial_rows('newsletter'))
    return sorted(rows, key=lambda row: (row['updated_at'] or row['published_at'] or row['verified_at'] or '', row['kind'], row['id']), reverse=True)


def admin_records(user, *, query='', kind='', status=''):
    permitted = allowed_kinds(user)
    if not permitted or (kind and kind not in permitted):
        raise PermissionDenied('没有查看该类信息的权限。')
    rows = collect_records([kind] if kind else permitted, include_unpublished=True)
    if status:
        rows = [row for row in rows if row['publication_status'] == status]
    if query:
        needle = query.casefold()
        rows = [row for row in rows if needle in (row['title'] + '\n' + row['text']).casefold()]
    return rows


def knowledge_record(row):
    """最后一道白名单：维护路径、管理状态、联系人和内部说明不传给 AI。"""
    return {field: row[field] for field in KNOWLEDGE_FIELDS}
