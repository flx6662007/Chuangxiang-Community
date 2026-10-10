"""仅供回环地址评审的静态页面入口；不作为互联网静态服务器。"""

import os
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_safe
from django.views.static import serve


class PortableLoopbackMiddleware:
    """启动器绑定 127.0.0.1；额外拒绝非本机来源且不信任代理头。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get('REMOTE_ADDR') not in {'127.0.0.1', '::1'}:
            return HttpResponseBadRequest('评审包仅供本机访问。')
        return self.get_response(request)


@require_safe
def portable_health(request):
    response = JsonResponse({
        'status': 'ok',
        'instance_token': os.environ.get('PORTABLE_INSTANCE_TOKEN', ''),
        'package_id': os.environ.get('PORTABLE_PACKAGE_ID', ''),
    })
    response['Cache-Control'] = 'no-store'
    return response


def _safe_relative_path(path):
    # Windows 的反斜线、盘符和隐藏文件也不得逃逸构建目录。
    if '\\' in path or ':' in path or any(part.startswith('.') for part in path.split('/')):
        raise Http404
    return path


def _serve_file(request, path, root):
    response = serve(request, path, document_root=root, show_indexes=False)
    # Windows 注册表可能为 .js 提供非脚本 MIME；nosniff 下需固定这些构建产物。
    content_types = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css'}
    if content_type := content_types.get(Path(path).suffix.lower()):
        response['Content-Type'] = content_type
    return response


@require_safe
def frontend(request, path=''):
    path = _safe_relative_path(path)
    root = Path(settings.PORTABLE_FRONTEND_DIST).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise Http404
    if target.is_file():
        return _serve_file(request, path, root)
    # API、后台和缺失资源必须保持 404，不能被 Vue HTML 掩盖。
    if path.split('/')[0] in {'api', 'admin', 'accounts', 'static', 'assets'} or Path(path).suffix:
        raise Http404
    response = _serve_file(request, 'index.html', root)
    response['Cache-Control'] = 'no-store'
    return response


@require_safe
def static_file(request, path):
    path = _safe_relative_path(path)
    # 优先使用收集目录，也支持包内 Django/admin 自带静态资源，无需额外依赖。
    root = Path(settings.STATIC_ROOT).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise Http404
    if target.is_file():
        return _serve_file(request, path, root)
    found = finders.find(path)
    if not found:
        raise Http404
    found = Path(found)
    return _serve_file(request, found.name, found.parent)
