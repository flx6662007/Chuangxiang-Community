"""使用学校邮箱的用户创建入口。"""

from asgiref.sync import sync_to_async
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return (email or '').strip().lower()

    def get_by_natural_key(self, email):
        return self.get(email=self.normalize_email(email))

    async def aget_by_natural_key(self, email):
        return await self.aget(email=self.normalize_email(email))

    def _create_user(self, email, password, **extra_fields):
        if not email or not email.strip():
            raise ValueError('学校邮箱不能为空。')
        if 'public_code' in extra_fields:
            raise ValueError('系统代号由系统生成，不能指定。')
        user = self.model(email=self.normalize_email(email), **extra_fields)
        if password is not None:
            validate_password(password, user=user)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields['is_staff'] is not True or extra_fields['is_superuser'] is not True:
            raise ValueError('超级管理员必须同时启用 is_staff 和 is_superuser。')
        if not password:
            raise ValueError('超级管理员必须设置密码。')
        return self._create_user(email, password, **extra_fields)

    async def acreate_user(self, email, password=None, **extra_fields):
        return await sync_to_async(self.create_user)(email, password, **extra_fields)

    async def acreate_superuser(self, email, password=None, **extra_fields):
        return await sync_to_async(self.create_superuser)(email, password, **extra_fields)

    create_user.alters_data = True
    create_superuser.alters_data = True
    acreate_user.alters_data = True
    acreate_superuser.alters_data = True
