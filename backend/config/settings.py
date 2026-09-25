"""后端公共配置；本机密码等配置从环境变量或 backend/.env 读取。"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# BASE_DIR 指向 backend；进程环境变量优先于 .env 中的同名配置。
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def required_environment(name):
    """读取必填配置，拒绝缺失值和配置样例中的占位值。"""
    value = os.getenv(name)
    if not value or value.startswith('replace-with-'):
        raise ImproperlyConfigured(
            f'请在 backend/.env 或环境变量中填写 {name}，不能使用样例占位值。'
            '配置方法见 docs/backend-development.md。'
        )
    return value


# 基础配置。真实密钥不提交到仓库；正式部署时必须关闭 DEBUG。
SECRET_KEY = required_environment('DJANGO_SECRET_KEY')

DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]


# 启用 Django 内置功能、DRF 和本项目业务模块。

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.headless',
    'accounts.apps.AccountsConfig',
    'competitions.apps.CompetitionsConfig',
    'teams.apps.TeamsConfig',
    'research.apps.ResearchConfig',
    'resources.apps.ResourcesConfig',
    'newsletters.apps.NewslettersConfig',
    'favorites.apps.FavoritesConfig',
    'governance.apps.GovernanceConfig',
    'notifications.apps.NotificationsConfig',
    'ingestion.apps.IngestionConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'accounts.middleware.AccountAPIErrorMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# 数据库连接。这里只指定连接方式，不会创建表或导入数据。

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': required_environment('DB_NAME'),
        'USER': required_environment('DB_USER'),
        'PASSWORD': required_environment('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {'connect_timeout': 5},
    }
}

# 第一轮用户字段采用学校邮箱登录；必须在 accounts 的首次迁移中创建。
AUTH_USER_MODEL = 'accounts.User'

# 接口默认要求登录；游客可读的业务接口实现时需单独声明公开权限。
# 游客接口单独放行；发布/申请资格另外检查邮箱与账号限制。
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# Django 密码强度校验规则。

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 界面语言和时间设置。

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True


# Django 静态文件的 URL 前缀。

STATIC_URL = 'static/'

# 未显式指定主键时，使用自动增长的整数主键。

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend',
                           'allauth.account.auth_backends.AuthenticationBackend']
ACCOUNT_ADAPTER = 'accounts.adapters.SchoolAccountAdapter'
HEADLESS_ADAPTER = 'accounts.adapters.SchoolHeadlessAdapter'
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ('browser',)
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_PREVENT_ENUMERATION = False  # 重复注册明确报错，绝不覆盖原账号。
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
ACCOUNT_MAX_EMAIL_ADDRESSES = 1
# allauth 65.19.4 验证码模式要求此值；Adapter 允许未验证账号登录。
# 发布/申请权限仍要求验证，见 accounts.permissions。
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_FORMAT = {'length': 6, 'numeric': True, 'dashed': False}
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = 600
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = 3  # 此版本以整数配置本轮重发次数。
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE = False
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT = 600
ACCOUNT_PASSWORD_RESET_BY_CODE_MAX_ATTEMPTS = 5
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[创享平台] '
ACCOUNT_RATE_LIMITS = {
    'signup': '5/h/ip', 'login': '30/m/ip',
    'login_failed': '5/300s/key,20/300s/ip',
    'confirm_email': '1/60s/key,5/h/key,20/h/ip',
    'reset_password': '1/60s/key,5/h/key,20/h/ip',
}
ACCOUNT_SESSION_REMEMBER = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'accounts.views.csrf_failure'
PUBLIC_ORIGIN = os.getenv('DJANGO_PUBLIC_ORIGIN', 'http://localhost:5173' if DEBUG else '').rstrip('/')
HEADLESS_FRONTEND_URLS = {
    'account_signup': PUBLIC_ORIGIN + '/account',
    'account_confirm_email': PUBLIC_ORIGIN + '/account',
    'account_reset_password_from_key': PUBLIC_ORIGIN + '/account',
}
default_csrf_origins = 'http://localhost:5173,http://127.0.0.1:5173' if DEBUG else PUBLIC_ORIGIN
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', default_csrf_origins).split(',') if v.strip()]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '15'))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '创享平台 <noreply@example.org>' if DEBUG else '')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured('EMAIL_USE_TLS 和 EMAIL_USE_SSL 只能启用一项。')
REDIS_URL = os.getenv('REDIS_URL', '')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}} if REDIS_URL else {
    'default': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache', 'LOCATION': BASE_DIR / '.local' / 'cache'}
}
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', '0' if DEBUG else '1') == '1'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
ALLAUTH_TRUSTED_PROXY_COUNT = int(os.getenv('ALLAUTH_TRUSTED_PROXY_COUNT', '0'))
if not DEBUG:
    origin = urlsplit(PUBLIC_ORIGIN)
    if origin.scheme != 'https' or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
        raise ImproperlyConfigured('正式环境须配置 HTTPS 的 DJANGO_PUBLIC_ORIGIN（不含路径）。')
    if '*' in ALLOWED_HOSTS or not ALLOWED_HOSTS or origin.hostname not in ALLOWED_HOSTS:
        raise ImproperlyConfigured('正式环境须将实际域名填写到 DJANGO_ALLOWED_HOSTS。')
    if not REDIS_URL:
        raise ImproperlyConfigured('正式环境须配置 REDIS_URL，共享验证码及登录限流缓存。')
    if EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend' or not all((EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL)):
        raise ImproperlyConfigured('正式环境须填写 SMTP 配置；不能使用终端邮件后端冒充真实发信。')
    if not (EMAIL_USE_TLS or EMAIL_USE_SSL):
        raise ImproperlyConfigured('正式 SMTP 必须启用 TLS 或 SSL。')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# AI 默认关闭；仅在主动调用 AI 服务时检查密钥、地址和模型配置。
AI_SERVICES = {
    'ENABLED': os.getenv('AI_ENABLED', '0') == '1',
    'PROVIDER': os.getenv('AI_PROVIDER', 'qwen'),
    'BASE_URL': os.getenv('AI_BASE_URL', ''),
    'API_KEY': os.getenv('AI_API_KEY', ''),
    'MODEL': os.getenv('AI_MODEL', ''),
    'TIMEOUT_SECONDS': os.getenv('AI_TIMEOUT_SECONDS', '30'),
    'MAX_OUTPUT_TOKENS': os.getenv('AI_MAX_OUTPUT_TOKENS', '2048'),
}
