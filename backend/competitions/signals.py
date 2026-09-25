"""关系入口的基础保护；发布和并发写入仍需统一事务服务。"""

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver

from .models import Competition, CompetitionTaxonomy


@receiver(m2m_changed, sender=Competition.tags.through)
def validate_tag_selection(sender, instance, action, reverse, pk_set, using, **kwargs):
    if action != 'pre_add' or not pk_set:
        return
    if reverse:
        valid = instance.kind == CompetitionTaxonomy.Kind.TAG and instance.is_active
    else:
        valid = not CompetitionTaxonomy.objects.using(using).filter(pk__in=pk_set).exclude(
            kind=CompetitionTaxonomy.Kind.TAG, is_active=True,
        ).exists()
    if not valid:
        raise ValidationError('赛事标签只能新增选择启用的标签词条。')


@receiver(pre_delete, sender=CompetitionTaxonomy)
def protect_used_taxonomy(sender, instance, using, **kwargs):
    if instance.tagged_competitions.using(using).exists() or instance.categorized_competitions.using(using).exists():
        raise ProtectedError('被使用的分类和标签请停用，不可删除。', [instance])


@receiver(pre_delete, sender=Competition)
def protect_published_competition(sender, instance, **kwargs):
    if instance.published_at is not None or instance.publication_status != Competition.PublicationStatus.DRAFT:
        raise ProtectedError('发布过的赛事请下架，不可删除。', [instance])
