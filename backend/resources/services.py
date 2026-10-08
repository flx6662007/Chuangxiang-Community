"""学习资源发布服务。浏览公开资源不需要登录，维护与发布需后台权限。"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from common.public_content import public_text, safe_source_url
from .models import Resource, ResourceRevision


@transaction.atomic
def publish_resource(resource_id, *, actor, category=None):
    if not (actor and actor.is_active and actor.is_staff
            and actor.has_perm('resources.change_resource')):
        raise PermissionDenied('发布资源需要资源维护权限。')
    resource = Resource.objects.select_for_update().get(pk=resource_id)
    if resource.publication_status == 'published':
        return resource
    if resource.publication_status != 'draft':
        raise ValidationError('已撤下资源须另行复核，不能通过首次发布恢复。')
    if resource.availability != 'available':
        raise ValidationError('不可用资源不能发布。')
    if not safe_source_url(resource.access_url):
        raise ValidationError('资源须有不包含凭据的公开 HTTP(S) 来源链接。')
    if not public_text(resource.title).strip() or not public_text(resource.description).strip():
        raise ValidationError('请补全资源名称和介绍。')
    if category is not None:
        resource.category = category
    if not resource.category_id:
        raise ValidationError('发布前须选择资源类别。')
    resource.publication_status = 'published'
    resource.published_at = timezone.now()
    resource.last_edited_at = resource.published_at
    resource.content_version += 1
    resource.updated_by = actor
    resource.full_clean()
    resource.save()
    # 发布不改变来源的实际核验时间，也不公开相联赛事或知识正文。
    snapshot = {key: getattr(resource, key) for key in (
        'code', 'title', 'description', 'provider', 'access_url', 'source_note',
        'availability', 'content_version',
    )}
    snapshot.update(
        category=resource.category.code,
        tags=sorted(resource.tags.values_list('code', flat=True)),
        directions=sorted(resource.directions.values_list('code', flat=True)),
        competitions=sorted(resource.competitions.values_list('code', flat=True)),
        research_opportunities=sorted(resource.research_opportunities.values_list('code', flat=True)),
    )
    revision = ResourceRevision(resource=resource, version=resource.content_version,
                                snapshot=snapshot, created_by=actor)
    revision.full_clean()
    revision.save()
    return resource
