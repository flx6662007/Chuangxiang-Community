"""知识正文发布与核验分别留痕；不自动发布关联赛事或资源。"""
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


@transaction.atomic
def publish_document(code, *, actor, reason='按项目决定直接发布整理资料'):
    if not actor or not actor.is_active or not actor.is_staff or not actor.has_perms([
        'curation.change_knowledgedocument', 'curation.add_documentreview',
    ]):
        raise PermissionDenied('需要知识文档发布及记录权限。')
    require(isinstance(reason, str) and 0 < len(reason.strip()) <= 500, '发布原因须为 1—500 字。')
    # current_revision 可空；PostgreSQL 不能锁 LEFT JOIN 的可空一侧。
    # 只锁文档本身，正文版本不可变，无需再次加锁。
    document = KnowledgeDocument.objects.select_for_update(of=('self',)).select_related('current_revision').get(code=code)
    if document.review_status in ('published', 'approved'):
        return document
    require(document.review_status == 'draft', '已撤下资料不能通过首次发布恢复。')
    require(document.current_revision_id and document.current_revision.body.strip(), '请先保存有效正文。')
    record = DocumentReview(document=document, revision=document.current_revision,
                            status='published', reason=reason.strip(), actor=actor)
    record.full_clean()
    record.save()
    document.review_status = 'published'
    document.full_clean()
    document.save(update_fields=['review_status', 'updated_at'])
    return document
