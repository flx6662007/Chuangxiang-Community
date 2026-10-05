from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from .models import Resource, ResourceRevision, ResourceTaxonomy
from .services import publish_resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'category', 'publication_status', 'availability')
    list_filter = ('publication_status', 'availability', 'category')
    search_fields = ('code', 'title')
    actions = ('publish_selected',)
    readonly_fields = tuple(field.name for field in Resource._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='发布所选已整理学习资料', permissions=['change'])
    def publish_selected(self, request, queryset):
        published = 0
        for resource in queryset:
            try:
                publish_resource(resource.pk, actor=request.user)
                published += 1
            except (ValidationError, PermissionDenied) as exc:
                self.message_user(request, f'{resource.code}：{exc}', messages.ERROR)
        self.message_user(request, f'已发布或原已发布 {published} 条资源。', messages.SUCCESS)


@admin.register(ResourceTaxonomy, ResourceRevision)
class ResourceReferenceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
