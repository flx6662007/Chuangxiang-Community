"""邀请内测入口：口令隔离、静态页面及 Windows 上的 Waitress 服务。"""

import argparse
import base64
import binascii
import hashlib
import hmac
import ipaddress
import logging
import mimetypes
import os
import re
import threading
import time
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.db.utils import InterfaceError, OperationalError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_safe


GATE_COOKIE_NAME = '__Host-chuangxiang_beta_gate'
GATE_COOKIE_SALT = 'chuangxiang.private-beta-gate.v1'
GATE_COOKIE_AGE = 4 * 60 * 60


def gate_cookie_binding(host):
    """入口 cookie 随域名或入口凭据更换失效；不携带可还原的入口口令。"""
    message = '\0'.join((host.lower(), settings.PRIVATE_BETA_USERNAME, settings.PRIVATE_BETA_PASSWORD))
    return hmac.new(settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def validate_private_beta_environment(values, *, regular_db_name='', frontend_dist=None):
    """所有内测专用字段显式提供，绝不复用开发数据库或空入口口令。"""
    def required(name, minimum=1):
        value = values.get(name, '')
        if not isinstance(value, str) or len(value) < minimum or value.startswith('replace-with-'):
            raise ImproperlyConfigured(f'内测配置缺失或过短：{name}。')
        return value

    origin = required('PRIVATE_BETA_ORIGIN')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.netloc != parsed.hostname
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', parsed.hostname)
            or '.' not in parsed.hostname or '..' in parsed.hostname):
        raise ImproperlyConfigured('PRIVATE_BETA_ORIGIN 必须为不含路径、端口的精确 HTTPS 域名。')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ImproperlyConfigured('PRIVATE_BETA_ORIGIN 必须是 HTTPS 域名，不能使用 IP 地址。')

    username = required('PRIVATE_BETA_USERNAME', 8)
    password = required('PRIVATE_BETA_PASSWORD', 24)
    if ':' in username or any(ord(char) < 32 for char in username + password):
        raise ImproperlyConfigured('内测入口凭据不能包含控制字符，用户名不能包含冒号。')
    secret_key = required('PRIVATE_BETA_SECRET_KEY', 50)
    db_name = required('PRIVATE_BETA_DB_NAME')
    if not re.fullmatch(r'chuangxiang_beta_[a-z0-9_]{1,40}', db_name) or db_name == regular_db_name:
        raise ImproperlyConfigured('内测必须使用独立的 chuangxiang_beta_ 数据库，不能连接开发库。')
    state_dir = Path(required('PRIVATE_BETA_STATE_DIR'))
    if not state_dir.is_absolute():
        raise ImproperlyConfigured('PRIVATE_BETA_STATE_DIR 必须为绝对路径。')
    state_dir = state_dir.resolve()
    if frontend_dist:
        public_dist = Path(frontend_dist).resolve()
        if (state_dir.is_relative_to(public_dist)
                or state_dir.is_relative_to(public_dist.parent / 'public')):
            raise ImproperlyConfigured('内测邮件、缓存和凭据目录不能放在前端公开目录中。')
    db_host = values.get('PRIVATE_BETA_DB_HOST', '127.0.0.1')
    if db_host not in ('127.0.0.1', 'localhost', '::1'):
        raise ImproperlyConfigured('本机内测数据库必须使用回环地址。')
    try:
        db_port = int(values.get('PRIVATE_BETA_DB_PORT', '5432'))
    except (TypeError, ValueError):
        raise ImproperlyConfigured('PRIVATE_BETA_DB_PORT 必须是有效端口。') from None
    if not 1 <= db_port <= 65535:
        raise ImproperlyConfigured('PRIVATE_BETA_DB_PORT 必须是有效端口。')
    return {
        'origin': origin, 'hostname': parsed.hostname,
        'username': username, 'password': password, 'secret_key': secret_key,
        'db_name': db_name, 'db_user': required('PRIVATE_BETA_DB_USER'),
        'db_password': required('PRIVATE_BETA_DB_PASSWORD'), 'db_host': db_host,
        'db_port': str(db_port), 'state_dir': state_dir,
    }


class PrivateBetaGateMiddleware:
    """邀请口令只控制入站；各业务 API 仍要求其原有登录和操作权限。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 在读入口凭据和返回任何页面前，先应用 Django 的精确 Host 校验。
        host = request.get_host()
        authenticated_by_basic = False
        authorization = request.META.get('HTTP_AUTHORIZATION', '')
        if len(authorization) <= 4096:
            scheme, _, credentials = authorization.partition(' ')
            if scheme.lower() == 'basic':
                try:
                    decoded = base64.b64decode(credentials, validate=True).decode('utf-8')
                    username, separator, password = decoded.partition(':')
                    # 不短路：用户名和口令均以常量时间比较。
                    matches_user = hmac.compare_digest(username.encode(), settings.PRIVATE_BETA_USERNAME.encode())
                    matches_password = hmac.compare_digest(password.encode(), settings.PRIVATE_BETA_PASSWORD.encode())
                    authenticated_by_basic = bool(separator) & matches_user & matches_password
                except (binascii.Error, UnicodeDecodeError, ValueError):
                    pass
        binding = gate_cookie_binding(host)
        authenticated_by_cookie = False
        try:
            cookie = request.get_signed_cookie(GATE_COOKIE_NAME, salt=GATE_COOKIE_SALT, max_age=GATE_COOKIE_AGE)
            authenticated_by_cookie = hmac.compare_digest(cookie, binding)
        except (KeyError, signing.BadSignature, ValueError):
            pass
        authenticated = authenticated_by_basic or authenticated_by_cookie
        if not authenticated:
            response = JsonResponse({'code': 'private_beta_gate_required', 'detail': '请输入邀请内测入口账号和口令。'}, status=401)
            response['WWW-Authenticate'] = 'Basic realm="Chuangxiang private beta", charset="UTF-8"'
        elif self._blocked(request):
            response = JsonResponse({'detail': '内测使用分配的测试账号。', 'code': 'private_beta_endpoint_disabled'}, status=404)
        else:
            # Waitress 仅监听回环地址；此头由本机 cloudflared 写入，供现有登录限流区分访客。
            client_ip = request.META.get('HTTP_CF_CONNECTING_IP', '')
            if request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1') and client_ip:
                try:
                    request.META['REMOTE_ADDR'] = str(ipaddress.ip_address(client_ip))
                except ValueError:
                    pass
            response = self.get_response(request)
        if authenticated_by_basic and not authenticated_by_cookie:
            # 首次导航认证后，浏览器的同源 API 与懒加载资源可用 cookie 继续入站。
            # 这不是用户会话；各业务接口继续执行原有 Session + CSRF + 权限校验。
            response.set_signed_cookie(GATE_COOKIE_NAME, binding, salt=GATE_COOKIE_SALT,
                                       max_age=GATE_COOKIE_AGE, secure=True, httponly=True,
                                       samesite='Lax', path='/')
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @staticmethod
    def _blocked(request):
        route = request.path.rstrip('/').lower()
        if route == '/admin' or route.startswith('/admin/') or route == '/accounts' or route.startswith('/accounts/'):
            return True
        if route in {
            '/api/auth/browser/v1/auth/signup',
            '/api/auth/browser/v1/auth/password/request',
            '/api/auth/browser/v1/auth/password/reset',
            '/api/auth/browser/v1/auth/email/verify',
        }:
            return True
        return route == '/api/auth/browser/v1/account/email' and request.method != 'GET'


class LocalBetaAdminMiddleware:
    """独立本机后台不接受隧道请求或代理身份头。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.get_host()
        if (request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1')
                or request.META.get('HTTP_CF_CONNECTING_IP')
                or request.META.get('HTTP_CF_RAY')
                or request.META.get('HTTP_FORWARDED')
                or request.META.get('HTTP_X_FORWARDED_FOR')
                or request.META.get('HTTP_X_FORWARDED_HOST')
                or request.META.get('HTTP_X_FORWARDED_PROTO')):
            return HttpResponse('此后台仅供本机使用。', status=403)
        if request.path.startswith('/static/') and request.method in ('GET', 'HEAD'):
            from django.contrib.staticfiles.views import serve as serve_static
            response = serve_static(request, request.path.removeprefix('/static/'), insecure=True)
        else:
            response = self.get_response(request)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Cache-Control'] = 'private, no-store'
        return response


def configure_local_admin(port):
    """仅影响本进程；公网内测进程始终使用原有入口和 HTTPS cookie。"""
    if not getattr(settings, 'PRIVATE_BETA', False):
        raise ImproperlyConfigured('本机内测后台只可在 private_beta_settings 下启动。')
    settings.ROOT_URLCONF = 'config.urls'
    settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
    settings.MIDDLEWARE = ['config.private_beta.LocalBetaAdminMiddleware', *(
        middleware for middleware in settings.MIDDLEWARE
        if middleware != 'config.private_beta.PrivateBetaGateMiddleware'
    )]
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_PROXY_SSL_HEADER = None
    settings.SESSION_COOKIE_SECURE = settings.CSRF_COOKIE_SECURE = False
    settings.SESSION_COOKIE_NAME = 'beta_admin_sessionid'
    settings.CSRF_COOKIE_NAME = 'beta_admin_csrftoken'
    settings.CSRF_TRUSTED_ORIGINS = [f'http://127.0.0.1:{port}', f'http://localhost:{port}']
    settings.PUBLIC_ORIGIN = f'http://127.0.0.1:{port}'


def run_beta_maintenance_once():
    """每轮重新核验实际数据库，复用现有组队期限结算，不碰开发库。"""
    try:
        close_old_connections()
        expected = str(settings.DATABASES.get('default', {}).get('NAME', ''))
        if (getattr(settings, 'PRIVATE_BETA', False) is not True
                or not re.fullmatch(r'chuangxiang_beta_[a-z0-9_]{1,40}', expected)
                or connection.vendor != 'postgresql'):
            raise ImproperlyConfigured('组队自动维护仅可在独立 PostgreSQL 内测库运行。')
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            actual = cursor.fetchone()[0]
        if actual != expected:
            raise ImproperlyConfigured('内测自动维护的数据库身份不符。')
        # 管理命令输出仅为本轮状态说明；不积累到页面、共享日志或响应中。
        call_command('settle_team_deadlines', stdout=StringIO(), stderr=StringIO())
    finally:
        # Django 连接按线程保存；只关闭本维护线程的连接，不影响网页请求。
        connection.close()


def wait_for_beta_database(*, timeout=120):
    """启动时等待 PostgreSQL 完成恢复；实际数据库就绪后才开放 HTTP 端口。"""
    expected = str(settings.DATABASES.get('default', {}).get('NAME', ''))
    if (getattr(settings, 'PRIVATE_BETA', False) is not True
            or not re.fullmatch(r'chuangxiang_beta_[a-z0-9_]{1,40}', expected)
            or connection.vendor != 'postgresql'):
        raise ImproperlyConfigured('内测启动检查仅允许独立 PostgreSQL 内测库。')
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() >= deadline:
            raise ImproperlyConfigured('等待内测数据库就绪超时，服务未启动；请确认 PostgreSQL 已启动或完成恢复。')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database()')
                actual = cursor.fetchone()[0]
            if actual != expected:
                raise ImproperlyConfigured('实际连接的数据库与内测配置不一致，服务未启动。')
            return
        except (InterfaceError, OperationalError):
            # Crash recovery can outlast pg_ctl's initial wait. Never log the driver
            # exception: it can contain host, user or other private connection data.
            pass
        except ImproperlyConfigured:
            raise
        except Exception:
            raise ImproperlyConfigured('内测数据库检查失败，服务未启动；请核对本机配置。') from None
        finally:
            # This is the startup thread's connection, not an HTTP/maintenance connection.
            connection.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ImproperlyConfigured('等待内测数据库就绪超时，服务未启动；请确认 PostgreSQL 已启动或完成恢复。') from None
        time.sleep(min(2, remaining))


def beta_maintenance_loop(stop_event):
    while not stop_event.is_set():
        try:
            run_beta_maintenance_once()
        except Exception:
            # 不记录异常原文和 traceback，防止连接参数或私有状态进入日志。
            logging.getLogger(__name__).warning('内测组队状态自动维护失败，将在下一轮重试。')
        if stop_event.wait(60):
            break


def start_beta_maintenance(*, local_admin=False):
    if local_admin or getattr(settings, 'PRIVATE_BETA', False) is not True:
        return None
    stop_event = threading.Event()
    worker = threading.Thread(target=beta_maintenance_loop, args=(stop_event,),
                              name='private-beta-team-maintenance', daemon=True)
    worker.start()
    return stop_event, worker


@require_safe
def private_beta_status(request):
    return JsonResponse({
        'private_beta': True, 'registration_enabled': False,
        'mail_delivery': 'local-test-files', 'test_accounts_only': True,
        'message': '邀请内测：请使用分配的测试账号；数据仅用于本轮测试。',
    })


@require_safe
def frontend(request, path=''):
    """只提供编译后的公开资源；未知文件和后端路径不会退回首页。"""
    dist = Path(settings.PRIVATE_BETA_FRONTEND_DIST).resolve()
    parts = path.split('/')
    if ('\\' in path or ':' in path or any(part.startswith('.') for part in parts)
            or any(ord(char) < 32 for char in path)):
        raise Http404
    target = (dist / path).resolve()
    if not target.is_relative_to(dist):
        raise Http404
    if path and target.is_file():
        allowed_extensions = {'.js', '.css', '.woff', '.woff2', '.ttf', '.otf', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ico', '.avif'}
        if target.suffix.lower() not in allowed_extensions and path != 'index.html':
            raise Http404
        content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        # Windows 的注册表可能把 JavaScript 配成 text/plain，模块脚本必须显式 MIME。
        if target.suffix == '.js':
            content_type = 'text/javascript'
        return FileResponse(target.open('rb'), content_type=content_type)
    reserved = {'api', 'admin', 'accounts', 'assets', 'fonts', 'static', 'media', 'mail', 'cache', 'backend'}
    index = (dist / 'index.html').resolve()
    if (parts[0].lower() in reserved or '.' in parts[-1]
            or not index.is_relative_to(dist) or not index.is_file()):
        raise Http404
    return FileResponse(index.open('rb'), content_type='text/html; charset=utf-8')


def main():
    parser = argparse.ArgumentParser(description='启动仅监听本机的邀请内测服务。')
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--local-admin', action='store_true', help='独立启动仅供本机管理员使用的后台。')
    args = parser.parse_args()
    if args.env_file:
        os.environ['PRIVATE_BETA_ENV_FILE'] = str(args.env_file.resolve())
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.private_beta_settings'
    from django.core.wsgi import get_wsgi_application
    from waitress import serve
    if args.local_admin:
        configure_local_admin(args.port)
    application = get_wsgi_application()
    if not args.local_admin and not (Path(settings.PRIVATE_BETA_FRONTEND_DIST) / 'index.html').is_file():
        parser.error('请先在 frontend 执行 npm run build，生成 dist/index.html。')
    try:
        wait_for_beta_database()
    except ImproperlyConfigured as error:
        parser.exit(1, f'{error}\n')
    proxy_options = {} if args.local_admin else {
        'trusted_proxy': '127.0.0.1', 'trusted_proxy_headers': {'x-forwarded-proto'},
    }
    maintenance = start_beta_maintenance(local_admin=args.local_admin)
    try:
        serve(application, host='127.0.0.1', port=args.port, threads=4,
              clear_untrusted_proxy_headers=True, max_request_body_size=1_048_576,
              expose_tracebacks=False, **proxy_options)
    finally:
        if maintenance:
            maintenance[0].set()


if __name__ == '__main__':
    main()
