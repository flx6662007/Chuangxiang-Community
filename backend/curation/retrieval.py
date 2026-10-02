"""未来学生端检索必须使用此审核边界；本轮不提供检索 HTTP 或向量库。"""
from django.db.models import Q
from .models import KnowledgeDocument


def student_visible_documents():
    return KnowledgeDocument.objects.filter(
        review_status='approved', current_revision__isnull=False,
    ).exclude(
        Q(current_revision__links__competition__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__publication_status__in=['draft', 'withdrawn']) |
        Q(current_revision__links__resource__availability='unavailable')
    ).distinct()
