"""用户管理仅允许超级管理员；验证记录不能手工标记成功。"""
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import SchoolUserChangeForm, SchoolUserCreationForm
from .models import User, UserRestriction


@admin.register(User)
class SchoolUserAdmin(UserAdmin):
    form = SchoolUserChangeForm
    add_form = SchoolUserCreationForm
    ordering = ('id',)
    list_display = ('public_code', 'email', 'is_active', 'is_staff')
    search_fields = ('public_code', 'email')
    readonly_fields = ('public_code', 'contact_updated_at', 'last_login', 'date_joined')
    fieldsets = (
        ('账号', {'fields': ('public_code', 'email', 'password')}),
        ('联系资料', {'fields': ('wechat_id', 'phone_number', 'contact_updated_at')}),
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('时间', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = ((None, {'fields': ('email', 'password1', 'password2')}),)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('email',) if obj else ())

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAccountAdmin(admin.ModelAdmin):
    actions = None

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.unregister(EmailAddress)


@admin.register(EmailAddress)
class SchoolEmailAddressAdmin(ReadOnlyAccountAdmin):
    list_display = ('email', 'user', 'primary', 'verified')
    search_fields = ('email', 'user__public_code')


@admin.register(UserRestriction)
class RestrictionAdmin(ReadOnlyAccountAdmin):
    list_display = ('user', 'starts_at', 'expires_at', 'revoked_at')
    search_fields = ('user__public_code',)
