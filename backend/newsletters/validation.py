from common.models import require


def validate_model(obj):
    name = type(obj).__name__
    old = None if obj._state.adding else type(obj).objects.filter(pk=obj.pk).first()
    if name == 'Newsletter' and obj.current_revision_id:
        require(obj.current_revision.newsletter_id == obj.pk and obj.current_revision.status == 'confirmed', '当前版本须属于本期且已确认。')
    elif name == 'NewsletterRevision':
        if old and old.status == 'confirmed':
            require(all(getattr(old,f.attname) == getattr(obj,f.attname) for f in obj._meta.fields), '已确认版本不可原地更改。')
        if obj.status == 'confirmed':
            from .models import NewsletterItem
            items = NewsletterItem.objects.filter(revision=obj) if obj.pk else []
            require(bool(items), '确认前至少有一个内容项。')
            for item in items:
                require(bool(item.title_snapshot.strip() and item.summary_snapshot.strip() and item.source_url.strip()), '内容项标题、摘要和来源必须完整。')
    elif name == 'NewsletterItem':
        require(obj.revision.status == 'draft', '已确认版本不能增改内容项。')
        if obj.kind == 'competition':
            require(obj.source_updated_at is not None and obj.source_version is None, '赛事引用保存更新时间，不伪造版本号。')
        elif obj.kind in ['research', 'resource']:
            require(obj.source_version is not None and obj.source_version >= 1, '科研和资源引用须保存来源版本。')
