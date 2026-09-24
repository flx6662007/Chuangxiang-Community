"""后端公共配置；本机密码等配置从环境变量或 backend/.env 读取。"""

import os
from pathlib import Path

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
    'accounts.apps.AccountsConfig',
    'competitions.apps.CompetitionsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# 与数据库负责人定义 accounts.User 后，再添加 AUTH_USER_MODEL 配置。
# accounts 中的 migrate 命令暂时阻止创建默认用户表。

# 接口默认要求登录；游客可读的业务接口实现时需单独声明公开权限。
# 这只是接口默认配置，不代表注册、登录和学校邮箱验证已实现。
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
