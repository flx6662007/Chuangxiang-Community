from rest_framework import serializers

from teams.serializers import StrictSerializer
from .models import Appeal, Report
from .services import EFFECT_NOTE, REPORT_NOTE


class ReportInput(StrictSerializer):
    target_type = serializers.ChoiceField(choices=['competition', 'recruitment'])
    target_id = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    description = serializers.CharField(min_length=1, max_length=1000, trim_whitespace=True)


class AppealInput(StrictSerializer):
    target_type = serializers.ChoiceField(choices=['restriction', 'recruitment_action', 'report'])
    target_id = serializers.IntegerField(min_value=1)
    description = serializers.CharField(min_length=1, max_length=1000, trim_whitespace=True)


def record_output(row, user=None):
    is_report = isinstance(row, Report)
    if is_report:
        kind, target_id = ('competition', row.competition_id) if row.competition_id else ('recruitment', row.recruitment_id)
    else:
        kind, target_id = ('restriction', row.restriction_id) if row.restriction_id else (
            ('recruitment_action', row.admin_action_id) if row.admin_action_id else ('report', row.report_id))
    result = {
        'id': row.pk, 'target_type': kind, 'target_id': target_id, 'target_title': row.target_title,
        'description': row.description, 'status': row.status, 'status_label': row.get_status_display(),
        'feedback': row.feedback, 'created_at': row.created_at, 'reviewed_at': row.reviewed_at,
        'allowed_actions': [], 'effect_note': REPORT_NOTE if is_report else EFFECT_NOTE,
    }
    if is_report:
        result.update(reason=row.reason, reason_label=row.get_reason_display())
        if row.status != 'pending' and not Appeal.objects.filter(report=row, submitted_by=row.submitted_by, status='pending').exists():
            result['allowed_actions'] = ['appeal']
    return result
