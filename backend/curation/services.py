"""离线知识文档审核；不发布其关联赛事或资源。"""
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import KnowledgeDocument, DocumentReview
from .package import require


@transaction.atomic
def review_document(code, *, revision, status, reason, actor):
    if not actor or not actor.is_active or not actor.is_staff or not actor.has_perms([
        'curation.change_knowledgedocument', 'curation.add_documentreview',
    ]):
        raise PermissionDenied('需要知识文档审核权限。')
    require(status in ('approved', 'withdrawn', 'draft'), '审核状态无效。')
    require(reason and reason.strip(), '必须记录审核依据或撤下原因。')
    document = KnowledgeDocument.objects.select_for_update().get(code=code)
    require(document.current_revision_id and document.current_revision.version == revision,
            '当前版本已变化或不存在，请重新阅读后审核。')
    record = DocumentReview(document=document, revision=document.current_revision,
                            status=status, reason=reason.strip(), actor=actor)
    record.full_clean()
    record.save()
    document.review_status = status
    document.full_clean()
    document.save(update_fields=['review_status', 'updated_at'])
    return record
