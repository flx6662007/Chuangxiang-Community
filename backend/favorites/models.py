"""本轮确认模型；写入须 full_clean，并在事务服务中执行跨表联动。"""
from datetime import timedelta
import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from common.models import DomainModel
from common.codes import new_code

class Favorite(DomainModel):
    """用户收藏赛事、科研或资源之一；仅本人可读。"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='收藏用户', on_delete=models.PROTECT, related_name='+')
    competition = models.ForeignKey('competitions.Competition', verbose_name='赛事目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    research = models.ForeignKey('research.ResearchOpportunity', verbose_name='科研目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    resource = models.ForeignKey('resources.Resource', verbose_name='资源目标', on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    created_at = models.DateTimeField('收藏时间', default=timezone.now)

    @property
    def target(self):
        return self.competition or self.research or self.resource

    @property
    def is_target_available(self):
        return bool(self.target and self.target.publication_status == 'published')

    class Meta:
        verbose_name = 'Favorite'
        constraints = [
            models.CheckConstraint(condition=Q(competition__isnull=False, research__isnull=True, resource__isnull=True) | Q(competition__isnull=True, research__isnull=False, resource__isnull=True) | Q(competition__isnull=True, research__isnull=True, resource__isnull=False), name='favorite_one_target'),
            models.UniqueConstraint(fields=['user', 'competition'], name='favorite_competition', condition=Q(competition__isnull=False)),
            models.UniqueConstraint(fields=['user', 'research'], name='favorite_research', condition=Q(research__isnull=False)),
            models.UniqueConstraint(fields=['user', 'resource'], name='favorite_resource', condition=Q(resource__isnull=False)),
        ]
        indexes = [
            models.Index(fields=['user', 'created_at'], name='f01_idx_1'),
        ]
