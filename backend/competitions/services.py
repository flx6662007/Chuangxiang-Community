"""赛事后台受控写入：锁定赛事，校验完整关系后提交，记录必要操作。"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Competition, CompetitionSource, CompetitionTaxonomy


EDITABLE_FIELDS = (
    'code', 'title', 'edition', 'summary', 'description', 'category_id', 'level',
    'organizer', 'tracks', 'eligibility', 'participation_type', 'team_size_min',
    'team_size_max', 'registration_method', 'registration_url', 'campus_arrangements',
    'registration_deadline', 'registration_deadline_at', 'registration_deadline_timezone',
    'submission_deadline', 'submission_deadline_at', 'submission_deadline_timezone',
    'campus_deadline', 'campus_deadline_at', 'campus_deadline_timezone', 'deadline_notes',
    'recruitment_enabled', 'recruitment_deadline', 'recruitment_note',
)
SOURCE_FIELDS = (
    'source_type', 'source_name', 'source_url', 'is_primary',
    'source_published_on', 'source_updated_on',
)


def require_editor(actor, permission='change_competition'):
    if not actor or not actor.is_active or not actor.is_staff or not actor.has_perm(f'competitions.{permission}'):
        raise PermissionDenied('需要相应的赛事管理权限。')


def _audit(competition, actor, action, *, reason='', fields=(), before=None):
    from governance.models import AdminAction
    record = AdminAction(
        competition=competition, actor=actor, action=action, reason=reason,
        changes={'fields': list(fields), 'before_status': before or competition.publication_status,
                 'after_status': competition.publication_status},
    )
    record.full_clean()
    record.save()


def validate_tags(competition, tags):
    old = set(competition.tags.values_list('pk', flat=True)) if competition.pk else set()
    for tag in tags:
        if tag.kind != CompetitionTaxonomy.Kind.TAG or (not tag.is_active and tag.pk not in old):
            raise ValidationError({'tags': '只可新增启用的标签词条；已有停用标签可保留。'})


def _validate_public_relations(competition):
    for source in competition.sources.all():
        source.full_clean()
    validate_tags(competition, competition.tags.all())


@transaction.atomic
def save_competition(instance, *, actor, tags=None):
    from teams.services import lock_competition_graph, reconcile_competition

    if instance.pk is None:
        return _save_competition(instance, actor=actor, tags=tags)
    require_editor(actor)
    with lock_competition_graph(instance.pk):
        saved = _save_competition(instance, actor=actor, tags=tags)
        reconcile_competition(saved.pk)
        return saved


def _save_competition(instance, *, actor, tags=None):
    """只编辑内容；发布状态和系统核验字段不能由此入口伪造。"""
    creating = instance.pk is None
    require_editor(actor, 'add_competition' if creating else 'change_competition')
    saved = Competition() if creating else Competition.objects.select_for_update().get(pk=instance.pk)
    if instance.publication_status != saved.publication_status:
        raise ValidationError('发布和下架请使用专门操作。')
    changed = []
    for name in EDITABLE_FIELDS:
        if getattr(saved, name) != getattr(instance, name):
            changed.append(name)
            setattr(saved, name, getattr(instance, name))
    selected = list(tags) if tags is not None else None
    if selected is not None:
        # 锁住词条以免选择后被另一位管理员停用。
        selected_ids = {tag.pk for tag in selected}
        selected = list(CompetitionTaxonomy.objects.select_for_update().filter(pk__in=selected_ids))
        if len(selected) != len(selected_ids):
            raise ValidationError({'tags': '所选标签不存在。'})
        validate_tags(saved, selected)
        old_ids = set(saved.tags.values_list('pk', flat=True)) if saved.pk else set()
        if old_ids != selected_ids:
            changed.append('tags')
    if saved.category_id:
        CompetitionTaxonomy.objects.select_for_update().get(pk=saved.category_id)
    if saved.publication_status == Competition.PublicationStatus.PUBLISHED:
        _validate_public_relations(saved)
    if not creating and saved.recruitment_enabled and any(
        name in changed for name in ('team_size_min', 'team_size_max', 'participation_type', 'eligibility')
    ):
        from teams.models import Recruitment
        if Recruitment.objects.filter(team__competition_id=saved.pk, publication_status='published', closed_at__isnull=True).exists():
            raise ValidationError('本届有进行中的招募。修改参赛资格或人数规则时，请同时停止招募，核对规则后重新开放。')
    saved.full_clean()
    if creating or changed:
        if creating:
            saved.created_by = actor
        saved.updated_by = actor
        saved.save()
        if selected is not None:
            saved.tags.set(selected)
        saved.full_clean()
        _audit(saved, actor, 'edit', fields=changed)
    return saved


@transaction.atomic
def save_source(instance, *, actor, verified=False):
    """来源变动限草稿/下架赛事；变动后须重新核验，主来源在事务内切换。"""
    creating = instance.pk is None
    require_editor(actor, 'add_competitionsource' if creating else 'change_competitionsource')
    require_editor(actor)
    competition = Competition.objects.select_for_update().get(pk=instance.competition_id)
    if competition.publication_status == Competition.PublicationStatus.PUBLISHED:
        raise ValidationError('请先下架赛事，再修改来源；修改后重新核验发布。')
    saved = CompetitionSource(competition=competition) if creating else CompetitionSource.objects.get(pk=instance.pk)
    if saved.competition_id != competition.pk:
        raise ValidationError('来源不能转移到其他赛事。')
    changed = [field for field in SOURCE_FIELDS if getattr(saved, field) != getattr(instance, field)]
    for field in SOURCE_FIELDS:
        setattr(saved, field, getattr(instance, field))
    if changed:
        saved.last_verified_at = None
    if verified:
        saved.last_verified_at = timezone.now()
    if saved.is_primary:
        for old in competition.sources.filter(is_primary=True).exclude(pk=saved.pk):
            old.is_primary = False
            old.full_clean()
            old.save(update_fields=['is_primary'])
    saved.full_clean()
    saved.save()
    if creating or changed:
        competition.updated_by = actor
        competition.save(update_fields=['updated_by', 'updated_at'])
    if creating or changed or verified:
        _audit(competition, actor, 'verify' if verified else 'edit', fields=['sources'])
    return saved


@transaction.atomic
def verify_source(source_id, *, actor):
    require_editor(actor, 'change_competitionsource')
    require_editor(actor)
    parent_id = CompetitionSource.objects.values_list('competition_id', flat=True).get(pk=source_id)
    competition = Competition.objects.select_for_update().get(pk=parent_id)
    source = competition.sources.get(pk=source_id)
    source.last_verified_at = timezone.now()
    source.full_clean()
    source.save(update_fields=['last_verified_at'])
    competition.full_clean()
    _audit(competition, actor, 'verify', fields=['sources'])
    return source


@transaction.atomic
def publish_competition(competition_id, *, actor):
    require_editor(actor)
    competition = Competition.objects.select_for_update().get(pk=competition_id)
    previous = competition.publication_status
    if competition.category_id:
        CompetitionTaxonomy.objects.select_for_update().get(pk=competition.category_id)
    _validate_public_relations(competition)
    now = timezone.now()
    competition.publication_status = Competition.PublicationStatus.PUBLISHED
    competition.published_at = competition.published_at or now
    competition.last_verified_at = now
    competition.full_clean()
    if previous == Competition.PublicationStatus.PUBLISHED:
        # 仅重新核验不冒充内容更新。
        competition.save(update_fields=['last_verified_at'])
    else:
        competition.updated_by = actor
        competition.save()
    _audit(competition, actor, 'publish' if previous != 'published' else 'verify', before=previous)
    return competition


@transaction.atomic
def withdraw_competition(competition_id, *, actor, reason):
    require_editor(actor)
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        raise ValidationError('请填写 1 至 500 字的具体下架原因。')
    from teams.services import lock_competition_graph, reconcile_competition
    with lock_competition_graph(competition_id) as competition:
        result = _withdraw_locked(competition, actor=actor, reason=reason)
        reconcile_competition(competition_id)
        return result


def _withdraw_locked(competition, *, actor, reason):
    if competition.publication_status != Competition.PublicationStatus.PUBLISHED:
        raise ValidationError('只能下架当前已公开的赛事。')
    competition.publication_status = Competition.PublicationStatus.WITHDRAWN
    competition.withdrawal_reason = reason.strip()
    competition.recruitment_enabled = False
    competition.updated_by = actor
    competition.full_clean()
    competition.save()
    _audit(competition, actor, 'withdraw', reason=competition.withdrawal_reason, before='published')
    return competition
