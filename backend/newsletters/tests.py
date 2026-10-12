import copy
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone

from competitions.models import Competition
from resources.models import Resource, ResourceRevision
from .models import Newsletter, NewsletterRevision, NewsletterItem
from .importer import load_package, import_issue, plan_import
from .presentation import public_link

urlpatterns = [path('editorial/', include('information_library.public_urls'))]


@override_settings(ROOT_URLCONF=__name__, COMPETITION_CATALOG_ONLY=False)
class NewsletterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser(email='news-editor@tongji.edu.cn', password='tests-only')

    def setUp(self):
        self.data = load_package()

    def publish(self):
        issue, _ = import_issue(self.data, actor=self.actor, publish=True)
        return issue

    def detail(self, issue):
        return self.client.get(f'/editorial/newsletters/{issue.code}/')

    def test_default_command_is_read_only_and_publish_requires_write(self):
        output = StringIO()
        call_command('import_newsletter', stdout=output)
        self.assertIn('仅预览', output.getvalue())
        self.assertEqual(Newsletter.objects.count(), 0)
        self.assertEqual(Resource.objects.count(), 0)
        self.assertEqual(Competition.objects.count(), 0)
        with self.assertRaises(CommandError):
            call_command('import_newsletter', publish=True, stdout=StringIO())

    def test_draft_then_publish_and_repeat_do_not_duplicate(self):
        call_command('import_newsletter', write=True, actor_id=self.actor.pk, stdout=StringIO())
        issue = Newsletter.objects.get(code=self.data['code'])
        self.assertEqual(self.detail(issue).status_code, 404)
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)
        call_command('import_newsletter', write=True, publish=True, actor_id=self.actor.pk, stdout=StringIO())
        issue.refresh_from_db()
        first_time = issue.published_at
        self.assertEqual(Newsletter.objects.count(), 1)
        self.assertEqual(NewsletterRevision.objects.count(), 1)
        self.assertEqual(NewsletterItem.objects.count(), 8)
        self.assertEqual(Resource.objects.count(), 6)
        self.assertEqual(Competition.objects.count(), 2)
        revisions = ResourceRevision.objects.count()
        call_command('import_newsletter', write=True, publish=True, actor_id=self.actor.pk, stdout=StringIO())
        issue.refresh_from_db()
        self.assertEqual(issue.published_at, first_time)
        self.assertEqual(ResourceRevision.objects.count(), revisions)
        self.assertEqual(NewsletterItem.objects.count(), 8)

    def test_complete_public_detail_snapshot_grouping_dates_and_sources(self):
        issue = self.publish()
        response = self.detail(issue)
        self.assertEqual(response.status_code, 200)
        detail = response.json()
        self.assertEqual(detail['code'], 'newsletter-2026-10')
        self.assertEqual(detail['title'], '创享快讯 · 2026年10月')
        self.assertEqual(detail['sourcePublishedOn'], '2026-10-10')
        self.assertEqual(detail['publishedAt'], issue.published_at.isoformat())
        self.assertEqual(detail['credits'], '创享编辑部')
        self.assertEqual([len(s['groups']) for s in detail['sections']], [2, 5])
        self.assertEqual(len(detail['sections'][1]['groups'][3]['items']), 2)
        self.assertIn('#/ict-contest?compId=', detail['sections'][0]['groups'][1]['items'][0]['sourceUrl'])
        self.assertNotIn('项目招募', response.content.decode())
        self.assertNotIn('confirmed_by', response.content.decode())
        card = self.client.get('/editorial/newsletters/').json()['results'][0]
        self.assertEqual(card['title'], detail['title'])
        self.assertEqual(card['detailUrl'], '/newsletters/newsletter-2026-10')
        self.assertEqual(card['sourceUrl'], '')
        self.assertEqual(card['detailUrl'], '/newsletters/' + issue.code)
        self.assertLessEqual(len(card['summary']), 180)
        self.assertNotIn('报名截止', card['summary'])
        self.assertEqual(self.client.post(f'/editorial/newsletters/{issue.code}/').status_code, 405)

    def test_resource_update_preserves_snapshot_but_withdrawal_hides_content(self):
        issue = self.publish()
        row = Resource.objects.get(code='ollama')
        Resource.objects.filter(pk=row.pk).update(title='新版名称', description='新正文', content_version=3)
        detail = self.detail(issue).json()
        entry = detail['sections'][1]['groups'][-1]['items'][0]
        self.assertEqual(entry['title'], 'Ollama')
        self.assertTrue(entry['sourceChanged'])
        self.assertNotIn('新正文', entry['body'])
        Resource.objects.filter(pk=row.pk).update(publication_status='withdrawn', withdrawal_reason='内部原因')
        response = self.detail(issue)
        self.assertNotIn('Ollama', response.content.decode())
        self.assertNotIn('内部原因', response.content.decode())
        self.assertTrue(response.json()['hasHiddenItems'])
        self.assertEqual(response.json()['introduction'], '')

    def test_inactive_resource_and_draft_references_never_leak(self):
        issue = self.publish()
        Resource.objects.update(availability='unavailable')
        Competition.objects.update(publication_status='draft', published_at=None)
        detail = self.detail(issue).json()
        self.assertEqual(detail['sections'], [])
        self.assertEqual(detail['introduction'], '')
        self.assertEqual(self.client.get('/editorial/newsletters/').json()['count'], 0)
        issue.publication_status = 'withdrawn'
        issue.withdrawal_reason = '内部原因'
        issue.save()
        self.assertEqual(self.detail(issue).status_code, 404)

    def test_draft_new_revision_and_wrong_owner_do_not_leak(self):
        issue = self.publish()
        draft = NewsletterRevision.objects.create(newsletter=issue, version=2, title='私人草稿',
            introduction='私人内容', created_by=self.actor, updated_by=self.actor)
        self.assertNotIn('私人', self.detail(issue).content.decode())
        other = Newsletter.objects.create(code='other-issue', created_by=self.actor)
        Newsletter.objects.filter(pk=other.pk).update(publication_status='published', published_at=timezone.now(),
                                                    current_revision=issue.current_revision)
        self.assertEqual(self.detail(other).status_code, 404)
        self.assertEqual(self.client.get('/editorial/newsletters/missing/').status_code, 404)
        with self.assertRaises(ValidationError):
            import_issue(self.data, actor=self.actor, publish=True)

    def test_unsafe_or_changed_source_is_not_clickable(self):
        issue = self.publish()
        for url in ('javascript:alert(1)', 'http://127.0.0.1/secret', 'https://github.com/?token=secret',
                    'https://github.com/#/page?access_token=secret', 'https://github.com/#access_token=secret'):
            self.assertEqual(public_link(url), '')
        Resource.objects.filter(code='ollama').update(access_url='https://ollama.com/', content_version=3)
        entry = self.detail(issue).json()['sections'][1]['groups'][-1]['items'][0]
        self.assertEqual(entry['sourceUrl'], '')
        self.assertTrue(entry['sourceChanged'])

    def test_package_conflict_permissions_and_rollback(self):
        regular = get_user_model().objects.create_user(email='reader@tongji.edu.cn', password='tests-only')
        with self.assertRaises(CommandError):
            call_command('import_newsletter', write=True, actor_id=regular.pk, stdout=StringIO())
        self.assertFalse(Newsletter.objects.exists())
        # Failure after earlier targets were created still rolls the entire write back.
        bad = copy.deepcopy(self.data)
        bad['items'][-1]['body'] = 'x' * 11000
        with self.assertRaises(ValidationError):
            import_issue(bad, actor=self.actor, publish=True)
        self.assertFalse(Resource.objects.exists())
        self.assertFalse(Competition.objects.exists())
        self.publish()
        changed = copy.deepcopy(self.data)
        changed['credits'] = '不同署名'
        with self.assertRaises(ValidationError):
            import_issue(changed, actor=self.actor, publish=True)
        self.assertEqual(NewsletterRevision.objects.count(), 1)

    def test_existing_public_resources_are_reused_without_mutation(self):
        self.publish()
        data = copy.deepcopy(self.data)
        data['code'] = 'newsletter-reuse-2026-10'
        before = list(Resource.objects.values('id', 'updated_at', 'content_version', 'description'))
        self.assertTrue(all(row['action'] == 'reuse' for row in plan_import(data)['items']))
        import_issue(data, actor=self.actor, publish=True)
        self.assertEqual(before, list(Resource.objects.values('id', 'updated_at', 'content_version', 'description')))
        self.assertEqual(Resource.objects.count(), 6)

    def test_ai_policy_is_not_relaxed_for_public_resource_snapshots(self):
        from information_library.retrieval import search_knowledge
        self.publish()
        self.assertEqual(search_knowledge(kinds=['newsletter']), [])

    @override_settings(COMPETITION_CATALOG_ONLY=True)
    def test_editorial_selection_and_body_search_independent_of_catalog(self):
        issue = self.publish()
        self.assertEqual(len(self.detail(issue).json()['sections'][0]['groups']), 2)
        response = self.client.get('/editorial/newsletters/', {'search': '英文论文'}).json()
        self.assertEqual(response['count'], 1)
        self.assertNotIn('_searchText', response['results'][0])
        Resource.objects.filter(code='ollama').update(publication_status='draft', published_at=None)
        self.assertEqual(self.client.get('/editorial/newsletters/', {'search': 'Ollama'}).json()['count'], 0)

    def test_changed_reference_between_draft_and_publish_is_rejected(self):
        issue, _ = import_issue(self.data, actor=self.actor)
        Resource.objects.filter(code='ollama').update(description='经过其他流程编辑', content_version=2,
            publication_status='published', published_at=timezone.now())
        with self.assertRaisesMessage(ValidationError, '草稿建立后发生变化'):
            import_issue(self.data, actor=self.actor, publish=True)
        issue.refresh_from_db()
        self.assertEqual(issue.publication_status, 'draft')
        self.assertFalse(Competition.objects.filter(publication_status='published').exists())

    def test_newsletter_permission_does_not_grant_resource_creation(self):
        from django.contrib.auth.models import Permission
        from django.core.exceptions import PermissionDenied
        actor = get_user_model().objects.create_user(email='limited-editor@tongji.edu.cn', password='tests-only', is_staff=True)
        actor.user_permissions.set(Permission.objects.filter(content_type__app_label='newsletters'))
        data = copy.deepcopy(self.data)
        data['items'] = data['items'][2:]
        with self.assertRaises(PermissionDenied):
            import_issue(data, actor=actor)
        self.assertFalse(Resource.objects.exists())

    def test_same_edition_alias_is_reused_and_other_edition_is_not(self):
        self.publish()
        target = Competition.objects.get(code='apmcm-2026')
        Competition.objects.filter(pk=target.pk).update(code='existing-apmcm', edition='2026')
        data = copy.deepcopy(self.data)
        data['code'] = 'new-issue-with-alias'
        self.assertEqual(plan_import(data)['items'][0]['targetCode'], 'existing-apmcm')
        Competition.objects.filter(pk=target.pk).update(edition='2025')
        self.assertEqual(plan_import(data)['items'][0]['action'], 'create')
