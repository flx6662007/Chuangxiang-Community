"""Serve the built Vue app with the local Django/database configuration."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Load the development database without applying production-only HTTPS checks.
os.environ['DJANGO_DEBUG'] = '1'
from .settings import *  # noqa: E402,F403

try:
    LOCAL_PREVIEW_PORT = int(os.environ.get('LOCAL_PREVIEW_PORT', '8000'))
except ValueError:
    raise ImproperlyConfigured('LOCAL_PREVIEW_PORT 必须是有效端口。') from None
if not 1024 <= LOCAL_PREVIEW_PORT <= 65535:
    raise ImproperlyConfigured('LOCAL_PREVIEW_PORT 必须在 1024 至 65535 之间。')

PORTABLE_FRONTEND_DIST = (Path(__file__).resolve().parents[2] / 'frontend' / 'dist').resolve()
if not (PORTABLE_FRONTEND_DIST / 'index.html').is_file():
    raise ImproperlyConfigured('缺少 frontend/dist/index.html；请先在 frontend/ 执行 npm run build。')

ROOT_URLCONF = 'config.local_preview_urls'
MIDDLEWARE = ['config.portable.PortableLoopbackMiddleware', *MIDDLEWARE]  # noqa: F405
DEBUG = False
os.environ['DJANGO_DEBUG'] = '0'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
PUBLIC_ORIGIN = f'http://127.0.0.1:{LOCAL_PREVIEW_PORT}'
HEADLESS_FRONTEND_URLS = {
    key: PUBLIC_ORIGIN + '/account' for key in HEADLESS_FRONTEND_URLS  # noqa: F405
}
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN, f'http://localhost:{LOCAL_PREVIEW_PORT}']
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
