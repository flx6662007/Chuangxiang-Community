from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from governance.models import AdminAction

from .admin import CompetitionAdmin, CompetitionSourceAdmin
from .models import Competition, CompetitionSource, CompetitionTaxonomy
from .services import publish_competition, save_competition, save_source, verify_source, withdraw_competition


class CompetitionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(email='editor@tongji.edu.cn', password='test-password')
        cls.category = CompetitionTaxonomy.objects.create(code='engineering', kind='category', name='工程')
        cls.tag = CompetitionTaxonomy.objects.create(code='python', kind='tag', name='Python')

    def draft(self, code='demo'):
        return save_competition(Competition(
            code=code, title='虚构赛事', edition='2026', summary='虚构简介', description='虚构详情',
            category=self.category, participation_type='team',
        ), actor=self.actor, tags=[self.tag])

    def source(self, competition, verified=True, **kwargs):
        values = dict(competition=competition, source_type='official', source_name='演示原文',
                      source_url='https://example.org/notice', is_primary=True)
        values.update(kwargs)
        return save_source(CompetitionSource(**values), actor=self.actor, verified=verified)

    def published(self):
        competition = self.draft()
        self.source(competition)
        return publish_competition(competition.pk, actor=self.actor)

    def test_publish_requires_verified_source_and_rolls_back_on_failure(self):
        competition = self.draft()
        source = self.source(competition, verified=False)
        with self.assertRaises(ValidationError):
            publish_competition(competition.pk, actor=self.actor)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'draft')
        self.assertIsNone(competition.published_at)
        self.assertFalse(AdminAction.objects.filter(action='publish').exists())
        verify_source(source.pk, actor=self.actor)
        published = publish_competition(competition.pk, actor=self.actor)
        self.assertEqual(published.publication_status, 'published')
        self.assertTrue(AdminAction.objects.filter(action='publish', competition=published).exists())

    def test_permission_checks_reject_nonstaff_and_missing_model_permission(self):
        competition = self.draft()
        for staff in (False, True):
            user = get_user_model().objects.create_user(email=f'user-{staff}@tongji.edu.cn', is_staff=staff)
            with self.assertRaises(PermissionDenied):
                publish_competition(competition.pk, actor=user)
        user.user_permissions.add(Permission.objects.get(codename='change_competition'))
        user = get_user_model().objects.get(pk=user.pk)
        self.source(competition)
        self.assertEqual(publish_competition(competition.pk, actor=user).publication_status, 'published')

    def test_first_publication_survives_withdraw_and_republish(self):
        competition = self.published()
        first = competition.published_at
        competition = withdraw_competition(competition.pk, actor=self.actor, reason='原文调整，待复核')
        self.assertFalse(competition.recruitment_enabled)
        competition = publish_competition(competition.pk, actor=self.actor)
        self.assertEqual(competition.published_at, first)
        self.assertEqual(competition.withdrawal_reason, '原文调整，待复核')

    def test_withdraw_requires_reason_and_published_state(self):
        draft = self.draft()
        with self.assertRaises(ValidationError):
            withdraw_competition(draft.pk, actor=self.actor, reason='弃用')
        self.source(draft)
        published = publish_competition(draft.pk, actor=self.actor)
        with self.assertRaises(ValidationError):
            withdraw_competition(published.pk, actor=self.actor, reason='  ')

    def test_noop_or_verification_does_not_change_content_time(self):
        competition = self.published()
        before = competition.updated_at
        self.assertEqual(save_competition(competition, actor=self.actor, tags=[self.tag]).updated_at, before)
        self.assertEqual(publish_competition(competition.pk, actor=self.actor).updated_at, before)
        verify_source(competition.sources.get().pk, actor=self.actor)
        competition.refresh_from_db()
        self.assertEqual(competition.updated_at, before)

    def test_public_content_and_tag_edit_touch_content_time(self):
        competition = self.published()
        before = competition.updated_at
        first = competition.published_at
        competition.summary = '更新后的虚构简介'
        competition = save_competition(competition, actor=self.actor, tags=[])
        self.assertGreater(competition.updated_at, before)
        self.assertEqual(competition.published_at, first)
        self.assertFalse(competition.tags.exists())
        self.assertEqual(competition.updated_by, self.actor)

    def test_invalid_tag_or_category_rejected_without_partial_save(self):
        competition = self.draft()
        competition.summary = '不应保存'
        with self.assertRaises(ValidationError):
            save_competition(competition, actor=self.actor, tags=[self.category])
        competition.refresh_from_db()
        self.assertEqual(competition.summary, '虚构简介')
        competition.category = self.tag
        with self.assertRaises(ValidationError):
            save_competition(competition, actor=self.actor)

    def test_content_entry_cannot_directly_publish_or_forge_verification(self):
        competition = self.draft()
        competition.publication_status = 'published'
        competition.last_verified_at = timezone.now()
        with self.assertRaises(ValidationError):
            save_competition(competition, actor=self.actor)

    def test_source_edits_reverify_and_touch_parent_but_cannot_edit_public_source(self):
        competition = self.draft()
        source = self.source(competition)
        competition.refresh_from_db()
        before = competition.updated_at
        source.source_url = 'https://example.org/correction'
        source = save_source(source, actor=self.actor)
        self.assertIsNone(source.last_verified_at)
        competition.refresh_from_db()
        self.assertGreater(competition.updated_at, before)
        verify_source(source.pk, actor=self.actor)
        publish_competition(competition.pk, actor=self.actor)
        source.source_name = '不可直接更改'
        with self.assertRaises(ValidationError):
            save_source(source, actor=self.actor, verified=True)

    def test_primary_source_switch_is_atomic(self):
        competition = self.draft()
        original = self.source(competition)
        replacement = self.source(competition, source_url='https://example.org/replacement')
        original.refresh_from_db()
        self.assertFalse(original.is_primary)
        self.assertEqual(competition.sources.get(is_primary=True), replacement)

    def test_disabled_existing_tags_can_remain_but_not_newly_assigned(self):
        competition = self.draft()
        self.tag.is_active = False
        self.tag.save()
        competition.title = '更正标题'
        self.assertEqual(save_competition(competition, actor=self.actor, tags=[self.tag]).title, '更正标题')
        with self.assertRaises(ValidationError):
            self.draft(code='other')

    def test_admin_disables_delete_and_public_source_changes(self):
        request = RequestFactory().get('/admin/')
        request.user = self.actor
        competition = self.published()
        competition_admin = CompetitionAdmin(Competition, admin.site)
        source_admin = CompetitionSourceAdmin(CompetitionSource, admin.site)
        self.assertFalse(competition_admin.has_delete_permission(request, competition))
        self.assertNotIn('delete_selected', competition_admin.get_actions(request))
        self.assertFalse(source_admin.has_change_permission(request, competition.sources.get()))
        self.assertIn('publication_status', competition_admin.get_readonly_fields(request, competition))
