"""人工资料正文与不可变版本；不自动加入公开或 AI 检索。"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder

from common.models import DomainModel


class KnowledgeDocument(DomainModel):
    immutable_fields = ('code',)
    code = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=300)
    review_status = models.CharField(max_length=12, default='draft', choices=[
        ('draft', '待审核'), ('approved', '已审核'), ('withdrawn', '已撤下'),
    ])
    current_revision = models.ForeignKey('DocumentRevision', on_delete=models.PROTECT,
                                         null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.current_revision_id and self.current_revision.document_id != self.pk:
            raise ValidationError('当前版本必须属于本文档。')
        if self.review_status == 'approved' and not self.current_revision_id:
            raise ValidationError('无正文版本的文档不能通过审核。')

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(review_status__in=['draft', 'approved', 'withdrawn']), name='curation_review_status')]


class DocumentRevision(DomainModel):
    immutable_fields = '*'
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.PROTECT, related_name='revisions')
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    body = models.TextField()
    edition = models.CharField(max_length=100, blank=True)
    sources = models.JSONField(default=list)
    attachments = models.JSONField(default=list, blank=True)
    content_hash = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document', 'version'], name='curation_document_version'),
            models.CheckConstraint(condition=Q(version__gte=1), name='curation_version_positive'),
        ]


class DocumentLink(DomainModel):
    """链接属于版本；旧版关联不随新导入变化，每条只关联一种对象。"""
    immutable_fields = '*'
    revision = models.ForeignKey(DocumentRevision, on_delete=models.PROTECT, related_name='links')
    catalog = models.ForeignKey('competition_catalog.CatalogEntry', on_delete=models.PROTECT, null=True, blank=True)
    competition = models.ForeignKey('competitions.Competition', on_delete=models.PROTECT, null=True, blank=True)
    resource = models.ForeignKey('resources.Resource', on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(
                Q(catalog__isnull=False, competition__isnull=True, resource__isnull=True) |
                Q(catalog__isnull=True, competition__isnull=False, resource__isnull=True) |
                Q(catalog__isnull=True, competition__isnull=True, resource__isnull=False)
            ), name='curation_one_link_target'),
            *[models.UniqueConstraint(fields=['revision', name], name=f'curation_link_{name}')
              for name in ('catalog', 'competition', 'resource')],
        ]


class KnowledgeChunk(models.Model):
    """Rebuildable exact-search vectors for an approved document revision."""

    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='search_chunks')
    revision = models.ForeignKey(DocumentRevision, on_delete=models.CASCADE, related_name='+')
    position = models.PositiveIntegerField()
    text = models.TextField()
    source_url = models.URLField(max_length=2048)
    locator = models.CharField(max_length=300, blank=True)
    content_hash = models.CharField(max_length=64)
    text_hash = models.CharField(max_length=64)
    model_id = models.CharField(max_length=160)
    model_revision = models.CharField(max_length=40)
    dimension = models.PositiveSmallIntegerField()
    vector = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['document', 'revision', 'position', 'model_id', 'model_revision'],
                                               name='curation_chunk_version_unique')]
        indexes = [models.Index(fields=['document', 'revision'], name='curation_chunk_current_idx')]


class ImportedObject(models.Model):
    """记录上次导入状态，识别后台人工编辑与底稿之间的冲突。"""
    kind = models.CharField(max_length=16)
    code = models.CharField(max_length=100)
    package_id = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    state_hash = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind', 'code'], name='curation_imported_identity')]


class ImportRun(models.Model):
    package_id = models.CharField(max_length=100)
    package_hash = models.CharField(max_length=64)
    batches = models.JSONField(default=list)
    counts = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class ImportedObjectRevision(DomainModel):
    """保留每次实际写入的完整载荷与状态，包括赛事旧来源和旧日期。"""
    immutable_fields = '*'
    imported_object = models.ForeignKey(ImportedObject, on_delete=models.PROTECT, related_name='revisions')
    version = models.PositiveIntegerField()
    payload = models.JSONField(encoder=DjangoJSONEncoder)
    state = models.JSONField(encoder=DjangoJSONEncoder)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['imported_object', 'version'], name='curation_import_version')]


class DocumentReview(DomainModel):
    immutable_fields = '*'
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.PROTECT, related_name='reviews')
    revision = models.ForeignKey(DocumentRevision, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=KnowledgeDocument._meta.get_field('review_status').choices)
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.revision_id and self.revision.document_id != self.document_id:
            raise ValidationError('审核版本必须属于本文档。')
