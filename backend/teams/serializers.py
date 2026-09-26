"""输入拒绝未知字段；公开输出采用显式白名单。"""
from rest_framework import serializers
from django.db.models import Q
from accounts.permissions import account_eligibility
from .models import RecruitmentRevision, ApplicationRevision, Membership, Application, DepartureRequest, DissolutionRequest, DissolutionResponse, Recruitment


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) if isinstance(data, dict) else set()
        if unknown:
            raise serializers.ValidationError({'unknown_fields': sorted(unknown)})
        return super().to_internal_value(data)


def choice(model, name, **kwargs):
    return serializers.ChoiceField(choices=model._meta.get_field(name).choices, **kwargs)


def codes(**kwargs):
    return serializers.ListField(child=serializers.SlugField(max_length=64), max_length=30, **kwargs)


class RecruitmentInput(StrictSerializer):
    competition_id = serializers.IntegerField(min_value=1)
    team_id = serializers.IntegerField(min_value=1, required=False)
    duration_days = serializers.ChoiceField(choices=[3, 7, 14])
    existing_member_count = serializers.IntegerField(min_value=1, max_value=1000)
    recruitment_quota = serializers.IntegerField(min_value=1, max_value=1000)
    foundation_requirement = choice(RecruitmentRevision, 'foundation_requirement')
    weekly_effort = choice(RecruitmentRevision, 'weekly_effort')
    collaboration_mode = choice(RecruitmentRevision, 'collaboration_mode')
    collaboration_goal = choice(RecruitmentRevision, 'collaboration_goal', required=False, default='', allow_blank=True)
    expected_duration = choice(RecruitmentRevision, 'expected_duration', required=False, default='', allow_blank=True)
    current_skills = codes(required=False, default=list)
    required_roles = codes(required=False, default=list)
    required_skills = codes(required=False, default=list)
    campuses = codes(required=False, default=list)


class EditInput(RecruitmentInput):
    competition_id = None
    team_id = None
    duration_days = None
    expected_version = serializers.IntegerField(min_value=1)
    recruitment_quota = serializers.IntegerField(min_value=0, max_value=1000, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'expected_version':
                field.required = False
                field.default = serializers.empty


class VersionInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)


class ApplicationInput(VersionInput):
    weekly_effort = choice(ApplicationRevision, 'weekly_effort')
    desired_roles = codes(required=False, default=list)
    skills = codes(required=False, default=list)


class ActionInput(VersionInput):
    expected_application_version = serializers.IntegerField(min_value=1)


class ContinueInput(ApplicationInput):
    expected_application_version = serializers.IntegerField(min_value=1)


class DepartureInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=['exit', 'removal'])


class ResponseInput(StrictSerializer):
    response = serializers.ChoiceField(choices=['agree', 'reject'])


class DissolutionInput(StrictSerializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError('请明确确认发起解散。')
        return value


def option_list(revision, field):
    return list(getattr(revision, field).order_by('sort_order', 'pk').values('code', 'name'))


def actor_id(user):
    return user.pk if user and user.is_authenticated else None


def competition_data(competition):
    return {key: getattr(competition, key) for key in ('id', 'code', 'title', 'edition')}


def card_output(card, user=None):
    rev = card.current_revision
    if not rev:
        return None
    from django.utils import timezone
    status = ('closed' if card.closed_at or card.team.dissolved_at else
              'unavailable' if card.publication_status != 'published' or not card.team.competition.is_recruitment_open else
              'expired' if not card.expires_at or card.expires_at <= timezone.now() else
              'paused' if card.team.is_dissolution_pending else 'full' if card.remaining_slots == 0 else 'open')
    actions = []
    uid = actor_id(user)
    if uid == card.team.recruiter_id:
        if status in ['open', 'full']:
            actions += ['edit', 'close']
        elif status == 'paused':
            actions += ['close']
    elif uid and status == 'open' and account_eligibility(user)['eligible']:
        if not Application.objects.filter(recruitment=card, applicant_id=uid).exists() and not Membership.objects.filter(
                competition=card.team.competition, user_id=uid, ended_at__isnull=True).exists():
            actions += ['apply']
    result = {key: getattr(rev, key) for key in (
        'existing_member_count', 'recruitment_quota', 'foundation_requirement', 'weekly_effort',
        'collaboration_goal', 'expected_duration', 'collaboration_mode')}
    result.update({field: option_list(rev, field) for field in ['current_skills', 'required_roles', 'required_skills', 'campuses']})
    result.update({'id': card.pk, 'code': card.code, 'team': {'id': card.team_id, 'code': card.team.code},
        'competition': competition_data(card.team.competition), 'version': rev.version,
        'current_existing_member_count': card.current_existing_member_count,
        'joined_member_count': card.joined_member_count, 'remaining_slots': card.remaining_slots,
        'duration_days': card.duration_days, 'published_at': card.published_at, 'expires_at': card.expires_at,
        'effective_expires_at': min(card.expires_at, card.team.competition.recruitment_deadline)
            if card.expires_at and card.team.competition.recruitment_deadline else card.expires_at,
        'last_edited_at': card.last_edited_at, 'closed_at': card.closed_at, 'close_reason': card.close_reason,
        'is_open': card.is_open, 'status': status, 'allowed_actions': actions})
    return result


def application_output(app, user):
    rev = app.current_revision
    uid = actor_id(user)
    applicant = uid == app.applicant_id
    actions = []
    if app.status in ['pending', 'contact_open']:
        actions = ['withdraw'] if applicant else ['reject' if app.status == 'pending' else 'end']
        own_confirmation = app.applicant_confirmed_at if applicant else app.recruiter_confirmed_at
        if own_confirmation:
            # 解散等待或版本挂起不能阻止当事人收回自己的确认。
            actions += ['revoke-confirmation']
        if app.current_revision.recruitment_revision_id != app.recruitment.current_revision_id and applicant and app.recruitment.is_open:
            actions += ['continue']
        if not app.is_paused and app.recruitment.is_open:
            if app.status == 'pending' and not applicant:
                actions += ['accept']
            if app.status == 'contact_open':
                if not own_confirmation:
                    actions += ['confirm']
    from .services import card_data
    previous, current = card_data(rev.recruitment_revision), card_data(app.recruitment.current_revision)
    changed_fields = [key for key in previous if previous[key] != current[key]]
    return {'id': app.pk, 'recruitment': card_output(app.recruitment, user), 'changed_fields': changed_fields,
        'applicant': {'public_code': app.applicant.public_code}, 'is_applicant': applicant,
        'version': rev.version, 'recruitment_version': rev.recruitment_revision.version,
        'status': app.status, 'is_paused': app.is_paused, 'end_reason': app.end_reason,
        'weekly_effort': rev.weekly_effort, 'desired_roles': option_list(rev, 'desired_roles'), 'skills': option_list(rev, 'skills'),
        'submitted_at': app.submitted_at, 'resolved_at': app.resolved_at,
        'applicant_confirmed_at': app.applicant_confirmed_at, 'recruiter_confirmed_at': app.recruiter_confirmed_at,
        'contact_available': app.can_view_contact(uid), 'allowed_actions': actions}


def departure_output(req, user):
    from django.utils import timezone
    uid = actor_id(user)
    active = req.status == 'pending' and req.deadline_at > timezone.now()
    return {'id': req.pk, 'membership_id': req.membership_id, 'team_id': req.membership.team_id,
        'kind': req.kind, 'status': req.status, 'response': req.response,
        'is_initiator': req.initiator_id == uid, 'is_responder': req.responder_id == uid,
        'created_at': req.created_at, 'deadline_at': req.deadline_at,
        'responded_at': req.responded_at, 'resolved_at': req.resolved_at,
        'allowed_actions': (['withdraw'] if req.initiator_id == uid else ['respond'] if req.responder_id == uid else []) if active else []}


def dissolution_output(req, user):
    from django.utils import timezone
    uid = actor_id(user)
    vote = DissolutionResponse.objects.filter(request=req, membership__user_id=uid).first()
    active = req.status == 'pending' and req.deadline_at > timezone.now()
    return {'id': req.pk, 'team_id': req.team_id, 'status': req.status, 'completion_reason': req.completion_reason,
        'is_initiator': req.initiator_id == uid, 'my_response': vote.response if vote else None,
        'created_at': req.created_at, 'deadline_at': req.deadline_at, 'resolved_at': req.resolved_at,
        'responses': [{'public_code': v.membership.user.public_code, 'response': v.response, 'excluded_at': v.excluded_at}
                      for v in DissolutionResponse.objects.filter(request=req).select_related('membership__user')],
        'allowed_actions': (['withdraw'] if req.initiator_id == uid else ['respond'] if vote and not vote.response and not vote.excluded_at else []) if active else []}


def team_output(team, user):
    uid = actor_id(user)
    recruiter = uid == team.recruiter_id
    own_memberships = Membership.objects.filter(team=team, user_id=uid)
    history_only = not own_memberships.filter(ended_at__isnull=True).exists()
    membership_query = Membership.objects.filter(team=team)
    departure_query = DepartureRequest.objects.filter(membership__team=team)
    dissolution_query = DissolutionRequest.objects.filter(team=team)
    if history_only:
        membership_query = membership_query.filter(user_id=uid)
        departure_query = departure_query.filter(membership__user_id=uid)
        dissolution_query = dissolution_query.filter(Q(initiator_id=uid) | Q(pk__in=DissolutionResponse.objects.filter(
            membership__team=team, membership__user_id=uid).values('request_id')))
    members = []
    for member in membership_query.select_related('user').order_by('pk'):
        active = not member.ended_at and not team.dissolved_at
        pending = DepartureRequest.objects.filter(membership=member, status='pending').exists()
        actions = []
        if active and not pending and member.user_id != team.recruiter_id:
            if recruiter:
                actions = ['removal']
            elif uid == member.user_id:
                actions = ['exit']
        members.append({'id': member.pk, 'user': {'public_code': member.user.public_code},
            'is_self': uid == member.user_id, 'is_recruiter': member.user_id == team.recruiter_id,
            'application_id': member.application_id, 'joined_at': member.joined_at,
            'ended_at': member.ended_at, 'end_reason': member.end_reason, 'allowed_actions': actions})
    actions = []
    if not history_only and recruiter and not team.dissolved_at and not team.is_dissolution_pending:
        actions.append('dissolve')
        if team.competition.is_recruitment_open and account_eligibility(user)['eligible'] and not Recruitment.objects.filter(
                team=team, publication_status='published', closed_at__isnull=True).exists():
            actions.append('publish')
    dissolutions = [dissolution_output(r, user) for r in dissolution_query.order_by('-id')]
    if history_only:
        for request in dissolutions:
            request['responses'] = [v for v in request['responses'] if v['public_code'] == user.public_code]
    return {'id': team.pk, 'code': team.code, 'competition': competition_data(team.competition),
        'recruiter': {'public_code': team.recruiter.public_code}, 'is_recruiter': recruiter, 'dissolved_at': team.dissolved_at,
        'history_only': history_only,
        'recruitments': [] if history_only else [card_output(c, user) for c in Recruitment.objects.filter(team=team).exclude(current_revision=None).order_by('-id')],
        'memberships': members,
        'departure_requests': [departure_output(r, user) for r in departure_query.order_by('-id')],
        'dissolution_requests': dissolutions,
        'allowed_actions': actions}
