"""离线测试配置：在临时 SQLite 内存库执行迁移，不读写本地 PostgreSQL。"""

import os

# 即使开发机还没有 .env，也可运行离线模型测试。
for key, value in {
    'DJANGO_SECRET_KEY': 'isolated-model-tests-only-not-for-deployment',
    'DB_NAME': 'unused', 'DB_USER': 'unused', 'DB_PASSWORD': 'unused',
    'DJANGO_DEBUG': '1',
}.items():
    os.environ.setdefault(key, value)

from .settings import *  # noqa: E402,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
SECURE_SSL_REDIRECT = False
