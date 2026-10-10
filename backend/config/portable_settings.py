"""Windows 本机评审包专用配置；不加载开发 .env，也不连接 PostgreSQL。"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def _absolute_directory(name):
    value = os.environ.get(name, '')
    if not value or not Path(value).is_absolute():
        raise ImproperlyConfigured(f'{name} 必须由评审启动器提供绝对目录。')
    return Path(value).resolve()


_data_dir = _absolute_directory('PORTABLE_DATA_DIR')
_frontend_dist = _absolute_directory('PORTABLE_FRONTEND_DIST')
if _data_dir.is_relative_to(_frontend_dist) or _frontend_dist.is_relative_to(_data_dir):
    raise ImproperlyConfigured('评审数据目录与前端静态目录必须彼此独立。')
if not (_frontend_dist / 'index.html').is_file():
    raise ImproperlyConfigured('评审包缺少已构建的前端 index.html。')
_secret = os.environ.get('PORTABLE_SECRET_KEY', '')
if len(_secret) < 40 or _secret.startswith('replace-with-'):
    raise ImproperlyConfigured('PORTABLE_SECRET_KEY 必须由启动器首次随机生成并保存在本机。')
try:
    _port = int(os.environ.get('PORTABLE_PORT', '8765'))
except ValueError:
    raise ImproperlyConfigured('PORTABLE_PORT 必须为有效端口。') from None
if not 1024 <= _port <= 65535:
    raise ImproperlyConfigured('PORTABLE_PORT 必须在 1024 至 65535 之间。')
_origin = f'http://127.0.0.1:{_port}'

# python-dotenv 1.2.3 支持此开关；公共配置中的 load_dotenv 不会读取任何文件。
# 公共配置的生产校验针对 HTTPS/PostgreSQL 部署，导入阶段使用其开发分支；
# 下方立即固定本机包全部安全配置，最终 DEBUG 始终为 False。
os.environ.update({
    'PYTHON_DOTENV_DISABLED': '1',
    'DJANGO_DEBUG': '1', 'DJANGO_SECRET_KEY': _secret,
    'DJANGO_PUBLIC_ORIGIN': _origin, 'DJANGO_ALLOWED_HOSTS': '127.0.0.1,localhost',
    'DJANGO_CSRF_TRUSTED_ORIGINS': _origin,
    'DB_NAME': 'portable_unused', 'DB_USER': 'portable_unused',
    'DB_PASSWORD': 'portable_unused', 'DB_HOST': '127.0.0.1', 'DB_PORT': '1',
    'REDIS_URL': '', 'EMAIL_BACKEND': 'django.core.mail.backends.filebased.EmailBackend',
    'EMAIL_HOST': '', 'EMAIL_PORT': '25', 'EMAIL_HOST_USER': '', 'EMAIL_HOST_PASSWORD': '',
    'EMAIL_USE_TLS': '0', 'EMAIL_USE_SSL': '0', 'EMAIL_TIMEOUT': '15',
    'DEFAULT_FROM_EMAIL': '创享评审 <review@example.invalid>',
    'ALLAUTH_TRUSTED_PROXY_COUNT': '0',
    'COMPETITION_CATALOG_ONLY': '1', 'CATALOG_AUTO_PUBLISH': '0', 'CATALOG_PUBLISH_ACTOR_ID': '',
    'AI_ENABLED': '0', 'AI_API_KEY': '', 'AI_BASE_URL': '',
    'AI_SEARXNG_URL': '', 'AI_WEB_PROXY_URL': '',
    'COMPETITION_SEMANTIC_INDEX': '', 'UNIFIED_SEMANTIC_INDEX': '',
    'COMPETITION_EMBEDDING_MODEL_PATH': '',
    'COMPETITION_EMBEDDING_REVISION': '7999e1d3359715c523056ef9478215996d62a620',
    'COMPETITION_SEMANTIC_THRESHOLD': '0.60',
    'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
    'HF_HOME': str(_data_dir / 'model-cache'),
    'PUBLIC_RESEARCH_ENABLED': os.environ.get('PORTABLE_PUBLIC_RESEARCH_ENABLED', '0'),
})
# 模型与索引只从本次评审包读取；缺失时保留已有关键词检索降级。
# 首次构建索引请显式传 --output，因为此时目标 .npz 尚不存在。
if os.environ.get('PORTABLE_PACKAGE_ROOT'):
    _package_root = _absolute_directory('PORTABLE_PACKAGE_ROOT')
    _model = _package_root / 'models' / 'bge-small-zh-v1.5'
    if _model.is_dir() and _model.resolve().is_relative_to(_package_root):
        os.environ['COMPETITION_EMBEDDING_MODEL_PATH'] = str(_model)
        for _variable, _filename in (
            ('COMPETITION_SEMANTIC_INDEX', 'competitions.npz'),
            ('UNIFIED_SEMANTIC_INDEX', 'unified.npz'),
        ):
            _index = _package_root / 'index' / _filename
            if _index.is_file() and _index.resolve().is_relative_to(_package_root):
                os.environ[_variable] = str(_index)
# 只接受启动器从评审包自身 review.env 显式传入的 AI 配置，不继承开发凭据。
for _name, _default in {
    'API_KEY': '', 'BASE_URL': 'https://api.deepseek.com', 'PROXY_URL': '',
    'MODEL': 'deepseek-flash', 'TIMEOUT_SECONDS': '60', 'MAX_OUTPUT_TOKENS': '2048',
}.items():
    os.environ['DEEPSEEK_' + _name] = os.environ.get('PORTABLE_DEEPSEEK_' + _name, _default)

from .settings import *  # noqa: E402,F403

PORTABLE = True
DEBUG = False
os.environ['DJANGO_DEBUG'] = '0'
SECRET_KEY = _secret
PORTABLE_DATA_DIR = _data_dir
PORTABLE_FRONTEND_DIST = _frontend_dist
PORTABLE_PORT = _port
ROOT_URLCONF = 'config.portable_urls'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
PUBLIC_ORIGIN = _origin
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN, f'http://localhost:{_port}']
MIDDLEWARE = ['config.portable.PortableLoopbackMiddleware', *MIDDLEWARE]  # noqa: F405
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3', 'NAME': PORTABLE_DATA_DIR / 'demo.sqlite3',
    'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'},
    'CONN_MAX_AGE': 0,
}}
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
    'LOCATION': PORTABLE_DATA_DIR / 'cache',
}}
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = PORTABLE_DATA_DIR / 'mail'
EMAIL_HOST = EMAIL_HOST_USER = EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = EMAIL_USE_SSL = False
REDIS_URL = ''
STATIC_ROOT = PORTABLE_DATA_DIR / 'staticfiles'
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
SECURE_HSTS_SECONDS = 0
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False
SESSION_COOKIE_NAME = 'portable_sessionid'
# 前端从 csrftoken 读取 CSRF；保留此名称以兼容既有请求拦截器。
CSRF_COOKIE_NAME = 'csrftoken'
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = CSRF_COOKIE_SAMESITE = 'Lax'
ALLAUTH_TRUSTED_PROXY_COUNT = 0
REST_FRAMEWORK = {**REST_FRAMEWORK, 'NUM_PROXIES': 0}  # noqa: F405

for _directory in (PORTABLE_DATA_DIR, EMAIL_FILE_PATH, PORTABLE_DATA_DIR / 'cache'):
    _directory.mkdir(parents=True, exist_ok=True)
