"""后台只通过专门复核表单结案；禁止直接修改提交正文或覆盖历史结论。"""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from teams.errors import BusinessError
from .models import AdminAction, Appeal, Report
from .services import EFFECT_NOTE, REPORT_NOTE, review_record


class ReviewForm(forms.Form):
    outcome = forms.ChoiceField(label='核实后的结论')
    feedback = forms.CharField(label='向提交人反馈的理由与处理进展', min_length=1, max_length=1000, widget=forms.Textarea)

    def __init__(self, *args, model, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['outcome'].choices = [(code, label) for code, label in model.Status.choices if code != 'pending']


class ReadOnlyAdmin(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        # readonly_fields 只限制表单字段，默认 POST 仍会调用 obj.save()。
        # 在读取对象前阻断普通详情写入，避免旧实例覆盖并发复核结果。
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            raise PermissionDenied('此页面只读，请使用专门的核实反馈入口。')
        context = {**(extra_context or {}), 'show_save': False, 'show_save_and_continue': False,
            'show_save_and_add_another': False, 'show_delete': False}
        return super().changeform_view(request, object_id, form_url, extra_context=context)

    def save_model(self, request, obj, form, change):
        # 兜底禁止其他 admin 保存路径；专用 review_view 只调用事务服务。
        raise PermissionDenied('治理记录不得通过通用管理表单保存。')


class ReviewAdmin(ReadOnlyAdmin):
    list_display = ['id', 'target_title', 'submitted_by', 'status', 'created_at', 'reviewed_at', 'review_link']
    list_filter = ['status']
    search_fields = ['target_title', 'submitted_by__public_code']
    ordering = ['-created_at', '-pk']

    def get_readonly_fields(self, request, obj=None):
        return super().get_readonly_fields(request, obj) + ['review_link']

    @admin.display(description='处理入口')
    def review_link(self, obj):
        if obj.status != 'pending':
            return '已处理，结论不可覆盖'
        return format_html('<a href="{}">核实并反馈</a>', reverse(f'admin:governance_{self.model._meta.model_name}_review', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:pk>/review/', self.admin_site.admin_view(self.review_view),
            name=f'governance_{self.model._meta.model_name}_review')] + super().get_urls()

    def review_view(self, request, pk):
        if not self.has_change_permission(request):
            raise PermissionDenied
        row = get_object_or_404(self.model, pk=pk)
        note = EFFECT_NOTE if self.model is Appeal else REPORT_NOTE
        form = ReviewForm(request.POST or None, model=self.model)
        if request.method == 'POST' and form.is_valid():
            try:
                review_record(self.model, pk, actor=request.user, **form.cleaned_data)
            except BusinessError as exc:
                form.add_error(None, str(exc.detail['detail']))
            except ValidationError as exc:
                form.add_error(None, '; '.join(exc.messages))
            else:
                self.message_user(request, '处理反馈已保存。' + note, messages.SUCCESS)
                return HttpResponseRedirect(reverse(f'admin:governance_{self.model._meta.model_name}_change', args=[pk]))
        return TemplateResponse(request, 'admin/governance/review.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': f'处理{self.model._meta.verbose_name} #{pk}', 'record': row, 'form': form, 'effect_note': note,
        })


admin.site.register(Report, ReviewAdmin)
admin.site.register(Appeal, ReviewAdmin)


@admin.register(AdminAction)
class AdminActionAdmin(ReadOnlyAdmin):
    list_display = ['id', 'action', 'actor', 'created_at', 'reason']
    list_filter = ['action']
    ordering = ['-created_at', '-pk']

    def has_change_permission(self, request, obj=None):
        return False
