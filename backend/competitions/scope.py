"""按学校赛事目录展示；包含全部学科，不删除目录外既有记录。"""
from django.conf import settings


def apply_competition_scope(queryset):
    if not settings.COMPETITION_CATALOG_ONLY:
        return queryset
    return queryset.filter(catalog_bindings__entry__is_active=True).distinct()
