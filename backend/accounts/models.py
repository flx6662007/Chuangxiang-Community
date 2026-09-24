"""第一轮用户基础模型；邮箱验证和业务限制随各自功能接入。"""

import secrets
import string

from django.contrib.auth.hashers import identify_hasher, is_password_usable
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, router, transaction
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from .managers import UserManager
from .validators import (
    validate_phone_number,
    validate_public_code,
    validate_school_email,
    validate_wechat_id,
)


def generate_public_code():
    alphabet = string.ascii_uppercase + string.digits
    return 'CX-' + ''.join(secrets.choice(alphabet) for _ in range(8))


class User(AbstractUser):
    username = None
    first_name = None
    last_name = None

    email = models.EmailField('学校邮箱', max_length=254, unique=True,
                              validators=[validate_school_email])
    public_code = models.CharField(
        '系统代号', max_length=11, unique=True, editable=False,
        default=generate_public_code, validators=[validate_public_code],
    )
    wechat_id = models.CharField(
        '微信号', max_length=64, blank=True, default='', validators=[validate_wechat_id],
    )
    phone_number = models.CharField(
        '手机号', max_length=32, blank=True, default='', validators=[validate_phone_number],
    )
    contact_updated_at = models.DateTimeField(
        '联系资料更新时间', null=True, blank=True, editable=False,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        constraints = [
            models.UniqueConstraint(Lower('email'), name='user_email_ci_unique'),
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim('email'))) & ~models.Q(email=''),
                name='user_email_normalized',
            ),
            models.CheckConstraint(
                condition=models.Q(email__regex=r'^[^@\s]+@tongji\.edu\.cn$'),
                name='user_email_school_domain',
            ),
            models.CheckConstraint(
                condition=models.Q(public_code__regex=r'^CX-[A-Z0-9]{8}$'),
                name='user_public_code_format',
            ),
        ]

    def __str__(self):
        return self.public_code

    def get_full_name(self):
        return self.public_code

    def get_short_name(self):
        return self.public_code

    @property
    def has_contact_details(self):
        return bool((self.wechat_id or '').strip() or (self.phone_number or '').strip())

    def _normalize_fields(self):
        self.email = UserManager.normalize_email(self.email)
        for field in ('wechat_id', 'phone_number'):
            value = getattr(self, field)
            if isinstance(value, str):
                setattr(self, field, value.strip())

    def clean_fields(self, exclude=None):
        self._normalize_fields()
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self._normalize_fields()
        if self.password and is_password_usable(self.password):
            try:
                identify_hasher(self.password)
            except ValueError as exc:
                raise ValidationError({'password': '请通过 set_password 设置密码。'}) from exc
        if not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).values_list('public_code', flat=True).first()
            if original is not None and original != self.public_code:
                raise ValidationError({'public_code': '系统代号建立后不能修改。'})

    def save(self, *args, **kwargs):
        """规范化、校验、维护联系时间，并在代号唯一冲突时有限重试。"""
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
        self._normalize_fields()
        contacts = {'email', 'wechat_id', 'phone_number'}
        if self._state.adding:
            contact_changed = self.has_contact_details
        else:
            previous = type(self).objects.using(using).get(pk=self.pk)
            contact_changed = any(
                getattr(self, field) != getattr(previous, field)
                for field in contacts
                if update_fields is None or field in update_fields
            )
        if contact_changed:
            self.contact_updated_at = timezone.now()
            if update_fields is not None:
                update_fields.add('contact_updated_at')
                kwargs['update_fields'] = update_fields

        # public_code 的并发冲突交数据库处理；邮箱函数唯一约束仍由 full_clean 检查。
        self.full_clean(validate_unique=False)
        adding = self._state.adding
        for attempt in range(5):
            try:
                with transaction.atomic(using=using):
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if not adding or not type(self).objects.using(using).filter(
                    public_code=self.public_code,
                ).exists() or attempt == 4:
                    raise
                self.public_code = generate_public_code()
