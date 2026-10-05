"""人工资料库的只读预览权限；普通登录不代表可查看内部草稿。"""

from rest_framework.exceptions import PermissionDenied, ValidationError


LIBRARY_VIEW_PERMISSIONS = (
    'competition_catalog.view_catalogentry',
    'competitions.view_competition',
    'resources.view_resource',
    'curation.view_knowledgedocument',
)


def can_preview_library(user):
    return bool(user.is_authenticated and user.is_active and user.is_staff
                and user.has_perms(LIBRARY_VIEW_PERMISSIONS))


def library_preview(request):
    value = request.query_params.get('preview', '0').lower()
    if value not in ('0', '1', 'false', 'true'):
        raise ValidationError({'preview': '只能填写 0、1、false 或 true。'})
    preview = value in ('1', 'true')
    if preview and not can_preview_library(request.user):
        raise PermissionDenied('仅有资料库查看权限的管理员可预览未发布资料。')
    return preview
