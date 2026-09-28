"""赛事时效只看官方截止：报名优先，其次投稿，未知时间不视为报名开放。"""

from django.db.models import Case, CharField, IntegerField, Q, Value, When
from django.utils import timezone


TIME_STATUSES = ('current', 'expired', 'all')


def annotate_timeliness(queryset, *, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    registration_known = Q(registration_deadline__isnull=False) | Q(registration_deadline_at__isnull=False)
    submission_known = Q(submission_deadline__isnull=False) | Q(submission_deadline_at__isnull=False)

    def closed(field):
        return Q(**{f'{field}_at__lte': now}) | Q(**{
            f'{field}_at__isnull': True, f'{field}__lt': today,
        })

    expired = closed('registration_deadline') | (~registration_known & closed('submission_deadline'))
    return queryset.annotate(
        _deadline_status=Case(
            When(expired, then=Value('closed')),
            When(registration_known | submission_known, then=Value('open')),
            default=Value('unknown'), output_field=CharField(),
        ),
        _deadline_kind=Case(
            When(registration_known, then=Value('registration')),
            When(submission_known, then=Value('submission')),
            default=Value('unknown'), output_field=CharField(),
        ),
    ).annotate(
        _still_open=Case(
            When(_deadline_status='open', then=Value(2)),
            When(_deadline_status='unknown', then=Value(1)),
            default=Value(0), output_field=IntegerField(),
        ),
    )


def deadline_status_label(obj):
    status, kind = obj._deadline_status, obj._deadline_kind
    if status == 'unknown':
        return '截止时间未明确，请查阅官方通知'
    subject = '报名' if kind == 'registration' else '作品提交'
    if status == 'closed':
        return f'{subject}已截止'
    field = f'{kind}_deadline'
    if not getattr(obj, field + '_at') and getattr(obj, field) == timezone.localdate():
        label = f'{subject}今日截止，时刻以原文为准'
    else:
        label = f'{subject}未截止'
    return label if kind == 'registration' else label + '；报名时间未明确'
