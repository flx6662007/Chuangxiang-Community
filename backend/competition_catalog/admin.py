from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.html import format_html

from .models import CatalogBinding, CatalogEntry, CatalogExtraction, MonitorRun, OfficialNotice, OfficialSite


class ReadOnlyAdmin(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CatalogEntry)
class CatalogEntryAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'grade', 'levels', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('grade', 'is_active')


@admin.register(OfficialSite)
class OfficialSiteAdmin(ReadOnlyAdmin):
    list_display = ('entry', 'source_link', 'kind', 'last_status', 'last_success_at', 'next_check_at')
    list_select_related = ('entry',)
    search_fields = ('entry__code', 'entry__name', 'url', 'last_error')
    list_filter = ('last_status', 'kind', 'enabled')

    @admin.display(description='官网入口')
    def source_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">打开来源</a>', obj.url)


@admin.register(OfficialNotice)
class OfficialNoticeAdmin(ReadOnlyAdmin):
    list_display = ('title', 'site', 'page_kind', 'status', 'source_published_on', 'last_seen_at', 'is_current_version')
    list_select_related = ('site__entry',)
    search_fields = ('title', 'body', 'site__entry__code')
    list_filter = ('page_kind', 'status', 'is_current_version')


@admin.register(MonitorRun)
class MonitorRunAdmin(ReadOnlyAdmin):
    list_display = ('site', 'started_at', 'status', 'pages', 'created', 'unchanged')
    list_select_related = ('site__entry',)
    list_filter = ('status',)


@admin.register(CatalogBinding)
class CatalogBindingAdmin(ReadOnlyAdmin):
    list_display = ('entry', 'competition')
    list_select_related = ('entry', 'competition')


@admin.register(CatalogExtraction)
class CatalogExtractionAdmin(ReadOnlyAdmin):
    list_display = ('id', 'notice', 'disposition', 'status', 'rule_version', 'competition', 'reviewed_at')
    list_select_related = ('notice__site__entry', 'competition', 'reviewed_by')
    list_filter = ('status', 'disposition', 'rule_version')
    search_fields = ('notice__title', 'notice__site__entry__code', 'competition__title')
    actions = ('publish_selected', 'reject_selected')

    def has_publish_permission(self, request):
        return request.user.is_active and request.user.is_staff and all(
            request.user.has_perm(f'competitions.{permission}') for permission in
            ('add_competition', 'change_competition', 'add_competitionsource'))

    @admin.action(description='重新核对官网规则并发布所选结果（默认不开招募）', permissions=['publish'])
    def publish_selected(self, request, queryset):
        from .publication import publish_extraction
        count = 0
        for record in queryset.order_by('pk'):
            try:
                publish_extraction(record.pk, request.user, mode='human')
                count += 1
            except (ValidationError, PermissionDenied) as exc:
                detail = '；'.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                self.message_user(request, f'提取记录 {record.pk} 未发布：{detail}', messages.ERROR)
        if count:
            self.message_user(request, f'{count} 条结果已核对并关联正式赛事。', messages.SUCCESS)

    @admin.action(description='拒绝所选待处理结果', permissions=['publish'])
    def reject_selected(self, request, queryset):
        from .publication import reject_extraction
        for record in queryset.order_by('pk'):
            try:
                reject_extraction(record.pk, actor=request.user)
            except (ValidationError, PermissionDenied) as exc:
                detail = '；'.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                self.message_user(request, f'提取记录 {record.pk} 未拒绝：{detail}', messages.ERROR)
