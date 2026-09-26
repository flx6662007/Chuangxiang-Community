"""获取日志、不可变版本、候选与受控采纳。网络获取永远在业务事务之外。"""
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
import hashlib
import uuid
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competitions.services import publish_competition, require_editor, save_competition, save_source
from .adapters import ADAPTERS, RULE_VERSION
from .http import FetchError, OfficialClient
from .models import FetchRun, ProcessingResult, SourceConfig, SourceVersion
from .validation import source_hash

CONTENT_FIELDS = ('title', 'edition', 'summary', 'description', 'level', 'organizer', 'tracks', 'eligibility',
                  'participation_type', 'team_size_min', 'team_size_max', 'registration_method',
                  'registration_url', 'registration_deadline', 'submission_deadline', 'deadline_notes')
SAFE_UPDATE_FIELDS = {'summary', 'description', 'tracks', 'registration_method', 'deadline_notes'}


def clean_save(obj, **kwargs):
    obj.full_clean()
    obj.save(**kwargs)
    return obj


@contextmanager
def source_mutex(source_id):
    """连接级 PostgreSQL advisory lock；不在整个网络请求期间持有事务/行锁。"""
    if connection.vendor != 'postgresql':
        raise ValidationError('持续采集需要 PostgreSQL 来源级互斥。')
    key = int.from_bytes(hashlib.sha256(f'chuangxiang-ingestion-{source_id}'.encode()).digest()[:8], 'big', signed=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [key])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [key])


def initialize_sources(*, actor):
    require_editor(actor, 'add_competition')
    sources = []
    for adapter in ADAPTERS.values():
        source, created = SourceConfig.objects.get_or_create(code=adapter.key, defaults=dict(
            name=adapter.name, base_url=adapter.base_url, content_kind='competition', adapter_key=adapter.key,
            is_active=True, maintained_by=actor,
        ))
        # 后续命令不重启被管理员停用的源、不替换维护人或配置。
        if created:
            source.full_clean()
        sources.append(source)
    return sources


def _snapshot(competition):
    return {name: (getattr(competition, name).isoformat() if isinstance(getattr(competition, name), date)
                   else getattr(competition, name)) for name in CONTENT_FIELDS}


def candidate_changes(result, competition):
    current = _snapshot(competition)
    return {field: {'before': current[field], 'after': result.candidate.get(field)} for field in CONTENT_FIELDS
            if field in result.candidate and result.candidate[field] != current[field]}


@transaction.atomic
def accept_candidate(result_id, *, actor, mode='human', enable_recruitment=False):
    """只有通过既定规则的新记录自动公开；重要变化与人工修订必须人工处理。

    已发布赛事的来源内容更新留待人工重新核验，绝不临时下架再上线。
    """
    if mode not in ('human', 'rules'):
        raise ValidationError('未知采纳方式。')
    require_editor(actor)
    original = ProcessingResult.objects.select_related('source_version__source').get(pk=result_id)
    SourceConfig.objects.select_for_update().get(pk=original.source_version.source_id)
    result = ProcessingResult.objects.select_for_update(of=('self',)).select_related('source_version__source').get(pk=result_id)
    if result.status == 'accepted':
        return result.competition
    if result.status != 'pending' or result.task_type != 'competition_extract':
        raise ValidationError('只有待处理赛事候选可以采纳。')
    if result.validation_errors:
        raise ValidationError('候选存在提取校验错误，需修正适配器并重新采集。')
    candidate, version = result.candidate, result.source_version
    latest_observation = SourceVersion.objects.filter(source_id=version.source_id, source_url=version.source_url).order_by('-last_seen_at', '-pk').first()
    if latest_observation.pk != version.pk:
        raise ValidationError('此候选已被较新的原文观察替代，不能覆盖当前信息；请处理最新原文候选。')
    if mode == 'rules' and candidate.get('_source_reverted'):
        raise ValidationError('官网回退到历史原文版本，须人工复核后采纳。')
    adapter = ADAPTERS.get(version.source.adapter_key)
    if not adapter or candidate.get('rule_version') != RULE_VERSION:
        raise ValidationError('候选规则版本不受支持，请重新提取。')
    # 由当前不可变原文证据再次检查关键字段，而不是信任 Admin 改过的任意 JSON。
    for field in ('title', 'edition', 'organizer', 'eligibility'):
        evidence = result.evidence.get(field, '')
        if not evidence or (evidence not in version.body_text and evidence != version.title):
            raise ValidationError(f'{field} 没有当前通知原文依据。')
    category, _ = CompetitionTaxonomy.objects.get_or_create(
        code=adapter.category_code, defaults=dict(kind='category', name=adapter.category_name))
    if category.kind != 'category' or not category.is_active:
        raise ValidationError('适配器分类已停用或用途不符。')
    previous = ProcessingResult.objects.filter(
        source_version__source=version.source, source_version__source_url=version.source_url,
        status='accepted', competition__isnull=False,
    ).order_by('-reviewed_at', '-pk').first()
    competition = Competition.objects.filter(
        pk=previous.competition_id).first() if previous else Competition.objects.filter(code=candidate['code']).first()
    creating = competition is None
    if creating:
        # 同标题不同来源不做不可靠的模糊合并。
        if Competition.objects.filter(title=candidate['title'], edition=candidate['edition']).exists():
            raise ValidationError('同届同名已有记录，请管理员确认来源映射后处理。')
        competition = Competition(code=candidate['code'], category=category)
    else:
        from teams.services import lock_competition_graph
        # 本函数外层 atomic 保留这些锁直到候选与赛事一起提交。
        with lock_competition_graph(competition.pk) as locked:
            competition = locked
        if candidate['code'] != competition.code or candidate['edition'] != competition.edition:
            raise ValidationError('同一来源地址出现不同赛事编码或届次，禁止覆盖原赛事。请管理员按新届次独立建档并核对来源关联；此候选保留待处理。')
        changes = candidate_changes(result, competition)
        if competition.publication_status != 'published':
            raise ValidationError('对应赛事当前未公开；采集不会自动恢复人工下架内容。')
        if mode == 'rules':
            baseline = previous.candidate.get('_accepted_snapshot') if previous else None
            if not baseline or _snapshot(competition) != baseline:
                raise ValidationError('正式赛事含人工修订，候选留待管理员复核。')
            if set(changes) - SAFE_UPDATE_FIELDS:
                raise ValidationError('候选涉及日期、人数、资格或来源等重要变更，等待管理员复核。')
        elif set(changes) - SAFE_UPDATE_FIELDS and competition.recruitment_enabled:
            # 重要条款经人工采纳后仍需重新确认招募适用条件；共用赛事服务结算队伍。
            competition.recruitment_enabled = False
    for field in CONTENT_FIELDS:
        value = candidate.get(field)
        if field.endswith('_deadline') and value:
            value = date.fromisoformat(value)
        setattr(competition, field, value)
    competition = save_competition(competition, actor=actor)
    if creating:
        source = save_source(CompetitionSource(
            competition=competition, source_type='official', source_name=version.source.name,
            source_url=version.source_url, is_primary=True, source_published_on=version.source_published_on,
            source_updated_on=version.source_updated_on,
        ), actor=actor, verified=True)
        source.fetched_at = version.last_seen_at
        clean_save(source, update_fields=['fetched_at'])
        competition = publish_competition(competition.pk, actor=actor)
    else:
        source = competition.sources.filter(source_url=version.source_url).first()
        if not source:
            raise ValidationError('新来源关系需管理员核对，不自动改写已发布来源。')
        if source.source_published_on != version.source_published_on or source.source_updated_on != version.source_updated_on:
            if mode == 'rules':
                raise ValidationError('官方来源时间发生变化，等待管理员复核。')
            source.source_published_on = version.source_published_on
            source.source_updated_on = version.source_updated_on
        source.fetched_at = version.last_seen_at
        source.last_verified_at = timezone.now()
        clean_save(source)
        competition.last_verified_at = timezone.now()
        clean_save(competition, update_fields=['last_verified_at'])
    # 这是平台提前停止招募政策，不把未知的官方时区伪装为精确截止时间。
    if creating and enable_recruitment and competition.participation_type in ('team', 'both') and competition.team_size_max and competition.registration_deadline:
        cutoff = datetime.combine(competition.registration_deadline - timedelta(days=1), time.min, ZoneInfo('Asia/Shanghai'))
        if cutoff > timezone.now():
            competition.recruitment_enabled = True
            competition.recruitment_deadline = cutoff
            competition.recruitment_note = '官方通知明确可组队。平台按北京时间在官方报名截止日期前一天 00:00 提前停止招募；这是平台保守期限，不等于官方报名截止时刻。原文：' + version.source_url
            competition = save_competition(competition, actor=actor)
    result.candidate['_accepted_snapshot'] = _snapshot(competition)
    result.status, result.decision_mode = 'accepted', mode
    result.rule_version = RULE_VERSION if mode == 'rules' else ''
    result.reviewed_by = actor if mode == 'human' else None
    result.reviewed_at, result.competition = timezone.now(), competition
    clean_save(result)
    return competition


@transaction.atomic
def reject_candidate(result_id, *, actor):
    require_editor(actor)
    result = ProcessingResult.objects.select_for_update().get(pk=result_id)
    if result.status != 'pending':
        raise ValidationError('只能拒绝待处理候选。')
    result.status, result.decision_mode, result.reviewed_by = 'rejected', 'human', actor
    result.reviewed_at = timezone.now()
    return clean_save(result)


@transaction.atomic
def record_extraction(source, run, page, extracted):
    SourceConfig.objects.select_for_update().get(pk=source.pk)
    version = SourceVersion(
        source=source, first_fetch=run, source_url=page.url, title=extracted.title,
        body_text=extracted.body, source_published_on=extracted.published_on,
    )
    version.content_hash = source_hash(version)
    previous_observation = SourceVersion.objects.filter(source=source, source_url=page.url).order_by('-last_seen_at', '-pk').first()
    old = SourceVersion.objects.filter(source=source, source_url=page.url, content_hash=version.content_hash).first()
    unchanged = old is not None and previous_observation.pk == old.pk
    if old:
        version = old
        version.last_seen_at = timezone.now()
        clean_save(version, update_fields=['last_seen_at'])
    else:
        clean_save(version)
    result = ProcessingResult.objects.filter(source_version=version, task_type='competition_extract', candidate__rule_version=RULE_VERSION).order_by('-created_at', '-pk').first()
    latest_accepted = ProcessingResult.objects.filter(
        source_version__source=source, source_version__source_url=page.url,
        task_type='competition_extract', status='accepted',
    ).order_by('-reviewed_at', '-pk').first()
    if result and result.status == 'accepted' and latest_accepted and latest_accepted.source_version_id != version.pk:
        # A→B→A：复用原文 A，但不能复用 A 过去的采纳决定冒充本次采纳。
        extracted.candidate['_source_reverted'] = True
        result = None
    if not result:
        result = clean_save(ProcessingResult(task_type='competition_extract', source_version=version,
            candidate=extracted.candidate, evidence=extracted.evidence,
            missing_fields=extracted.missing, validation_errors=extracted.errors))
    # 获取成功仅更新 fetched_at，不伪造发布时间/核验时间或修改赛事内容。
    for relation in CompetitionSource.objects.filter(source_url=page.url):
        relation.fetched_at = version.last_seen_at
        clean_save(relation, update_fields=['fetched_at'])
    return result, unchanged


def _finish(run, status, *, error=None, http_status=None):
    run.status, run.finished_at, run.http_status = status, timezone.now(), http_status
    if error:
        run.error_code = error.code
        run.error_summary = str(error)[:1000]
    clean_save(run)


def sync_source(source, *, actor=None, trigger='scheduled', auto_accept=False, enable_recruitment=False, max_pages=20, client=None):
    adapter = ADAPTERS.get(source.adapter_key)
    if not adapter or source.base_url.rstrip('/') != adapter.base_url.rstrip('/'):
        raise ValidationError('来源与已审核适配器入口不一致。')
    if trigger == 'manual' and actor is None:
        raise ValidationError('手动采集须记录触发人。')
    editor = actor or source.maintained_by
    require_editor(editor)
    stats = dict(source=source.code, discovered=0, fetched=0, unchanged=0, accepted=0, pending=0, failed=0, locked=False)
    with source_mutex(source.pk) as acquired:
        if not acquired:
            stats['locked'] = True
            return stats
        batch = uuid.uuid4()
        owned = client is None
        client = client or OfficialClient(adapter.hosts)
        def run_for(url):
            return clean_save(FetchRun(source=source, batch_key=batch, requested_url=url, trigger=trigger,
                                      triggered_by=actor if trigger == 'manual' else None))
        try:
            # 异常退出留下的 running 仅在重新取得互斥后结算，不能把活进程误判为失败。
            for stale in FetchRun.objects.filter(source=source, status='running'):
                _finish(stale, 'failed', error=FetchError('interrupted', '前次采集进程已退出，未完成的获取已结算。'))
            listing_run = run_for(source.base_url)
            urls = []
            try:
                listing = client.get(source.base_url)
                urls = adapter.discover(listing)
                if not urls:
                    raise FetchError('discovery_empty', '列表未发现适配器支持的报名通知，请检查版式或来源范围。')
                stats['discovered'] = len(urls)
                _finish(listing_run, 'succeeded', http_status=listing.status)
            except FetchError as exc:
                _finish(listing_run, 'failed', error=exc, http_status=exc.status)
                stats['failed'] += 1
            # 首轮发现新页，已收录但列表已翻页的有效来源也持续复查。
            known = list(ProcessingResult.objects.filter(
                source_version__source=source, status='accepted', competition__publication_status='published',
            ).order_by('-source_version__last_seen_at').values_list('source_version__source_url', flat=True).distinct())
            urls = list(dict.fromkeys(urls + known))
            seen = {row['source_url']: row['last_seen'] for row in SourceVersion.objects.filter(
                source=source, source_url__in=urls).values('source_url').annotate(last_seen=Max('last_seen_at'))}
            # 新页优先；其后轮换最久未成功获取的页，避免列表较长时旧页永久饥饿。
            urls.sort(key=lambda url: seen[url].timestamp() if url in seen else 0)
            urls = urls[:max_pages]
            for url in urls:
                run = run_for(url)
                try:
                    page = client.get(url)
                    extracted = adapter.parse(page)
                    result, unchanged = record_extraction(source, run, page, extracted)
                    _finish(run, 'unchanged' if unchanged else 'succeeded', http_status=page.status)
                    stats['fetched'] += 1
                    stats['unchanged'] += int(unchanged)
                    if auto_accept and result.status == 'pending' and not result.validation_errors:
                        try:
                            accept_candidate(result.pk, actor=editor, mode='rules', enable_recruitment=enable_recruitment)
                            result.refresh_from_db()
                        except ValidationError as exc:
                            # 保持待复核，可在 Admin 看原文/差异；不是网络失败。
                            result.refresh_from_db()
                            result.candidate['_review_reason'] = '；'.join(exc.messages)[:1000]
                            clean_save(result, update_fields=['candidate'])
                    stats['accepted' if result.status == 'accepted' else 'pending'] += 1
                except FetchError as exc:
                    _finish(run, 'failed', error=exc, http_status=exc.status)
                    stats['failed'] += 1
                except (ValidationError, ValueError, KeyError, TypeError) as exc:
                    _finish(run, 'failed', error=FetchError('parse_validation_failed', '解析或写入校验未通过，旧赛事内容保留。'))
                    stats['failed'] += 1
        finally:
            if owned:
                client.close()
    return stats
