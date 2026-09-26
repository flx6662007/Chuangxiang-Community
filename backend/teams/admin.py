"""管理员只读业务记录，只有专门的下架服务可改变招募状态。"""
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Recruitment, RecruitmentOption, Team, Application, Membership, DepartureRequest, DissolutionRequest
from .services import withdraw_recruitment
from .errors import BusinessError


@admin.register(RecruitmentOption)
class OptionAdmin(admin.ModelAdmin):
    list_display = ['code', 'kind', 'name', 'is_active', 'sort_order']
    list_filter = ['kind', 'is_active']
    search_fields = ['code', 'name']

    def get_readonly_fields(self, request, obj=None):
        return ['code', 'kind', 'name'] if obj else []


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WithdrawForm(forms.Form):
    reason = forms.CharField(label='核实后的下架理由', max_length=500, widget=forms.Textarea)


@admin.register(Recruitment)
class RecruitmentAdmin(ReadOnlyAdmin):
    list_display = ['code', 'team', 'publication_status', 'expires_at', 'closed_at', 'management_action']
    list_filter = ['publication_status', 'close_reason']
    search_fields = ['code', 'team__code', 'team__competition__title']

    @admin.display(description='管理操作')
    def management_action(self, obj):
        if obj.publication_status != 'published':
            return '已结束或下架'
        return format_html('<a href="{}">核实下架</a>', reverse('admin:teams_recruitment_withdraw', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:pk>/withdraw/', self.admin_site.admin_view(self.withdraw_view), name='teams_recruitment_withdraw')] + super().get_urls()

    def withdraw_view(self, request, pk):
        from django.core.exceptions import PermissionDenied
        if not self.has_change_permission(request):
            raise PermissionDenied
        card = get_object_or_404(Recruitment, pk=pk)
        form = WithdrawForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            try:
                withdraw_recruitment(pk, actor=request.user, reason=form.cleaned_data['reason'])
            except BusinessError as exc:
                form.add_error(None, str(exc.detail['detail']))
            else:
                self.message_user(request, '招募已下架，未入队申请已结束；正式成员关系保留。', messages.SUCCESS)
                return HttpResponseRedirect(reverse('admin:teams_recruitment_changelist'))
        return TemplateResponse(request, 'admin/teams/withdraw.html', {
            **self.admin_site.each_context(request), 'title': '核实并下架招募', 'opts': self.model._meta,
            'form': form, 'card': card,
        })


for model in (Team, Application, Membership, DepartureRequest, DissolutionRequest):
    admin.site.register(model, ReadOnlyAdmin)
