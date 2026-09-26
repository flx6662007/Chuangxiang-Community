from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from competitions.views import CompetitionPagination
from teams.errors import check
from teams.views import BusinessView
from . import services
from .models import Appeal, Report
from .serializers import AppealInput, ReportInput, record_output


class GovernanceView(BusinessView):
    permission_classes = [IsAuthenticated]


class OptionsView(GovernanceView):
    def get(self, request):
        def choices(items):
            return [{'code': code, 'name': label} for code, label in items]
        return Response({'report_reasons': choices(Report.Reason.choices),
            'report_statuses': choices(Report.Status.choices), 'appeal_statuses': choices(Appeal.Status.choices)})


class ReportListView(GovernanceView):
    model = Report
    input_class = ReportInput
    submit = staticmethod(services.submit_report)

    def get(self, request):
        rows = self.model.objects.filter(submitted_by=request.user).order_by('-created_at', '-id')
        if 'status' in request.query_params:
            value = request.query_params['status']
            check(value in self.model.Status.values, 'invalid_fields', '状态筛选值无效。', 400)
            rows = rows.filter(status=value)
        return self.page(rows, record_output)

    def post(self, request):
        row = self.submit(actor=request.user, data=self.read_input(self.input_class))
        return Response(record_output(row), status=201)


class AppealListView(ReportListView):
    model = Appeal
    input_class = AppealInput
    submit = staticmethod(services.submit_appeal)


class ReportDetailView(GovernanceView):
    model = Report

    def get(self, request, pk):
        return Response(record_output(self.model.objects.get(pk=pk, submitted_by=request.user)))


class AppealDetailView(ReportDetailView):
    model = Appeal


class AppealTargetsView(GovernanceView):
    def get(self, request):
        paginator = CompetitionPagination()
        page = paginator.paginate_queryset(services.target_choices(request.user), request, view=self)
        return paginator.get_paginated_response(page)
