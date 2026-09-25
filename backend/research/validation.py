from competitions.validators import parse_source_timezone
from common.models import require
from common.snapshots import content_snapshot


def validate_model(obj):
    name = type(obj).__name__
    if name == 'ResearchOpportunity' and obj.deadline_at and obj.deadline_timezone:
        zone = parse_source_timezone(obj.deadline_timezone)
        require(obj.deadline_at.astimezone(zone).date() == obj.deadline_on, '来源时区的时刻日期与截止日期不一致。')
    elif name == 'ResearchSource':
        require(obj.source_url != obj.opportunity.official_url, '主来源已在官方链接保存，无需重复。')
    elif name == 'ResearchRevision':
        content_snapshot(obj.snapshot)
        require(obj.snapshot['content_version'] == obj.version, '快照版本与记录版本不一致。')
