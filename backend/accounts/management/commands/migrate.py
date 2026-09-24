"""Prevent an accidental initial migration before the user model is agreed."""

from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrateCommand


class Command(DjangoMigrateCommand):
    def handle(self, *args, **options):
        if settings.AUTH_USER_MODEL == 'auth.User':
            raise CommandError(
                '用户模型尚未确定，本次没有执行迁移。请先与数据库负责人定义 '
                'accounts.User，设置 AUTH_USER_MODEL，并生成首次迁移。'
            )
        return super().handle(*args, **options)
