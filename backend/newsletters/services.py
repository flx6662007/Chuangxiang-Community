"""Issue publication is an explicit, permission checked transaction."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Newsletter, NewsletterItem, NewsletterRevision
from .presentation import public_link


def require_editor(actor):
    if not (actor and actor.is_active and actor.is_staff and
            all(actor.has_perm('newsletters.' + perm) for perm in (
                'add_newsletter', 'change_newsletter', 'add_newsletterrevision',
                'change_newsletterrevision', 'add_newsletteritem', 'change_newsletteritem'))):
        raise PermissionDenied('需要快讯及版本、内容项的维护权限。')


@transaction.atomic
def publish_issue(issue_id, *, actor):
    require_editor(actor)
    issue = Newsletter.objects.select_for_update().get(pk=issue_id)
    if issue.publication_status != 'draft':
        raise ValidationError('仅可首次发布草稿；更正或恢复撤下内容须另行审核。')
    revision = NewsletterRevision.objects.select_for_update().get(newsletter=issue, status='draft')
    items = list(NewsletterItem.objects.select_for_update().filter(revision=revision).order_by('position'))
    if not items:
        raise ValidationError('快讯至少需要一项内容。')
    for item in items:
        item.full_clean()
        if not public_link(item.source_url):
            raise ValidationError('条目来源必须为安全公开链接。')
        if item.kind != 'activity':
            model = item._meta.get_field(item.kind).remote_field.model
            target = model.objects.select_for_update().get(pk=getattr(item, item.kind + '_id'))
            if target.publication_status != 'published' or target.code.startswith('demo-'):
                raise ValidationError('引用对象必须已公开。')
            if item.kind == 'resource' and target.availability != 'available':
                raise ValidationError('资源不可用，不能发布快讯。')
            if item.kind == 'competition':
                if item.source_updated_at != target.updated_at:
                    raise ValidationError('赛事在草稿建立后发生变化，请复核草稿。')
                urls = list(target.sources.values_list('source_url', flat=True))
            else:
                if item.source_version != target.content_version:
                    raise ValidationError('引用在草稿建立后发生变化，请复核草稿。')
                urls = [target.access_url if item.kind == 'resource' else target.official_url]
            if item.source_url not in urls:
                raise ValidationError('来源与引用对象不一致，请复核后发布。')
    revision.status, revision.confirmed_at, revision.confirmed_by = 'confirmed', timezone.now(), actor
    revision.full_clean()
    revision.save()
    issue.current_revision, issue.publication_status = revision, 'published'
    issue.published_at = timezone.now()
    issue.full_clean()
    issue.save()
    return issue
