"""最小内容管理后台：默认存草稿，来源单独核验，发布/下架走事务。"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import Competition, CompetitionSource, CompetitionTaxonomy
from .services import (
    publish_competition, save_competition, save_source, validate_tags,
    verify_source, withdraw_competition,
)


class CompetitionActionForm(ActionForm):
    withdrawal_reason = forms.CharField(label='下架原因（下架操作必填）', required=False, max_length=500)


class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_tags = self.instance.tags.values_list('pk', flat=True) if self.instance.pk else []
        self.fields['tags'].queryset = CompetitionTaxonomy.objects.filter(
            kind='tag',
        ).filter(Q(is_active=True) | Q(pk__in=current_tags))
        self.fields['category'].queryset = CompetitionTaxonomy.objects.filter(
            kind='category',
        ).filter(Q(is_active=True) | Q(pk=self.instance.category_id))

    def clean_tags(self):
        tags = self.cleaned_data['tags']
        try:
            validate_tags(self.instance, tags)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        return tags


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    form = CompetitionForm
    action_form = CompetitionActionForm
    actions = ('verify_and_publish', 'withdraw_selected')
    list_display = ('title', 'edition', 'publication_status', 'category', 'updated_at')
    list_filter = ('publication_status', 'category', 'participation_type')
    search_fields = ('title', 'code', 'organizer')
    filter_horizontal = ('tags',)
    readonly_fields = (
        'publication_status', 'published_at', 'last_verified_at', 'withdrawal_reason',
        'created_at', 'updated_at', 'created_by', 'updated_by',
    )
    save_on_top = True

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('code',) if obj else ())

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        result = save_competition(obj, actor=request.user, tags=form.cleaned_data.get('tags', []))
        obj.__dict__.update(result.__dict__)

    def save_related(self, request, form, formsets, change):
        # tags 已由统一服务校验并保存；不再执行一个独立的 M2M 写入。
        pass

    @admin.action(description='确认已核验全部内容并发布（或更新核验时间）', permissions=['change'])
    def verify_and_publish(self, request, queryset):
        for pk in queryset.values_list('pk', flat=True):
            try:
                result = publish_competition(pk, actor=request.user)
            except ValidationError as exc:
                self.message_user(request, f'赛事 {pk}：' + '；'.join(exc.messages), messages.ERROR)
            else:
                self.log_change(request, result, '人工确认核验并发布')
                self.message_user(request, f'已核验发布：{result.title}', messages.SUCCESS)

    @admin.action(description='下架所选赛事（先填写上方下架原因）', permissions=['change'])
    def withdraw_selected(self, request, queryset):
        for pk in queryset.values_list('pk', flat=True):
            try:
                result = withdraw_competition(pk, actor=request.user, reason=request.POST.get('withdrawal_reason', ''))
            except ValidationError as exc:
                self.message_user(request, f'赛事 {pk}：' + '；'.join(exc.messages), messages.ERROR)
            else:
                self.log_change(request, result, '下架：' + result.withdrawal_reason)
                self.message_user(request, f'已下架：{result.title}', messages.SUCCESS)


class SourceForm(forms.ModelForm):
    verified = forms.BooleanField(
        label='我已打开原文，确认来源真实且适用于本届赛事', required=False,
        help_text='来源变动会清除旧核验结果；勾选后记录本次人工核验时间。',
    )

    class Meta:
        model = CompetitionSource
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'competition' in self.fields:
            self.fields['competition'].queryset = Competition.objects.exclude(publication_status='published')

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        if self.cleaned_data.get('is_primary'):
            # BooleanField 已校验此值；主来源唯一性须等 save_source 在事务内
            # 取消旧主来源后再校验。其他来源字段和模型 clean 仍照常执行。
            exclude.add('is_primary')
        return exclude


@admin.register(CompetitionSource)
class CompetitionSourceAdmin(admin.ModelAdmin):
    form = SourceForm
    list_display = ('source_name', 'competition', 'source_type', 'is_primary', 'last_verified_at')
    list_filter = ('source_type', 'is_primary', 'competition__publication_status')
    search_fields = ('source_name', 'competition__title')
    readonly_fields = ('last_verified_at', 'fetched_at')
    actions = ('mark_verified',)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('competition',) if obj else ())

    def has_add_permission(self, request):
        return super().has_add_permission(request) and request.user.has_perm('competitions.change_competition')

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj) and request.user.has_perm('competitions.change_competition')
        return allowed and (obj is None or obj.competition.publication_status != 'published')

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        result = save_source(obj, actor=request.user, verified=form.cleaned_data['verified'])
        obj.__dict__.update(result.__dict__)

    @admin.action(description='确认已核对原文，标记来源已核验', permissions=['change'])
    def mark_verified(self, request, queryset):
        for pk in queryset.values_list('pk', flat=True):
            try:
                source = verify_source(pk, actor=request.user)
            except ValidationError as exc:
                self.message_user(request, f'来源 {pk}：' + '；'.join(exc.messages), messages.ERROR)
            else:
                self.log_change(request, source, '人工核验来源')
                self.message_user(request, f'已核验：{source.source_name}', messages.SUCCESS)


@admin.register(CompetitionTaxonomy)
class CompetitionTaxonomyAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'kind', 'is_active', 'sort_order')
    list_filter = ('kind', 'is_active')
    search_fields = ('name', 'code')

    def get_readonly_fields(self, request, obj=None):
        return ('code', 'kind') if obj else ()

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        # 名称或排序改变会影响公开卡片；给已关联赛事更新内容时间。
        linked_ids = Competition.objects.filter(Q(category=obj) | Q(tags=obj)).values('pk') if change else []
        linked = list(Competition.objects.select_for_update().filter(pk__in=linked_ids).order_by('pk')) if change else []
        if change:
            CompetitionTaxonomy.objects.select_for_update().get(pk=obj.pk)
        obj.full_clean()
        obj.save()
        if set(form.changed_data) & {'name', 'sort_order'}:
            for competition in linked:
                competition.updated_by = request.user
                competition.save(update_fields=['updated_by', 'updated_at'])
