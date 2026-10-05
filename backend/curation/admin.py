from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from .package import PackageError
from .services import publish_document
from .models import KnowledgeDocument, DocumentRevision, DocumentLink, ImportRun, ImportedObject, ImportedObjectRevision, DocumentReview


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeDocument)
class DocumentAdmin(ReadOnlyAdmin):
    list_display = ('code', 'title', 'review_status', 'updated_at')
    list_filter = ('review_status',)
    search_fields = ('code', 'title')
    actions = ('publish_selected',)

    def has_publish_permission(self, request):
        return request.user.has_perms(['curation.change_knowledgedocument', 'curation.add_documentreview'])

    @admin.action(description='直接发布所选整理资料', permissions=['publish'])
    def publish_selected(self, request, queryset):
        count = 0
        for document in queryset:
            try:
                publish_document(document.code, actor=request.user)
                count += 1
            except (PermissionDenied, ValidationError, PackageError) as exc:
                self.message_user(request, f'{document.code}：{exc}', messages.ERROR)
        self.message_user(request, f'已公开 {count} 份资料。', messages.SUCCESS)


for model in (DocumentRevision, DocumentLink, ImportRun, ImportedObject, ImportedObjectRevision, DocumentReview):
    admin.site.register(model, ReadOnlyAdmin)
