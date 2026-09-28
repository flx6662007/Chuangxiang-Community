from django.contrib import admin
from django.utils.html import format_html

from .models import CatalogBinding, CatalogEntry, MonitorRun, OfficialNotice, OfficialSite


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
