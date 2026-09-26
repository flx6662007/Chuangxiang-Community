from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from .models import FetchRun, ProcessingResult, SourceConfig, SourceVersion
from .services import accept_candidate, candidate_changes, reject_candidate


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(SourceConfig)
class SourceConfigAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'adapter_key', 'maintained_by', 'updated_at')
    list_filter = ('is_active', 'adapter_key')
    readonly_fields = ('code', 'base_url', 'adapter_key', 'content_kind', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False  # 只能通过内置白名单初始化。

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FetchRun)
class FetchRunAdmin(ReadOnlyAdmin):
    list_display = ('id', 'source', 'status', 'started_at', 'finished_at', 'http_status', 'error_code')
    list_filter = ('source', 'status', 'trigger')
    search_fields = ('requested_url', 'error_code')
    ordering = ('-started_at',)


@admin.register(SourceVersion)
class SourceVersionAdmin(ReadOnlyAdmin):
    list_display = ('id', 'source', 'title', 'source_published_on', 'first_seen_at', 'last_seen_at')
    search_fields = ('title', 'source_url')
    list_filter = ('source',)


@admin.register(ProcessingResult)
class ProcessingResultAdmin(ReadOnlyAdmin):
    list_display = ('id', 'source_version', 'status', 'decision_mode', 'competition', 'created_at')
    list_filter = ('status', 'decision_mode', 'task_type')
    actions = ('accept_selected', 'reject_selected')
    ordering = ('-created_at',)

    def get_readonly_fields(self, request, obj=None):
        return super().get_readonly_fields(request, obj) + ['field_changes']

    @admin.display(description='与当前已采纳赛事的字段差异')
    def field_changes(self, obj):
        if not obj or not obj.source_version_id:
            return '无赛事原文。'
        previous = ProcessingResult.objects.filter(
            source_version__source_id=obj.source_version.source_id,
            source_version__source_url=obj.source_version.source_url,
            status='accepted', competition__isnull=False,
        ).order_by('-reviewed_at', '-pk').first()
        return candidate_changes(obj, previous.competition) if previous else '新赛事候选。'

    @admin.action(description='核对原文与字段后采纳（不自动开启招募）')
    def accept_selected(self, request, queryset):
        for result in queryset.filter(status='pending', task_type='competition_extract'):
            try:
                accept_candidate(result.pk, actor=request.user)
                self.message_user(request, f'候选 #{result.pk} 已采纳。', messages.SUCCESS)
            except (ValidationError, PermissionDenied) as exc:
                self.message_user(request, f'候选 #{result.pk} 未采纳：{exc}', messages.ERROR)

    @admin.action(description='拒绝所选待处理候选')
    def reject_selected(self, request, queryset):
        for result in queryset.filter(status='pending'):
            try:
                reject_candidate(result.pk, actor=request.user)
            except (ValidationError, PermissionDenied) as exc:
                self.message_user(request, str(exc), messages.ERROR)
