"""人工知识文档的当前版本查询；页面读取不触发爬取或模型调用。"""
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .models import KnowledgeDocument
from .retrieval import student_visible_documents


def visible_documents(preview=False):
    documents = (KnowledgeDocument.objects.filter(
        review_status__in=('draft', 'published', 'approved'), current_revision__isnull=False,
    ) if preview else student_visible_documents())
    return documents.select_related('current_revision').order_by('code')


def filtered_documents(params, preview=False):
    queryset = visible_documents(preview)
    search = params.get('search', '').strip()
    catalog_code = params.get('catalog_code', '').strip()
    if len(search) > 200 or len(catalog_code) > 16:
        raise ValidationError('搜索最多 200 字符，目录编号最多 16 字符。')
    if search:
        queryset = queryset.filter(Q(current_revision__title__icontains=search)
                                   | Q(current_revision__body__icontains=search))
    if catalog_code:
        queryset = queryset.filter(current_revision__links__catalog__code=catalog_code,
                                   current_revision__links__catalog__is_active=True)
    return queryset.distinct()
