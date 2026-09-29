"""官网原文到赛事的受控发布；不执行网络请求，不信任可修改的候选 JSON。"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competitions.services import require_editor, save_competition, save_source, publish_competition
from ingestion.http import checked_url, FetchError
from .models import CatalogBinding, CatalogEntry, CatalogExtraction, OfficialNotice, OfficialSite


CONTENT_FIELDS = (
    'code', 'title', 'edition', 'summary', 'description', 'level', 'organizer',
    'tracks', 'eligibility', 'participation_type', 'team_size_min', 'team_size_max',
    'registration_method', 'registration_url', 'registration_deadline',
    'submission_deadline', 'deadline_notes',
)
DERIVED_FIELDS = {'code', 'category_code', 'category_name'}
EMPTY_VALUES = (None, '', 'unknown')


def notice_snapshot(notice):
    site = notice.site
    return {
        'id': notice.pk, 'entry_code': site.entry.code, 'entry_name': site.entry.name,
        'aliases': list(site.entry.aliases), 'title': notice.title, 'body': notice.body,
        'url': notice.url, 'page_kind': notice.page_kind, 'status': notice.status,
        'published_on': notice.source_published_on.isoformat() if notice.source_published_on else None,
        'hash': notice.content_hash, 'site_kind': site.kind, 'dedicated': site.dedicated,
        'allowed_hosts': list(site.allowed_hosts), 'attachments': deepcopy(notice.attachments),
    }


def _clean_save(obj, **kwargs):
    obj.full_clean()
    obj.save(**kwargs)
    return obj


@transaction.atomic
def persist_extraction(notice, extracted):
    """同原文、同规则只保存一次；算法改动须升级规则版本。"""
    notice = OfficialNotice.objects.select_for_update().get(pk=notice.pk)
    required = {'candidate', 'evidence', 'missing_fields', 'errors', 'disposition', 'rule_version'}
    if not isinstance(extracted, dict) or not required.issubset(extracted):
        raise ValidationError('提取器返回结构不完整。')
    payload = {field: deepcopy(extracted[field]) for field in required}
    old = CatalogExtraction.objects.filter(notice=notice, rule_version=payload['rule_version']).first()
    if old:
        # disposition 可随当前日期从 ready 变为 historical，不改写原始提取快照。
        comparable = required - {'disposition'}
        if old.source_hash != notice.content_hash or any(getattr(old, key) != payload[key] for key in comparable):
            raise ValidationError('同一原文和规则版本出现不同结果；请升级提取规则，不覆盖既有记录。')
        return old
    return _clean_save(CatalogExtraction(notice=notice, source_hash=notice.content_hash, **payload))


def _normal(value):
    return re.sub(r'\s+', '', value)


def _validate_extraction(result, notice, today):
    from .extraction import extract_notice

    parsed = extract_notice(notice_snapshot(notice), today=today)
    for field in ('candidate', 'evidence', 'missing_fields', 'errors', 'rule_version'):
        if parsed.get(field) != getattr(result, field):
            raise ValidationError('候选与当前可信规则重新提取结果不一致，请重新提取；不能直接采纳修改后的 JSON。')
    if parsed.get('disposition') not in ('ready', 'historical') or parsed.get('errors'):
        raise ValidationError('当前原文仍需核对或不是可发布赛事通知。')
    candidate = parsed['candidate']
    if not isinstance(candidate, dict) or set(candidate) - set(CONTENT_FIELDS) - DERIVED_FIELDS:
        raise ValidationError('候选含不允许公开或控制发布状态的字段。')
    for key in ('code', 'title', 'edition', 'summary', 'description', 'organizer', 'eligibility',
                'category_code', 'category_name'):
        if not isinstance(candidate.get(key), str) or not candidate[key].strip():
            raise ValidationError(f'缺少可核验的 {key}，不能发布。')
    if not candidate['code'].startswith(f'catalog-{notice.site.entry.code}-'):
        raise ValidationError('赛事编码与目录归属不符。')
    if not isinstance(result.evidence, dict):
        raise ValidationError('字段依据格式无效。')
    source_text = _normal(notice.title + '\n' + notice.body)
    for field in CONTENT_FIELDS:
        if field in DERIVED_FIELDS or candidate.get(field) in EMPTY_VALUES:
            continue
        snippet = result.evidence.get(field)
        if not isinstance(snippet, str) or not snippet.strip():
            raise ValidationError(f'{field} 缺少原文片段依据。')
        parts = [part for part in snippet.splitlines() if part.strip()]
        if any(_normal(part) not in source_text for part in parts):
            raise ValidationError(f'{field} 的依据不在当前原文中。')
    deadlines = []
    for key in ('registration_deadline', 'submission_deadline'):
        value = candidate.get(key)
        if value is not None:
            try:
                deadlines.append(date.fromisoformat(value))
            except (ValueError, TypeError):
                raise ValidationError('截止日期必须是原文明确的 ISO 日期。')
    if not deadlines:
        raise ValidationError('至少须有一项可核验的官方报名或作品截止日期。')
    effective_deadline = date.fromisoformat(
        candidate.get('registration_deadline') or candidate['submission_deadline'])
    if parsed['disposition'] == 'historical' and effective_deadline >= today:
        raise ValidationError('历史结论与当天或未来截止冲突，须先核对年份和赛项。')
    return candidate, parsed['disposition']


def _verify_current_notice(notice, source_hash):
    if not notice.site.enabled or not notice.site.entry.is_active:
        raise ValidationError('官网入口或目录条目已停用，不发布。')
    if notice.page_kind != 'notice':
        raise ValidationError('目录首页或入口快照不能上架为赛事。')
    current = OfficialNotice.objects.filter(site=notice.site, url=notice.url, is_current_version=True)
    if not notice.is_current_version or current.count() != 1 or not current.filter(pk=notice.pk).exists():
        raise ValidationError('原文已被新版本替代或存在版本冲突；请处理当前版本。')
    content = {'title': notice.title, 'body': notice.body, 'attachments': notice.attachments,
               'source_published_on': str(notice.source_published_on)}
    digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if source_hash != notice.content_hash or digest != notice.content_hash:
        raise ValidationError('原文版本哈希不符，不能核验发布。')
    try:
        checked_url(notice.url, notice.site.allowed_hosts, resolve=False)
    except (FetchError, ValueError) as exc:
        raise ValidationError('原文地址不在已核对的官网范围内。') from exc


def _category(candidate):
    code, name = candidate['category_code'], candidate['category_name']
    category = CompetitionTaxonomy.objects.filter(code=code).first()
    if category is None:
        category = _clean_save(CompetitionTaxonomy(code=code, name=name, kind='category'))
    if category.kind != 'category' or not category.is_active:
        raise ValidationError('候选主分类已停用或用途不符。')
    return category


def _reject_superseded_event(notice, candidate):
    """完整的旧稿不能绕过同赛事尚待解析的新稿，后台单条发布也遵守此规则。"""
    from .extraction import extract_notice

    peers = OfficialNotice.objects.filter(
        site__entry=notice.site.entry, site__enabled=True, is_current_version=True,
        page_kind='notice',
    ).exclude(pk=notice.pk).select_related('site__entry')
    for peer in peers:
        newer = (peer.source_published_on and notice.source_published_on
                 and peer.source_published_on > notice.source_published_on)
        revised = (re.search(r'更新版|修订版|更正|修正', peer.title)
                   and not re.search(r'更新版|修订版|更正|修正', notice.title)
                   and (not notice.source_published_on or not peer.source_published_on
                        or peer.source_published_on >= notice.source_published_on))
        if not newer and not revised:
            continue
        parsed = extract_notice(notice_snapshot(peer), today=timezone.localdate())
        if parsed.get('candidate', {}).get('code') == candidate['code']:
            raise ValidationError(f'同一赛事有更新的官方通知（原文 {peer.pk}）；应先核对新稿，不能发布旧稿。')


def _candidate_values(candidate):
    values = {}
    for field in CONTENT_FIELDS:
        if field not in candidate:
            continue
        value = candidate[field]
        if field.endswith('_deadline') and value is not None:
            value = date.fromisoformat(value)
        values[field] = value
    return values


@transaction.atomic
def publish_extraction(extraction_id, actor, mode='rules'):
    """复核后新建正式赛事；已存在记录只允许完全相同的幂等关联。"""
    if mode not in ('rules', 'human'):
        raise ValidationError('未知处理方式。')
    for permission in ('add_competition', 'change_competition', 'add_competitionsource'):
        require_editor(actor, permission)
    original = CatalogExtraction.objects.select_related('notice__site').get(pk=extraction_id)
    # 所有入口按目录→官网→原文→提取记录锁定，跨官网的同目录新建串行。
    CatalogEntry.objects.select_for_update().get(pk=original.notice.site.entry_id)
    OfficialSite.objects.select_for_update().get(pk=original.notice.site_id)
    notice = OfficialNotice.objects.select_for_update(of=('self',)).select_related(
        'site__entry').get(pk=original.notice_id)
    result = CatalogExtraction.objects.select_for_update().get(pk=extraction_id)
    _verify_current_notice(notice, result.source_hash)
    candidate, disposition = _validate_extraction(result, notice, timezone.localdate())
    if result.status == 'rejected':
        raise ValidationError('此提取结果已拒绝；不能恢复旧决定。')
    if result.status == 'published':
        competition = result.competition
        if competition.publication_status != 'published':
            raise ValidationError('对应赛事已下架或未公开，不自动恢复。')
        return competition

    _reject_superseded_event(notice, candidate)

    values = _candidate_values(candidate)
    competition = Competition.objects.filter(code=candidate['code']).first()
    if competition:
        # 不触碰赛事字段、核验时间或招募开关，也不覆盖人工改动。
        prior = CatalogExtraction.objects.filter(
            competition=competition, status='published', notice__site__entry=notice.site.entry,
        ).exists()
        if not prior or competition.publication_status != 'published':
            raise ValidationError('赛事编码已有人工或未公开记录，须另行核对，不自动覆盖。')
        if any(getattr(competition, field) != value for field, value in values.items()):
            raise ValidationError('现有赛事与新原文或人工修订不同，需管理员核对，不自动覆盖。')
        source = competition.sources.filter(source_url=notice.url, last_verified_at__isnull=False).first()
        if not source:
            raise ValidationError('现有赛事对应另一来源，需核对来源映射。')
        if source.source_published_on != notice.source_published_on:
            raise ValidationError('官方来源发布日期发生变化，需管理员核对，不自动覆盖。')
    else:
        duplicate = Competition.objects.filter(
            title=candidate['title'], edition=candidate['edition'],
        ).exists() or CompetitionSource.objects.filter(
            source_url=notice.url, competition__edition=candidate['edition'],
        ).exists()
        if duplicate:
            raise ValidationError('同届同名或同原文已有赛事，请先核对已有记录和目录映射。')
        category = _category(candidate)
        competition = save_competition(Competition(category=category, **values), actor=actor)
        source = save_source(CompetitionSource(
            competition=competition, source_type='campus' if notice.site.kind == 'campus' else 'official',
            source_name=f'{notice.site.entry.name} 官方通知'[:200],
            source_url=notice.url, is_primary=True, source_published_on=notice.source_published_on,
        ), actor=actor, verified=True)
        source.fetched_at = notice.last_seen_at
        _clean_save(source, update_fields=['fetched_at'])
        competition = publish_competition(competition.pk, actor=actor)
    binding, created = CatalogBinding.objects.get_or_create(
        entry=notice.site.entry, competition=competition,
        defaults={'basis': f'官网原文 {notice.pk}，提取规则 {result.rule_version}；目录系列归属不代表具体奖项认定。'},
    )
    if created:
        binding.full_clean()
    result.status, result.competition = 'published', competition
    result.reviewed_by, result.reviewed_at, result.decision_mode = actor, timezone.now(), mode
    result.review_note = ('明确官方截止的历史赛事归档，未开启招募。' if disposition == 'historical'
                          else '按当前原文与可信规则核验发布；站内招募默认关闭。')
    _clean_save(result)
    return competition


@transaction.atomic
def reject_extraction(extraction_id, *, actor):
    require_editor(actor)
    result = CatalogExtraction.objects.select_for_update().get(pk=extraction_id)
    if result.status != 'pending':
        raise ValidationError('只能拒绝尚未处理的提取记录。')
    result.status, result.decision_mode = 'rejected', 'human'
    result.reviewed_by, result.reviewed_at = actor, timezone.now()
    result.review_note = '管理员拒绝本次提取结果；后续按新规则重新提取。'
    return _clean_save(result)
