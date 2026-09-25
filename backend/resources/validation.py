from common.models import require
from common.snapshots import content_snapshot


def validate_model(obj):
    if type(obj).__name__ == 'ResourceRevision':
        content_snapshot(obj.snapshot)
        require(obj.snapshot['content_version'] == obj.version, '快照版本与记录版本不一致。')
