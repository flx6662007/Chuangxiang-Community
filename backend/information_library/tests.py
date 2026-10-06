"""信息库权限、版本与 AI 数据边界。仅测试数据库，官方域名仅作字符串，无网络请求。"""
from datetime import date, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competition_catalog.models import CatalogBinding, CatalogEntry
from newsletters.models import Newsletter, NewsletterRevision, NewsletterItem
from research.models import ResearchOpportunity

from .retrieval import search_knowledge
from .selectors import (
    KNOWLEDGE_FIELDS, _editorial_rows, admin_records, collect_records, public_text, safe_source_url,
)

urlpatterns = [
    path('admin/information-library/', include('information_library.urls')),
    path('admin/', admin.site.urls),
]


@override_settings(PUBLIC_RESEARCH_ENABLED=True, ROOT_URLCONF='information_library.tests', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LibraryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = CompetitionTaxonomy.objects.create(code='library-test', kind='category', name='信息库测试')
        cls.actor = get_user_model().objects.create_user(email='library-test@tongji.edu.cn', password='test-password', is_staff=True)

    def setUp(self):
        self.editorial_patch = patch('information_library.selectors._editorial_rows', return_value=[])
        self.editorial_patch.start()
        self.addCleanup(self.editorial_patch.stop)

    def permit(self, *codenames):
        self.actor.user_permissions.set(Permission.objects.filter(codename__in=codenames))
        self.actor = get_user_model().objects.get(pk=self.actor.pk)
        self.client.force_login(self.actor)

    def competition(self, code='library-event', status='published', verified=True, **values):
        data = dict(code=code, title='算法设计赛事', edition='2026', summary='面向学生的算法比赛',
                    description='机器人优化任务', organizer='测试主办', category=self.category,
                    participation_type='both', team_size_min=1, team_size_max=3,
                    publication_status=status, last_verified_at=timezone.now(),
                    published_at=timezone.now() if status != 'draft' else None,
                    withdrawal_reason='内部下架记录' if status == 'withdrawn' else '',
                    recruitment_note='内部核验依据不传出')
        data.update(values)
        item = Competition.objects.create(**data)
        CompetitionSource.objects.create(competition=item, source_type='official', source_name='赛事官网',
                                         source_url=f'https://www.aicomp.cn/{code}', is_primary=True,
                                         last_verified_at=timezone.now() if verified else None)
        return item

    @override_settings(COMPETITION_CATALOG_ONLY=True)
    def test_public_retrieval_obeys_catalog_scope(self):
        item = self.competition(code='outside-catalog')
        self.assertFalse(any(row['id'] == f'db-{item.pk}' for row in search_knowledge('算法', kinds=['competition'])))
        entry = CatalogEntry.objects.create(code='2026001', name='算法设计赛事', grade='A', levels='全国',
                                            source_url='https://www.tongji.edu.cn/catalog', is_active=True)
        CatalogBinding.objects.create(entry=entry, competition=item, basis='测试关联')
        self.assertTrue(any(row['id'] == f'db-{item.pk}' for row in search_knowledge('算法', kinds=['competition'])))
        entry.is_active = False
        entry.save(update_fields=['is_active'])
        self.assertFalse(any(row['id'] == f'db-{item.pk}' for row in search_knowledge('算法', kinds=['competition'])))

    def research(self, code='library-research', status='published', **values):
        data = dict(code=code, title='机器人研究机会', summary='科研实践', description='公开研究内容',
                    recruiting_entity='科研团队', official_url='https://cs.tongji.edu.cn/research',
                    publication_status=status, published_at=timezone.now() if status != 'draft' else None,
                    withdrawal_reason='内部下架原因' if status == 'withdrawn' else '',
                    last_verified_at=timezone.now(), verification_note='内部核验说明SECRET',
                    application_email='private-contact@tongji.edu.cn',
                    application_instructions='联系人：内部姓名；电话：13812345678')
        data.update(values)
        return ResearchOpportunity.objects.create(**data)

    def newsletter(self, target=None, status='published', code='library-newsletter'):
        item = Newsletter.objects.create(code=code, created_by=self.actor)
        revision = NewsletterRevision.objects.create(newsletter=item, version=1, title='本期科研快讯',
                    introduction='当期导读', created_by=self.actor, updated_by=self.actor)
        values = dict(revision=revision, position=1, title_snapshot='旧标题快照', summary_snapshot='旧正文快照')
        if isinstance(target, Competition):
            values.update(kind='competition', competition=target, source_updated_at=target.updated_at,
                          source_url=target.sources.get().source_url)
        elif isinstance(target, ResearchOpportunity):
            values.update(kind='research', research=target, source_version=target.content_version,
                          source_url=target.official_url)
        else:
            values.update(kind='activity', title_snapshot='校内讲座', summary_snapshot='公开讲座内容',
                          source_url='https://www.tongji.edu.cn/lecture')
        NewsletterItem.objects.create(**values)
        if status != 'draft':
            revision.status = 'confirmed'
            revision.confirmed_at = timezone.now()
            revision.confirmed_by = self.actor
            revision.save()
            item.current_revision = revision
            item.publication_status = status
            item.published_at = timezone.now()
            item.withdrawal_reason = '内部说明' if status == 'withdrawn' else ''
            item.save()
        return item, revision

    def test_anonymous_and_nonstaff_cannot_open_library(self):
        url = reverse('information_library:index')
        self.assertEqual(self.client.get(url).status_code, 302)
        student = get_user_model().objects.create_user(email='student-library@tongji.edu.cn', password='test-password')
        self.client.force_login(student)
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_staff_without_permission_denied_and_no_permission_is_added(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(reverse('information_library:index')).status_code, 403)
        self.assertFalse(self.actor.user_permissions.exists())

    def test_view_permission_list_detail_and_cross_kind_isolation(self):
        competition, research = self.competition(), self.research()
        self.permit('view_competition')
        response = self.client.get(reverse('information_library:index'))
        self.assertContains(response, competition.title)
        self.assertNotContains(response, research.title)
        self.assertEqual(self.client.get(reverse('information_library:detail', args=['competition', f'db-{competition.pk}'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('information_library:detail', args=['research', f'db-{research.pk}'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('information_library:index'), {'kind': 'research'}).status_code, 403)

    def test_change_permission_also_reads_but_post_is_rejected(self):
        item = self.research()
        self.permit('change_researchopportunity')
        self.assertEqual(self.client.get(reverse('information_library:index')).status_code, 200)
        url = reverse('information_library:detail', args=['research', f'db-{item.pk}'])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.post(reverse('information_library:index')).status_code, 405)

    def test_filter_search_pagination_and_bad_parameters(self):
        for index in range(23):
            self.competition(code=f'library-event-{index}')
        self.competition(code='hidden-draft', status='draft', title='唯一草稿')
        self.permit('view_competition')
        url = reverse('information_library:index')
        response = self.client.get(url)
        self.assertEqual(len(response.context['page_obj']), 20)
        self.assertEqual(len(self.client.get(url, {'page': 2}).context['page_obj']), 4)
        self.assertEqual(self.client.get(url, {'status': 'draft'}).context['page_obj'].paginator.count, 1)
        self.assertContains(self.client.get(url, {'q': '唯一', 'kind': 'competition'}), '唯一草稿')
        self.assertEqual(self.client.get(url, {'q': '无此内容'}).context['page_obj'].paginator.count, 0)
        for params in ({'page': 'x'}, {'page': '0'}, {'page': '1' * 50}, {'q': 'a' * 201},
                       {'kind': 'account'}, {'status': 'secret'}):
            self.assertEqual(self.client.get(url, params).status_code, 400)
        self.assertEqual(self.client.get(url, {'page': 999}).status_code, 404)

    def test_admin_drafts_and_withdrawn_visible_but_not_ai(self):
        public = self.competition()
        draft = self.competition('draft-event', 'draft')
        withdrawn = self.competition('withdrawn-event', 'withdrawn')
        self.permit('view_competition')
        self.assertEqual(len(admin_records(self.actor)), 3)
        self.assertEqual([row['id'] for row in search_knowledge(kinds=['competition'])], [f'db-{public.pk}'])
        for item in (draft, withdrawn):
            self.assertEqual(self.client.get(reverse('information_library:detail', args=['competition', f'db-{item.pk}'])).status_code, 200)

    def test_demo_seed_records_excluded_even_from_admin(self):
        self.competition('demo-old')
        self.competition('legacy-marked', title='【虚构样例】旧赛事')
        self.research('demo-research')
        self.newsletter(code='demo-newsletter')
        self.assertEqual(collect_records(include_unpublished=True), [])
        self.assertEqual(search_knowledge(), [])

    def test_unverified_sources_admin_only_and_no_ai(self):
        item = self.competition(verified=False)
        self.permit('view_competition')
        response = self.client.get(reverse('information_library:detail', args=['competition', f'db-{item.pk}']))
        self.assertContains(response, '待核验来源')
        self.assertContains(response, 'https://www.aicomp.cn/library-event')
        self.assertEqual(search_knowledge(), [])

    def test_unsafe_source_not_rendered_or_retrieved(self):
        item = self.competition()
        CompetitionSource.objects.filter(competition=item).update(source_url='http://127.0.0.1/private')
        self.permit('view_competition')
        response = self.client.get(reverse('information_library:detail', args=['competition', f'db-{item.pk}']))
        self.assertNotContains(response, '127.0.0.1')
        self.assertEqual(search_knowledge(), [])

    def test_private_fields_contacts_and_html_excluded(self):
        self.research(description='<img src=x onerror=alert(1)>公开研究\n邮箱：hidden@tongji.edu.cn\n补充13812345678')
        row = search_knowledge(kinds=['research'])[0]
        self.assertEqual(set(row), set(KNOWLEDGE_FIELDS))
        serialized = json.dumps(row, ensure_ascii=False)
        for private in ('SECRET', 'private-contact', 'hidden@', '13812345678', 'onerror', 'application_', 'created_by', '_maintenance'):
            self.assertNotIn(private, serialized)
        self.assertIn('公开研究', row['text'])

    def test_competition_facts_dates_timezone_and_historical_state(self):
        instant = timezone.now() - timedelta(days=2)
        self.competition(registration_deadline=instant.date(), registration_deadline_at=instant,
                         registration_deadline_timezone='Asia/Shanghai')
        row = search_knowledge()[0]
        self.assertIn('主办方：测试主办', row['text'])
        self.assertIn('届次：2026', row['text'])
        self.assertIn('官方团队人数上限：3', row['text'])
        self.assertEqual(row['dates']['registration_deadline_timezone'], 'Asia/Shanghai')
        self.assertEqual(row['content_status'], 'expired')
        self.assertIsNone(row['source_dates'][0]['published_on'])

    def test_research_needs_review_preserved_without_claiming_current_availability(self):
        self.research(last_verified_at=timezone.now() - timedelta(days=31))
        row = search_knowledge()[0]
        self.assertEqual(row['content_status'], 'needs_review')
        self.assertIn('重新确认', row['status_note'])

    def test_keyword_all_terms_and_limits(self):
        for index in range(3):
            self.competition(f'library-event-{index}')
        self.assertEqual(len(search_knowledge('机器人 算法', limit=2)), 2)
        self.assertEqual(search_knowledge('机器人 不存在'), [])
        for options in ({'query': 'x' * 201}, {'limit': 0}, {'limit': True}, {'limit': 51},
                        {'kinds': 'competition'}, {'kinds': ['account']}, {'kinds': [None]},
                        {'kinds': iter(['competition'])}):
            with self.assertRaises(ValueError):
                search_knowledge(**options)

    def test_newsletter_uses_current_revision_never_draft_or_old_snapshots(self):
        target = self.competition()
        newsletter, revision = self.newsletter(target)
        NewsletterRevision.objects.create(newsletter=newsletter, version=2, title='秘密新草稿',
                    introduction='不可读的新草稿', created_by=self.actor, updated_by=self.actor)
        row = search_knowledge(kinds=['newsletter'])[0]
        self.assertEqual(row['title'], revision.title)
        self.assertIn(target.title, row['text'])
        self.assertNotIn('秘密', json.dumps(row, ensure_ascii=False))
        self.assertNotIn('旧标题快照', row['text'])
        self.assertNotIn('旧正文快照', row['text'])

    def test_new_current_revision_excludes_older_confirmed_content(self):
        newsletter, old = self.newsletter()
        new = NewsletterRevision.objects.create(newsletter=newsletter, version=2, title='新版快讯',
                    created_by=self.actor, updated_by=self.actor)
        NewsletterItem.objects.create(revision=new, position=1, kind='activity', title_snapshot='新讲座',
                    summary_snapshot='新版公开内容', source_url='https://www.tongji.edu.cn/new')
        new.status, new.confirmed_at, new.confirmed_by = 'confirmed', timezone.now(), self.actor
        new.save()
        newsletter.current_revision = new
        newsletter.save()
        row = search_knowledge(kinds=['newsletter'])[0]
        self.assertEqual(row['title'], '新版快讯')
        self.assertNotIn('校内讲座', row['text'])

    def test_withdrawn_reference_removes_issue_from_ai_and_hides_stale_intro(self):
        target = self.research()
        newsletter, revision = self.newsletter(target)
        self.assertEqual(len(search_knowledge(kinds=['newsletter'])), 1)
        target.publication_status, target.withdrawal_reason = 'withdrawn', '已撤下'
        target.save()
        self.assertEqual(search_knowledge(kinds=['newsletter']), [])
        row = collect_records(['newsletter'], include_unpublished=True)[0]
        self.assertEqual(row['content_status'], 'needs_review')
        for value in ('当期导读', '旧标题快照', '旧正文快照', target.title):
            self.assertNotIn(value, row['text'])

    def test_updated_competition_reference_blocks_whole_issue(self):
        target = self.competition()
        self.newsletter(target)
        target.description = '已更正'
        target.save()
        self.assertEqual(search_knowledge(kinds=['newsletter']), [])

    def test_changed_research_version_blocks_whole_issue(self):
        target = self.research()
        self.newsletter(target)
        ResearchOpportunity.objects.filter(pk=target.pk).update(content_version=2)
        self.assertEqual(search_knowledge(kinds=['newsletter']), [])

    def test_draft_and_withdrawn_newsletters_never_in_ai(self):
        self.newsletter(status='draft', code='draft-issue')
        self.newsletter(status='withdrawn', code='withdrawn-issue')
        self.assertEqual(search_knowledge(kinds=['newsletter']), [])
        self.assertEqual(len(collect_records(['newsletter'], include_unpublished=True)), 2)

    def test_newsletter_permission_does_not_expose_private_referenced_draft(self):
        target = self.competition(status='draft', title='私有草稿名称')
        issue, revision = self.newsletter(target)
        self.permit('view_newsletter')
        response = self.client.get(reverse('information_library:detail', args=['newsletter', f'db-{issue.pk}']))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '私有草稿名称')
        self.assertNotContains(response, '旧正文快照')

    def test_no_public_search_route_and_unknown_detail_is_404(self):
        self.assertEqual(self.client.get('/api/v1/information-library/search/').status_code, 404)
        self.permit('view_competition')
        self.assertEqual(self.client.get(reverse('information_library:detail', args=['competition', 'db-999999'])).status_code, 404)


class TextAndEditorialTests(SimpleTestCase):
    def test_safe_urls_reject_credentials_local_examples_and_schemes(self):
        for value in ('javascript:alert(1)', 'data:text/html,x', 'https://user:pass@www.tongji.edu.cn/',
                      'http://127.0.0.1/x', 'http://10.2.3.4/x', 'http://localhost/x',
                      'https://example.com/x', 'https://test.example.org/x', 'https://sub.example.net/x',
                      'https://www.tongji.edu.cn/?token=secret', 'https://www.tongji.edu.cn:9999/x',
                      'https://www.tongji.edu.cn/\nsecret'):
            self.assertEqual(safe_source_url(value), '', value)
        self.assertEqual(safe_source_url('https://www.tongji.edu.cn/info/1.htm#top'), 'https://www.tongji.edu.cn/info/1.htm')

    def test_text_redacts_contact_lines_and_renders_as_plain_text(self):
        self.assertEqual(public_text('<b>研究</b>\n微信：hidden_handle\n邮箱：a@tongji.edu.cn'), '研究')

    def test_real_editorial_content_preserves_missing_dates(self):
        archive = Path(__file__).resolve().parents[2] / 'docs/undergraduate-research/site-before-pause.json'
        with patch('information_library.selectors.EDITORIAL_PATH', archive):
            rows = list(_editorial_rows('research'))
        self.assertEqual(len(rows), 6)
        self.assertEqual(list(_editorial_rows('newsletter')), [])
        for row in rows:
            self.assertIsNone(row['updated_at'])
            self.assertIsNone(row['published_at'])
            self.assertIsNotNone(row['verified_at'])
            self.assertEqual(row['content_status'], 'unconfirmed_availability')
        no_source_date = next(row for row in rows if row['id'] == 'editorial-tongji-li-bing')
        self.assertIsNone(no_source_date['source_dates'][0]['published_on'])

    def test_editorial_hidden_demo_unsafe_and_unverified_not_ai_ready(self):
        data = {'laboratories': [
            {'id': 'demo-one', 'title': '演示', 'sourceUrl': 'https://www.tongji.edu.cn/'},
            {'id': 'draft-one', 'title': '草稿', 'publication_status': 'draft'},
            {'id': 'unsafe-one', 'title': '不安全', 'summary': '正文', 'verifiedOn': '2026-09-26', 'sourceUrl': 'javascript:x'},
            {'id': 'unchecked', 'title': '未核验', 'summary': '正文', 'sourceUrl': 'https://www.tongji.edu.cn/'},
        ]}
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'editorial.json'
            source.write_text(json.dumps(data), encoding='utf-8')
            with patch('information_library.selectors.EDITORIAL_PATH', source):
                rows = list(_editorial_rows('research'))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not row['_ai_ready'] for row in rows))
