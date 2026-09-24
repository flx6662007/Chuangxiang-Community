"""模型阶段的独立测试配置：只使用临时内存库，不读写本地 PostgreSQL。"""

import os

# 即使开发机还没有 .env，也可运行离线模型测试。
for key, value in {
    'DJANGO_SECRET_KEY': 'isolated-model-tests-only-not-for-deployment',
    'DB_NAME': 'unused', 'DB_USER': 'unused', 'DB_PASSWORD': 'unused',
}.items():
    os.environ.setdefault(key, value)

from .settings import *  # noqa: E402,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
# 初始迁移尚未交付；测试运行器仅根据当前模型同步临时表。
MIGRATION_MODULES = dict.fromkeys(('admin', 'auth', 'contenttypes', 'sessions', 'accounts', 'competitions'))
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
