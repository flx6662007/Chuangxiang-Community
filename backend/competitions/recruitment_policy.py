"""Platform team formation is independent of the official registration opening."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Asia/Shanghai')


def cutoff(fields):
    if fields.get('registration_deadline_at'):
        value = datetime.fromisoformat(fields['registration_deadline_at'])
        if value.tzinfo is None:
            raise ValueError('报名截止时刻需要时区')
        return value
    if fields.get('registration_deadline'):
        return datetime.combine(date.fromisoformat(fields['registration_deadline']) + timedelta(days=1), time.min, ZONE)
    return None


def target(record, now):
    fields = record.get('fields', {})
    completed = fields.get('event_completed_on')
    known_deadline = cutoff(fields)
    next_edition = bool((completed and date.fromisoformat(completed) <= now.astimezone(ZONE).date())
                        or (known_deadline is not None and now >= known_deadline))
    deadline = None if next_edition else known_deadline
    individual = fields.get('participation_type') == 'individual'
    opened = not individual and (deadline is None or now < deadline)
    return {'kind': 'next_edition' if next_edition else 'edition',
            'edition': '下一届（官方届次未公布）' if next_edition else record.get('edition', ''),
            'open': opened, 'deadline': deadline.isoformat() if deadline else None,
            'reason': '个人赛不开放参赛队伍招募' if individual else
                      '下一届组队已开放' if next_edition else
                      '本届报名已截止' if not opened else
                      '报名截止前可组队' if deadline else '可提前组队'}


def target_code(record, now):
    import hashlib
    prefix = 'knowledge-next-' if target(record, now)['kind'] == 'next_edition' else 'knowledge-edition-'
    return prefix + hashlib.sha256(record['id'].encode()).hexdigest()[:24]


def open_query(now):
    from django.db.models import Q
    return (Q(publication_status='published', recruitment_enabled=True,
              participation_type__in=['team', 'both', 'unknown']) &
            (Q(recruitment_deadline__isnull=True) | Q(recruitment_deadline__gt=now)) &
            (Q(registration_deadline_at__gt=now) |
             Q(registration_deadline_at__isnull=True, registration_deadline__gte=now.astimezone(ZONE).date()) |
             Q(registration_deadline_at__isnull=True, registration_deadline__isnull=True)))
