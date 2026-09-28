from contextlib import nullcontext
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone

from competitions.models import Competition, CompetitionTaxonomy
from competitions.scope import apply_competition_scope
from ingestion.http import FetchError, Page
from .models import CatalogBinding, CatalogEntry, MonitorRun, OfficialNotice, OfficialSite
from .monitor import discover, discover_indexes, parse_page, save_page, sync_site
from .registry import directory, initialize_catalog


BODY = '<p>这是一则关于当年比赛的官方说明。报名资格、队伍人数与具体时间均以正式通知为准。' * 4 + '</p>'


class CatalogRegistryTests(TestCase):
    def short_manifest(self):
        return {
            'version': 2030,
            'source_url': 'https://school.example/catalog',
            'entries': [{
                'code': '2030001', 'name': '测试赛事', 'grade': 'A',
                'levels': '国家级', 'departments': ['测试学院'], 'aliases': [],
                'sites': [{
                    'status': 'verified', 'url': 'https://contest.example/',
                    'evidence_url': 'https://school.example/original-notice',
                    'allowed_hosts': ['contest.example'], 'note': '原始核查说明',
                    'kind': 'competition', 'dedicated': True, 'enabled': True,
                }],
            }],
        }

    def test_complete_directory_including_humanities_and_no_staff_numbers(self):
        data = directory()
        self.assertEqual(len(data['entries']), 255)
        self.assertEqual({r['code'] for r in data['entries']}, {str(2026000 + i) for i in range(1, 256)})
        self.assertEqual({r['grade'] for r in data['entries']}, {'A+', 'A', 'B', 'C'})
        self.assertIn('外国语学院', data['entries'][78]['departments'])
        self.assertEqual(len(data['entries'][67]['departments']), 2)
        for row in data['entries']:
            self.assertNotIn('teacher', row)
            self.assertNotIn('staff_id', row)

    def test_initialization_is_idempotent_and_preserves_manual_pause(self):
        self.assertEqual(initialize_catalog(), 255)
        CatalogEntry.objects.filter(code='2026001').update(is_active=False)
        self.assertEqual(initialize_catalog(), 0)
        self.assertFalse(CatalogEntry.objects.get(code='2026001').is_active)

    def test_reinitialization_updates_source_metadata_but_preserves_manual_pause(self):
        manifest = self.short_manifest()
        with patch('competition_catalog.registry.directory', return_value=manifest):
            self.assertEqual(initialize_catalog(), 1)
            site = OfficialSite.objects.get()
            site.enabled = False
            site.save(update_fields=['enabled'])
            config = manifest['entries'][0]['sites'][0]
            config.update({
                'evidence_url': 'https://school.example/corrected-notice',
                'allowed_hosts': ['contest.example', 'www.contest.example'],
                'note': '核查后补充重定向域名与依据',
                'kind': 'organizer', 'dedicated': False,
            })
            manifest['entries'][0]['aliases'] = ['已核对别名']
            self.assertEqual(initialize_catalog(), 0)
        site.refresh_from_db()
        self.assertFalse(site.enabled)
        self.assertEqual(site.evidence_url, config['evidence_url'])
        self.assertEqual(site.allowed_hosts, config['allowed_hosts'])
        self.assertEqual(site.note, config['note'])
        self.assertEqual(site.kind, 'organizer')
        self.assertFalse(site.dedicated)
        self.assertEqual(site.entry.aliases, ['已核对别名'])
        self.assertEqual(OfficialSite.objects.count(), 1)

    def test_withdrawn_url_is_disabled_without_deleting_notice_history(self):
        manifest = self.short_manifest()
        with patch('competition_catalog.registry.directory', return_value=manifest):
            initialize_catalog()
            old_site = OfficialSite.objects.get()
            old_notice = OfficialNotice.objects.create(
                site=old_site, url='https://contest.example/old-notice',
                title='原始历史通知', body='历史原文保持不变', content_hash='a' * 64,
                source_published_on=date(2020, 1, 1), status='historical',
            )
            first_seen = old_notice.first_seen_at
            manifest['entries'][0]['sites'] = [{
                'status': 'verified', 'url': 'https://correct.example/',
                'evidence_url': 'https://school.example/corrected-notice',
                'allowed_hosts': ['correct.example'], 'note': '已核实的新官网',
            }]
            self.assertEqual(initialize_catalog(), 0)
            self.assertEqual(initialize_catalog(), 0)
        old_site.refresh_from_db()
        old_notice.refresh_from_db()
        self.assertFalse(old_site.enabled)
        self.assertTrue(OfficialSite.objects.get(url='https://correct.example/').enabled)
        self.assertEqual(OfficialSite.objects.count(), 2)
        self.assertEqual(OfficialNotice.objects.count(), 1)
        self.assertEqual(old_notice.site_id, old_site.pk)
        self.assertEqual(old_notice.first_seen_at, first_seen)
        self.assertEqual(old_notice.body, '历史原文保持不变')
        self.assertEqual(old_notice.content_hash, 'a' * 64)

    def test_explicit_manifest_pause_disables_existing_site_and_true_cannot_resume_it(self):
        manifest = self.short_manifest()
        with patch('competition_catalog.registry.directory', return_value=manifest):
            initialize_catalog()
            site = OfficialSite.objects.get()
            self.assertTrue(site.enabled)
            config = manifest['entries'][0]['sites'][0]
            config['enabled'] = False
            initialize_catalog()
            site.refresh_from_db()
            self.assertFalse(site.enabled)
            config['enabled'] = True
            initialize_catalog()
            site.refresh_from_db()
            self.assertFalse(site.enabled)
            del config['enabled']
            initialize_catalog()
            site.refresh_from_db()
            self.assertFalse(site.enabled)

    def test_catalog_corrections_sync_metadata_but_preserve_manual_inactive_state(self):
        manifest = self.short_manifest()
        with patch('competition_catalog.registry.directory', return_value=manifest):
            initialize_catalog()
            entry = CatalogEntry.objects.get()
            entry.is_active = False
            entry.save(update_fields=['is_active'])
            manifest['version'] = 2031
            manifest['source_url'] = 'https://school.example/corrected-catalog'
            manifest['entries'][0].update({
                'name': '修正后的赛事名称', 'grade': 'B', 'levels': '省部级',
                'departments': ['修正学院', '联合学院'], 'aliases': ['旧称'],
            })
            self.assertEqual(initialize_catalog(), 0)
            self.assertEqual(initialize_catalog(), 0)
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)
        self.assertEqual(entry.version, 2031)
        self.assertEqual(entry.name, '修正后的赛事名称')
        self.assertEqual(entry.grade, 'B')
        self.assertEqual(entry.levels, '省部级')
        self.assertEqual(entry.departments, ['修正学院', '联合学院'])
        self.assertEqual(entry.aliases, ['旧称'])
        self.assertEqual(entry.source_url, manifest['source_url'])
        self.assertEqual(CatalogEntry.objects.count(), 1)
        self.assertEqual(OfficialSite.objects.get().entry_id, entry.pk)


class CatalogMonitorTests(TestCase):
    def setUp(self):
        self.entry = CatalogEntry.objects.create(code='2030001', version=2030, name='全国大学生英语竞赛', grade='A',
                                                 levels='国家级', source_url='https://school.example/catalog')
        self.site = OfficialSite.objects.create(entry=self.entry, url='https://contest.example/',
                                               evidence_url='https://school.example/notice',
                                               allowed_hosts=['contest.example'], dedicated=True)

    def html(self, title='2030年全国大学生英语竞赛报名通知', addition=''):
        return f'<html><title>{title}</title><article><h1>{title}</h1>{BODY}{addition}</article><footer>2099年12月31日</footer></html>'

    def test_links_do_not_expand_to_untrusted_sites_or_files(self):
        page = Page(self.site.url, '<a href="/notice/1">报名通知</a><a href="http://127.0.0.1/secret">报名通知</a>'
                                  '<a href="https://evil.example/a">报名通知</a><a href="/notice/a.pdf">竞赛规程</a>')
        self.assertEqual(discover(self.site, page), ['https://contest.example/notice/1'])

    def test_department_homepage_uses_actual_contest_name(self):
        self.site.dedicated = False
        page = Page(self.site.url, '<a href="/other">其他比赛报名通知</a><a href="/right">2030年全国大学生英语竞赛通知</a>')
        self.assertEqual(discover(self.site, page), ['https://contest.example/right'])

    def test_index_discovery_keeps_one_approved_navigation_link(self):
        self.site.dedicated = False
        page = Page(self.site.url, '<a href="/news">新闻动态</a><a href="/notices">通知公告</a>'
                    '<a href="https://evil.example/list">竞赛通知</a>'
                    '<a href="https://user:password@contest.example/private">竞赛通知</a>'
                    '<a href="http://[broken">竞赛通知</a><a href="javascript:alert(1)">竞赛通知</a>')
        self.assertEqual(discover_indexes(self.site, page), ['https://contest.example/notices'])
        self.site.dedicated = True
        self.assertEqual(discover_indexes(self.site, page), [])

    def test_malformed_competition_link_does_not_hide_valid_link(self):
        page = Page(self.site.url, '<a href="http://[broken">报名通知</a>'
                    '<a href="https://contest.example:bad/n">报名通知</a>'
                    '<a href="/good#heading">报名通知</a>')
        self.assertEqual(discover(self.site, page), ['https://contest.example/good'])

    def test_snapshot_does_not_invent_dates_from_footer_or_registration(self):
        page = Page(self.site.url, self.html(addition='<p>报名截止：2030年10月10日</p>'))
        parsed = parse_page(self.site, page)
        self.assertIsNone(parsed['source_published_on'])
        self.assertNotIn('2099', parsed['body'])
        self.assertNotIn('registration_deadline', parsed)

    def test_old_title_and_explicit_publish_date_are_preserved(self):
        page = Page(self.site.url, self.html('2020年全国大学生英语竞赛通知', '<p>发布时间：2020年10月1日</p>'))
        parsed = parse_page(self.site, page)
        self.assertEqual(parsed['status'], 'historical')
        self.assertEqual(parsed['source_published_on'], date(2020, 10, 1))

    @patch('competition_catalog.monitor.timezone.localdate', return_value=date(2026, 9, 28))
    def test_explicit_publication_date_marks_yearless_old_notice(self, _):
        parsed = parse_page(self.site, Page(self.site.url, self.html(
            '第十七届全国大学生英语竞赛通知', '<p>发布时间：2021年12月20日</p>')))
        self.assertEqual(parsed['status'], 'historical')
        current = parse_page(self.site, Page(self.site.url, self.html(
            '2027年全国大学生英语竞赛通知', '<p>发布时间：2025年12月20日</p>')))
        self.assertEqual(current['status'], 'pending')

    def test_article_heading_wins_over_site_logo_and_hidden_form_values(self):
        page = Page(self.site.url, '<html><title>学院网站</title><header><h1>学院标志</h1></header>'
                    '<article><h1>2030年全国大学生英语竞赛通知</h1>' + BODY +
                    '<form>session-secret<input value="private-password"></form>'
                    '<script>const token = "hidden-token";</script></article></html>')
        parsed = parse_page(self.site, page)
        self.assertEqual(parsed['title'], '2030年全国大学生英语竞赛通知')
        for value in ('学院标志', 'session-secret', 'private-password', 'hidden-token'):
            self.assertNotIn(value, parsed['body'])

    def test_unsafe_attachments_are_omitted_without_fetching_them(self):
        anchors = ''.join(f'<a href="{url}">附件</a>' for url in (
            'https://contest.example/rules.pdf', 'https://cdn.official.example/rules.pdf',
            'https://user:secret@contest.example/rules.pdf', 'http://127.0.0.1/private.pdf',
            'http://[::1]/private.pdf', 'http://[broken', 'http://intranet/rules.pdf',
            'http://intranet.local/rules.pdf', 'javascript:private.pdf',
            'https://contest.example:bad/rules.pdf'))
        with patch('competition_catalog.monitor.OfficialClient') as client:
            parsed = parse_page(self.site, Page(self.site.url, self.html(addition=anchors)))
        client.assert_not_called()
        self.assertEqual([item['url'] for item in parsed['attachments']], [
            'https://contest.example/rules.pdf', 'https://cdn.official.example/rules.pdf'])

    def test_empty_spa_is_not_successful_notice(self):
        with self.assertRaises(FetchError):
            parse_page(self.site, Page(self.site.url, '<html><div id="app"></div></html>'))

    def test_versions_deduplicate_and_restore_without_changing_first_seen(self):
        page = Page(self.site.url, self.html())
        parsed = parse_page(self.site, page)
        self.assertTrue(save_page(self.site, page, parsed))
        first = OfficialNotice.objects.get()
        first_seen = first.first_seen_at
        self.assertFalse(save_page(self.site, page, parsed))
        self.assertTrue(save_page(self.site, page, {**parsed, 'body': parsed['body'] + '\n更正通知'}))
        self.assertFalse(save_page(self.site, page, parsed))
        first.refresh_from_db()
        self.assertEqual(first.first_seen_at, first_seen)
        self.assertTrue(first.is_current_version)
        self.assertEqual(OfficialNotice.objects.count(), 2)
        self.assertEqual(OfficialNotice.objects.filter(is_current_version=True).count(), 1)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_failed_urls_rotate_and_old_pages_remain(self, _):
        outer = self
        class FakeSession:
            def get(self, site, url):
                if url == site.url:
                    return Page(url, outer.html(addition='<a href="/bad">报名通知1</a><a href="/good">报名通知2</a>'))
                if url.endswith('/bad'):
                    raise FetchError('timeout', '测试失败')
                return Page(url, outer.html('2030年全国大学生英语竞赛新规则'))
        first = sync_site(self.site, max_pages=2, session=FakeSession())
        self.assertEqual(first['status'], 'partial')
        second = sync_site(self.site, max_pages=2, session=FakeSession())
        self.assertEqual(second['status'], 'succeeded')
        self.assertTrue(OfficialNotice.objects.filter(url__endswith='/good').exists())
        self.assertEqual(MonitorRun.objects.count(), 2)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_notice_follows_actual_navigation_then_matching_new_detail(self, _):
        self.site.dedicated = False
        self.site.save(update_fields=['dedicated'])
        visited = []
        pages = {
            self.site.url: self.html('2020年全国大学生英语竞赛通知', '<nav><a href="/list">通知公告</a></nav>'),
            'https://contest.example/list': self.html('学院通知公告',
                '<a href="/new">2030年全国大学生英语竞赛报名通知</a>'
                '<a href="/unrelated">2030年另一项比赛报名通知</a>'
                '<a href="https://evil.example/private">2030年全国大学生英语竞赛报名通知</a>'),
            'https://contest.example/new': self.html(),
        }
        class FakeSession:
            def get(self, site, url):
                visited.append(url)
                return Page(url, pages[url])
        result = sync_site(self.site, max_pages=3, session=FakeSession())
        self.assertEqual(visited, list(pages))
        self.assertEqual(result['pages'], 3)
        self.assertEqual(OfficialNotice.objects.get(url__endswith='/list').page_kind, 'index')
        self.assertEqual(OfficialNotice.objects.get(url__endswith='/new').page_kind, 'notice')
        self.assertEqual(Competition.objects.count(), 0)
        self.assertEqual(CatalogBinding.objects.count(), 0)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_index_discovered_failures_share_rotation_with_known_details(self, _):
        self.site.dedicated = False
        self.site.save(update_fields=['dedicated'])
        visited = []
        outer = self
        class FakeSession:
            def get(self, site, url):
                visited.append(url)
                if url == site.url:
                    return Page(url, outer.html(addition='<nav><a href="/list">通知公告</a></nav>'))
                if url.endswith('/list'):
                    return Page(url, outer.html('学院通知公告',
                        '<a href="/bad">全国大学生英语竞赛报名通知一</a>'
                        '<a href="/good">全国大学生英语竞赛报名通知二</a>'))
                if url.endswith('/bad'):
                    raise FetchError('timeout', '测试超时')
                return Page(url, outer.html())
        for _ in range(4):
            sync_site(self.site, max_pages=3, session=FakeSession())
        details = [url.rsplit('/', 1)[-1] for url in visited if url.endswith(('/bad', '/good'))]
        self.assertEqual(details, ['bad', 'good', 'bad', 'good'])
        self.assertEqual(len(visited), 12)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_failed_list_still_allows_known_notice_within_page_budget(self, _):
        self.site.dedicated = False
        self.site.save(update_fields=['dedicated'])
        known = Page('https://contest.example/known', self.html())
        save_page(self.site, known, parse_page(self.site, known))
        visited = []
        outer = self
        class FakeSession:
            def get(self, site, url):
                visited.append(url)
                if url == site.url:
                    return Page(url, outer.html(addition='<nav><a href="/list">通知公告</a></nav>'))
                if url.endswith('/list'):
                    raise FetchError('timeout', '列表失败')
                return known
        result = sync_site(self.site, max_pages=3, session=FakeSession())
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(visited, [self.site.url, 'https://contest.example/list', known.url])
        self.assertEqual(result['unchanged'], 1)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_results_announcement_is_archived_without_opening_registration(self, _):
        outer = self
        class FakeSession:
            def get(self, site, url):
                return Page(url, outer.html('2030年全国大学生英语竞赛获奖公示',
                    '<p>获奖名单公示至2030年12月31日，本文不是报名通知。</p>'))
        result = sync_site(self.site, max_pages=1, session=FakeSession())
        self.assertEqual(result['pages'], 1)
        notice = OfficialNotice.objects.get()
        self.assertEqual(notice.status, 'pending')
        self.assertEqual(Competition.objects.count(), 0)
        self.assertEqual(CatalogBinding.objects.count(), 0)
        self.assertFalse(hasattr(notice, 'registration_deadline'))

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_stale_disabled_site_and_catalog_never_start_network_fetch(self, _):
        # 预先访问关联，确保缓存的 entry 也不会绕过后来停用。
        self.assertTrue(self.site.entry.is_active)
        with patch('competition_catalog.monitor.Session') as session:
            OfficialSite.objects.filter(pk=self.site.pk).update(enabled=False)
            result = sync_site(self.site)
            self.assertEqual(result['status'], 'disabled')
            session.return_value.get.assert_not_called()
            OfficialSite.objects.filter(pk=self.site.pk).update(enabled=True)
            CatalogEntry.objects.filter(pk=self.entry.pk).update(is_active=False)
            result = sync_site(self.site)
            self.assertEqual(result['status'], 'disabled')
            session.return_value.get.assert_not_called()
        self.assertEqual(MonitorRun.objects.count(), 0)

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_run_summary_never_contains_archived_body(self, _):
        outer = self
        class FakeSession:
            def get(self, site, url):
                return Page(url, outer.html(addition='<p>PUBLIC-SOURCE-CONTENT-NOT-FOR-LOGS</p>'))
            def close(self):
                pass
        output = StringIO()
        with patch('competition_catalog.management.commands.sync_competition_catalog.Session', return_value=FakeSession()):
            call_command('sync_competition_catalog', force=True, stdout=output)
        self.assertNotIn('PUBLIC-SOURCE-CONTENT-NOT-FOR-LOGS', output.getvalue())
        self.assertIn('snapshot_only', output.getvalue())

    @patch('competition_catalog.monitor.source_mutex', side_effect=lambda *_: nullcontext(True))
    def test_failure_records_backoff_without_deleting_history(self, _):
        page = Page(self.site.url, self.html())
        save_page(self.site, page, parse_page(self.site, page))
        class FakeSession:
            def get(self, site, url):
                raise FetchError('robots_disallowed', '网站禁止')
        result = sync_site(self.site, session=FakeSession())
        self.assertEqual(result['status'], 'failed')
        self.site.refresh_from_db()
        self.assertEqual(self.site.consecutive_failures, 1)
        self.assertGreater(self.site.next_check_at, timezone.now())
        self.assertEqual(OfficialNotice.objects.count(), 1)

    @override_settings(COMPETITION_CATALOG_ONLY=True)
    def test_public_scope_is_directory_bound_without_subject_exclusion(self):
        category = CompetitionTaxonomy.objects.create(code='languages', kind='category', name='外语')
        human = Competition.objects.create(code='english-2030', title='英语竞赛', edition='2030', category=category)
        outside = Competition.objects.create(code='unlisted-2030', title='目录外理工比赛', edition='2030', category=category)
        CatalogBinding.objects.create(entry=self.entry, competition=human, basis='核对目录')
        self.assertEqual(list(apply_competition_scope(Competition.objects.all())), [human])
        self.entry.is_active = False
        self.entry.save()
        self.assertEqual(apply_competition_scope(Competition.objects.all()).count(), 0)
        self.assertEqual(Competition.objects.count(), 2)

    def test_admin_requires_permission_and_does_not_expose_a_public_endpoint(self):
        user = get_user_model().objects.create_user(email='catalog-test@tongji.edu.cn', password='test-only', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/competition_catalog/officialnotice/').status_code, 403)

    def test_raw_notice_detail_is_readonly_and_requires_its_own_view_permission(self):
        page = Page(self.site.url, self.html(addition='<p>INTERNAL-ARCHIVE-MARKER</p>'))
        save_page(self.site, page, parse_page(self.site, page))
        notice = OfficialNotice.objects.get()
        detail = f'/admin/competition_catalog/officialnotice/{notice.pk}/change/'
        self.assertEqual(self.client.get(detail).status_code, 302)
        user = get_user_model().objects.create_user(email='catalog-view@tongji.edu.cn', password='test-only', is_staff=True)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='competition_catalog', codename='view_catalogentry'))
        self.client.force_login(user)
        denied = self.client.get(detail)
        self.assertEqual(denied.status_code, 403)
        self.assertNotContains(denied, 'INTERNAL-ARCHIVE-MARKER', status_code=403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='competition_catalog', codename='view_officialnotice'))
        self.assertContains(self.client.get(detail), 'INTERNAL-ARCHIVE-MARKER')
        self.assertEqual(self.client.post(detail, {'title': '篡改原文'}).status_code, 403)
        notice.refresh_from_db()
        self.assertNotEqual(notice.title, '篡改原文')
