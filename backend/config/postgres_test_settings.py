"""使用真实迁移的 PostgreSQL 测试配置；只在独立 test_ 数据库运行测试。"""

from .settings import *  # noqa: F403

# 默认由 Django 创建测试库；无 CREATEDB 权限时由管理员预建并使用 --keepdb。
DATABASES['default']['TEST'] = {'NAME': 'test_' + DATABASES['default']['NAME']}  # noqa: F405
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
SECURE_SSL_REDIRECT = False
