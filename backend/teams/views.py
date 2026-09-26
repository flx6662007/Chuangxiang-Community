from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q, Count, F, Exists, OuterRef
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from competitions.views import CompetitionPagination
from . import services
from .errors import BusinessError, check
from .models import Recruitment, RecruitmentOption, RecruitmentRevision, Application, Team, Membership, DissolutionRequest
from .serializers import (StrictSerializer, RecruitmentInput, EditInput, VersionInput, ApplicationInput,
    ActionInput, ContinueInput, DepartureInput, ResponseInput, DissolutionInput, card_output,
    application_output, team_output, departure_output, dissolution_output)


class BusinessView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, ObjectDoesNotExist):
            exc = BusinessError('not_found', '对象不存在或不可访问。', 404)
        elif isinstance(exc, DjangoValidationError):
            exc = BusinessError('invalid_fields', '字段不符合业务规则。', 400,
                                getattr(exc, 'message_dict', None) or {'non_field_errors': exc.messages})
        elif isinstance(exc, ValidationError):
            exc = BusinessError('invalid_fields', '请检查提交字段。', 400, exc.detail)
        elif isinstance(exc, IntegrityError):
            exc = BusinessError('conflict', '状态已改变或记录已存在，请刷新后重试。')
        return super().handle_exception(exc)

    def read_input(self, cls):
        serializer = cls(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def page(self, objects, output):
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(objects, self.request, view=self)
        return paginator.get_paginated_response([output(obj, self.request.user) for obj in page])


class RecruitmentOptionsView(BusinessView):
    permission_classes = [AllowAny]

    def get(self, request):
        demo_options = (Q(code__startswith='demo-r1-') | Q(code__startswith='demo-r2-')) & Q(name__contains='【虚构样例】')
        result = {key: list(RecruitmentOption.objects.filter(kind=kind, is_active=True).exclude(demo_options).order_by('sort_order', 'pk').values('code', 'name'))
                  for key, kind in [('roles', 'role'), ('skills', 'skill'), ('campuses', 'campus')]}
        labels = {
            'beginner_ok': '零基础可参与', 'introductory': '具备基础知识', 'project_experience': '有项目经验',
            'up_to_2': '每周不超过 2 小时', 'over_2_to_5': '每周 2 至 5 小时', 'over_5_to_10': '每周 5 至 10 小时', 'over_10': '每周超过 10 小时',
            'online': '线上', 'offline': '线下', 'hybrid': '线上线下结合', 'learning': '共同学习',
            'deliver_entry': '完成参赛作品', 'strong_result': '争取较好成绩', 'up_to_1_month': '不超过 1 个月',
            'over_1_to_3_months': '1 至 3 个月', 'over_3_to_6_months': '3 至 6 个月', 'over_6_months': '超过 6 个月', '': '未选择',
        }
        for name in ('foundation_requirement', 'weekly_effort', 'collaboration_mode', 'collaboration_goal', 'expected_duration'):
            result[name] = [{'code': code, 'name': labels[code]} for code, _ in RecruitmentRevision._meta.get_field(name).choices]
        result['duration_days'] = [{'code': value, 'name': f'{value} 天'} for value in (3, 7, 14)]
        return Response(result)


def public_cards():
    return Recruitment.objects.filter(publication_status='published', team__competition__publication_status='published',
        current_revision__isnull=False).exclude((Q(team__competition__code__startswith='demo-r1-') |
            Q(team__competition__code__startswith='demo-r2-')) & Q(team__competition__title__contains='【虚构样例】')).select_related(
                'team__competition', 'team__recruiter', 'current_revision')


class RecruitmentListView(BusinessView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    def get(self, request):
        qs = public_cards().order_by('-published_at', '-id')
        p = request.query_params
        search = p.get('search', '').strip()
        check(len(search) <= 200, 'invalid_fields', '搜索内容最多 200 字符。', 400)
        if search:
            qs = qs.filter(Q(team__competition__title__icontains=search) | Q(team__competition__code__icontains=search) | Q(code__icontains=search))
        if p.get('competition_id'):
            check(p['competition_id'].isdigit(), 'invalid_fields', '赛事 ID 无效。', 400)
            qs = qs.filter(team__competition_id=p['competition_id'])
        for key, lookup in [('role', 'current_revision__required_roles__code'), ('skill', 'current_revision__required_skills__code'),
                            ('campus', 'current_revision__campuses__code'), ('collaboration_mode', 'current_revision__collaboration_mode')]:
            if p.get(key):
                check(len(p[key]) <= 64, 'invalid_fields', '筛选编码过长。', 400)
                qs = qs.filter(**{lookup: p[key]})
        if 'open_only' in p:
            check(p['open_only'] in ['true', 'false', '1', '0'], 'invalid_fields', 'open_only 使用 true 或 false。', 400)
        if p.get('open_only') in ['true', '1']:
            now = timezone.now()
            qs = qs.filter(closed_at__isnull=True, expires_at__gt=now, team__dissolved_at__isnull=True,
                           team__competition__recruitment_enabled=True).filter(
                Q(team__competition__recruitment_deadline__isnull=True) | Q(team__competition__recruitment_deadline__gt=now))
            occupied = Membership.objects.filter(application__recruitment_id=OuterRef('pk'), ended_at__isnull=True).values('application__recruitment_id').annotate(n=Count('pk')).values('n')
            from django.db.models import Subquery, IntegerField, Value
            from django.db.models.functions import Coalesce
            qs = qs.annotate(occupied=Coalesce(Subquery(occupied, output_field=IntegerField()), Value(0)),
                             paused=Exists(DissolutionRequest.objects.filter(team_id=OuterRef('team_id'), status='pending')))
            qs = qs.filter(paused=False, current_revision__recruitment_quota__gt=F('occupied'))
        return self.page(qs.distinct(), card_output)

    def post(self, request):
        card = services.publish_recruitment(actor=request.user, data=self.read_input(RecruitmentInput))
        return Response(card_output(card, request.user), status=status.HTTP_201_CREATED)


class RecruitmentPreviewView(BusinessView):
    def post(self, request):
        return Response(services.preview_recruitment(actor=request.user, data=self.read_input(RecruitmentInput)))


class RecruitmentDetailView(BusinessView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else super().get_permissions()

    def get(self, request, pk):
        return Response(card_output(public_cards().get(pk=pk), request.user))

    def patch(self, request, pk):
        card = services.edit_recruitment(pk, actor=request.user, data=self.read_input(EditInput))
        return Response(card_output(card, request.user))


class RecruitmentCloseView(BusinessView):
    def post(self, request, pk):
        return Response(card_output(services.close_recruitment(pk, actor=request.user, data=self.read_input(VersionInput)), request.user))


class ApplicationCreateView(BusinessView):
    def post(self, request, pk):
        app = services.submit_application(pk, actor=request.user, data=self.read_input(ApplicationInput))
        return Response(application_output(app, request.user), status=status.HTTP_201_CREATED)


def own_applications(user):
    return Application.objects.filter(Q(applicant=user) | Q(recruitment__team__recruiter=user)).select_related(
        'applicant', 'recruitment__team__competition', 'recruitment__team__recruiter', 'recruitment__current_revision',
        'current_revision__recruitment_revision')


def settle_for(ids):
    for competition_id in sorted(set(ids)):
        services.execute(competition_id, None, lambda now: None)


class ApplicationListView(BusinessView):
    def get(self, request):
        scope = request.query_params.get('scope', 'sent')
        check(scope in ['sent', 'received'], 'invalid_fields', 'scope 使用 sent 或 received。', 400)
        qs = own_applications(request.user)
        qs = qs.filter(applicant=request.user) if scope == 'sent' else qs.filter(recruitment__team__recruiter=request.user)
        settle_for(qs.filter(status__in=services.LIVE).values_list('recruitment__team__competition_id', flat=True))
        return self.page(qs.order_by('-id'), application_output)


class ApplicationDetailView(BusinessView):
    def get(self, request, pk):
        app = own_applications(request.user).get(pk=pk)
        settle_for([app.recruitment.team.competition_id])
        return Response(application_output(own_applications(request.user).get(pk=pk), request.user))


class ApplicationActionView(BusinessView):
    def post(self, request, pk, action):
        own_applications(request.user).get(pk=pk)
        check(action in ['accept', 'reject', 'withdraw', 'end', 'continue', 'confirm', 'revoke-confirmation'],
              'not_found', '操作不存在。', 404)
        data = self.read_input(ContinueInput if action == 'continue' else ActionInput)
        app = services.application_action(pk, actor=request.user, action=action, data=data)
        return Response(application_output(app, request.user))


class ApplicationContactView(BusinessView):
    def get(self, request, pk):
        app = own_applications(request.user).get(pk=pk)
        settle_for([app.recruitment.team.competition_id])
        app = own_applications(request.user).get(pk=pk)
        check(app.can_view_contact(request.user.pk), 'contact_not_authorized', '当前关系未开放或已结束联系权限。', 403)
        other = app.recruitment.team.recruiter if request.user.pk == app.applicant_id else app.applicant
        response = Response({field: getattr(other, field) for field in ['public_code', 'email', 'wechat_id', 'phone_number', 'contact_updated_at']})
        response['Cache-Control'] = 'no-store, private'
        response['Pragma'] = 'no-cache'
        return response


def own_teams(user):
    return Team.objects.filter(pk__in=Membership.objects.filter(user=user).values('team_id')).select_related('competition', 'recruiter')


class TeamListView(BusinessView):
    def get(self, request):
        qs = own_teams(request.user)
        settle_for(qs.values_list('competition_id', flat=True))
        return self.page(qs.order_by('-id'), team_output)


class TeamDetailView(BusinessView):
    def get(self, request, pk):
        team = own_teams(request.user).get(pk=pk)
        settle_for([team.competition_id])
        return Response(team_output(own_teams(request.user).get(pk=pk), request.user))


class DepartureCreateView(BusinessView):
    def post(self, request, pk):
        data = self.read_input(DepartureInput)
        return Response(departure_output(services.request_departure(pk, actor=request.user, kind=data['kind']), request.user), status=201)


class DepartureActionView(BusinessView):
    def post(self, request, pk, action):
        data = self.read_input(ResponseInput if action == 'respond' else StrictSerializer)
        return Response(departure_output(services.departure_action(pk, actor=request.user, action=action, response=data.get('response')), request.user))


class DissolutionCreateView(BusinessView):
    def post(self, request, pk):
        self.read_input(DissolutionInput)
        return Response(dissolution_output(services.request_dissolution(pk, actor=request.user), request.user), status=201)


class DissolutionActionView(BusinessView):
    def post(self, request, pk, action):
        data = self.read_input(ResponseInput if action == 'respond' else StrictSerializer)
        return Response(dissolution_output(services.dissolution_action(pk, actor=request.user, action=action, response=data.get('response')), request.user))
