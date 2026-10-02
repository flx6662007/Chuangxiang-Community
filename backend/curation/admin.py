from django.contrib import admin
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


for model in (DocumentRevision, DocumentLink, ImportRun, ImportedObject, ImportedObjectRevision, DocumentReview):
    admin.site.register(model, ReadOnlyAdmin)
