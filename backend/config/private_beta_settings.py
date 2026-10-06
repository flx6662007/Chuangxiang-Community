"""本机邀请内测专用配置，必须显式指定独立数据库及 HTTPS 隧道域名。"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values, load_dotenv

from .private_beta import validate_private_beta_environment

_backend_dir = Path(__file__).resolve().parent.parent
_regular_db_name = os.environ.get('DB_NAME') or dotenv_values(_backend_dir / '.env').get('DB_NAME', '')
_env_file = os.environ.get('PRIVATE_BETA_ENV_FILE')
if _env_file:
    _env_path = Path(_env_file)
    if not _env_path.is_absolute() or not _env_path.is_file():
        raise ImproperlyConfigured('PRIVATE_BETA_ENV_FILE 必须指向现有的私有配置文件。')
    load_dotenv(_env_path, override=True)
_frontend_dist = Path(os.environ.get('PRIVATE_BETA_FRONTEND_DIST', str(_backend_dir.parent / 'frontend' / 'dist'))).resolve()
_beta = validate_private_beta_environment(os.environ, regular_db_name=_regular_db_name, frontend_dist=_frontend_dist)

# 公共业务配置照常加载；这里只替换显式提供的内测配置，不继承开发库与调试模式。
os.environ.update({
    'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': _beta['secret_key'],
    'DJANGO_PUBLIC_ORIGIN': _beta['origin'], 'DJANGO_ALLOWED_HOSTS': _beta['hostname'],
    'DJANGO_CSRF_TRUSTED_ORIGINS': _beta['origin'],
    'DB_NAME': _beta['db_name'], 'DB_USER': _beta['db_user'], 'DB_PASSWORD': _beta['db_password'],
    'DB_HOST': _beta['db_host'], 'DB_PORT': _beta['db_port'],
    'EMAIL_USE_TLS': '0', 'EMAIL_USE_SSL': '0',
})

from .settings import *  # noqa: E402,F403

PRIVATE_BETA = True
DEBUG = False
SECRET_KEY = _beta['secret_key']
ALLOWED_HOSTS = [_beta['hostname']]
PUBLIC_ORIGIN = _beta['origin']
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]
PRIVATE_BETA_USERNAME = _beta['username']
PRIVATE_BETA_PASSWORD = _beta['password']
PRIVATE_BETA_STATE_DIR = _beta['state_dir']
PRIVATE_BETA_FRONTEND_DIST = _frontend_dist
ROOT_URLCONF = 'config.private_beta_urls'
MIDDLEWARE = ['config.private_beta.PrivateBetaGateMiddleware', *MIDDLEWARE]  # noqa: F405

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql', 'NAME': _beta['db_name'],
    'USER': _beta['db_user'], 'PASSWORD': _beta['db_password'],
    'HOST': _beta['db_host'], 'PORT': _beta['db_port'],
    'OPTIONS': {'connect_timeout': 5}, 'CONN_MAX_AGE': 0,
}}
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
    'LOCATION': PRIVATE_BETA_STATE_DIR / 'cache',
    'OPTIONS': {'MAX_ENTRIES': 10000},
}}
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = PRIVATE_BETA_STATE_DIR / 'mail'
DEFAULT_FROM_EMAIL = '创享内测 <beta@example.invalid>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_HOST = EMAIL_HOST_USER = EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = EMAIL_USE_SSL = False
REDIS_URL = ''
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 0  # 隧道域名随进程改变，不设置持久 HSTS。
SESSION_COOKIE_NAME = 'beta_sessionid'
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = None
ALLAUTH_TRUSTED_PROXY_COUNT = 0
# Waitress 清理代理头，门口中间件已验证 Cloudflare 客户地址；DRF 不再自行相信 XFF。
REST_FRAMEWORK = {**REST_FRAMEWORK, 'NUM_PROXIES': 0}  # noqa: F405
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576

for _directory in (PRIVATE_BETA_STATE_DIR, EMAIL_FILE_PATH, PRIVATE_BETA_STATE_DIR / 'cache'):
    _directory.mkdir(parents=True, exist_ok=True)
