"""结构测试使用小型构造 HTML，真实联网核验在命令验收中单独执行。"""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase, SimpleTestCase, TransactionTestCase
from django.utils import timezone
import httpx

from competitions.models import Competition, CompetitionSource
from .adapters import ADAPTERS, RULE_VERSION
from .http import FetchError, OfficialClient, Page, checked_url
from .models import FetchRun, ProcessingResult, SourceVersion
from .services import accept_candidate, initialize_sources, record_extraction, source_mutex, sync_source

AIC_URL = 'https://www.aicomp.cn/tracks/tracks-5/99999.html'
AIC_HTML = '''<html><div class="article-title"><div class="title">2030AIC·“测试主题”算法主题赛赛题及竞赛规则</div><div>2030-08-01 阅读 12</div></div>
<div class="article-content"><h6>一、组织机构</h6><p>主办单位：测试组委会</p>
<h6>二、参赛对象</h6><p>全球高校正式在读学生均可参赛。</p><h6>三、参赛要求</h6>
<p>1. 参赛选手可单人创建队伍，每支参赛团队人数不超过3人。</p>
<h6>四、赛题说明</h6><p>（一）测试方向</p><p>提交能够演示的应用及完整文档。</p>
<h6>五、赛程安排</h6><p>报名截止后不能修改队伍。</p><p>（一）报名（截止日期：2030年10月15日）</p>
<p>参赛者通过大赛官方网站注册，报名截止时间为10月15日20:00。</p>
<p>作品提交截止时间为2030年10月15日20:00。</p></div>
<footer>主办单位：错误页脚单位。报名截止：2099年12月31日</footer>
<a href="https://reg.aicomp.cn">大赛报名</a></html>'''

NMM_URL = 'https://www.nmmcm.org.cn/News/99999.html'
NMM_HTML = '''<h1 class="article-title">2030年第十六届数维杯全国大学生数学建模挑战赛（秋季赛）报名通知</h1>
<div class="article-meta">发布时间：2030-08-09</div><div class="article-content">
<p>主办单位：测试建模组委会</p><p>报名截止：即日起至2030年11月20日06:00</p>
<p>论文提交截止：2030年11月24日10:00</p>
<p>参赛对象：全国全日制在校学生。每队1–3名学生，允许跨校组队。</p>
<p>赛题设置：数学建模与交叉学科建模，任选一道赛题并提交规范论文。</p>
<p>在线支付：登录报名官网<a href="https://www.mojinghub.com/competitions/swbmcm/2030">https://www.mojinghub.com/competitions/swbmcm/2030</a>在线完成。</p>
</div><aside>2099年新赛季 999人</aside>'''


class AdapterTests(SimpleTestCase):
    def test_aic_fields_scoped_to_article_and_explicit_dates(self):
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, AIC_HTML))
        self.assertEqual(parsed.candidate['registration_deadline'], '2030-10-15')
        self.assertEqual(parsed.candidate['organizer'], '测试组委会')
        self.assertEqual(parsed.candidate['team_size_max'], 3)
        self.assertEqual(parsed.candidate['team_size_min'], 1)
        self.assertEqual(parsed.candidate['registration_url'], 'https://reg.aicomp.cn')
        self.assertNotIn('错误页脚', parsed.body)
        self.assertIn('20:00', parsed.candidate['deadline_notes'])
        self.assertNotIn('registration_deadline_at', parsed.candidate)
        self.assertEqual(parsed.errors, [])

    def test_nmm_season_and_person_count_not_teacher_count(self):
        parsed = ADAPTERS['nmmcm'].parse(Page(NMM_URL, NMM_HTML))
        self.assertEqual(parsed.candidate['edition'], '2030 秋季赛')
        self.assertEqual(parsed.candidate['team_size_max'], 3)
        self.assertEqual(parsed.candidate['registration_deadline'], '2030-11-20')
        self.assertNotIn('2099', parsed.body)

    def test_missing_fields_remain_missing(self):
        html = AIC_HTML.replace('报名（截止日期：2030年10月15日）', '报名（尚未公布）')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['registration_deadline'])
        self.assertIn('registration_deadline', parsed.missing)

    def test_discovery_rejects_other_contests_and_duplicate_links(self):
        html = f'<a href="{NMM_URL}">2030年第十六届数维杯全国大学生数学建模挑战赛（秋季赛）报名通知</a>'
        html += html + '<a href="/News/7.html">2031美国大学生数学建模竞赛报名通知</a>'
        self.assertEqual(ADAPTERS['nmmcm'].discover(Page('https://www.nmmcm.org.cn/', html)), [NMM_URL])

    def test_layout_change_is_not_silently_parsed(self):
        with self.assertRaises(FetchError):
            ADAPTERS['aicomp'].parse(Page(AIC_URL, '<h1>Changed</h1>'))

    def test_postponement_with_old_and_new_dates_requires_review(self):
        html = AIC_HTML.replace('报名（截止日期：2030年10月15日）', '报名截止由2030年9月30日延期至2030年10月15日')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['registration_deadline'])
        self.assertIn('ambiguous_deadline:registration_deadline', parsed.errors)
        html = AIC_HTML.replace('报名（截止日期：2030年10月15日）', '报名于2030年8月1日开始，报名截止：2030年10月15日')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertEqual(parsed.candidate['registration_deadline'], '2030-10-15')
        html = AIC_HTML.replace('报名（截止日期：2030年10月15日）', '报名于2030年8月1日开始，报名截止：10月15日')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['registration_deadline'])

    def test_students_and_teachers_are_counted_separately(self):
        html = AIC_HTML.replace('参赛选手可单人创建队伍，每支参赛团队人数不超过3人。', '每支团队可设指导教师最多2人、学生不超过3人。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertEqual(parsed.candidate['team_size_max'], 3)
        html = AIC_HTML.replace('参赛选手可单人创建队伍，每支参赛团队人数不超过3人。', '每支团队可设指导教师最多2人，其他人数规则见附件。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['team_size_max'])
        self.assertIn('ambiguous_team_size', parsed.errors)

    def test_member_limit_and_teacher_limit_keep_student_count_and_eligibility(self):
        rules = ('参赛选手可单人创建队伍参赛，也可与本校（不含分校）其他选手组队参赛。'
                 '每支团队成员上限3名（跨校组队无效），每支团队最多可设置2名指导教师。')
        html = AIC_HTML.replace('参赛选手可单人创建队伍，每支参赛团队人数不超过3人。', rules)
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertEqual((parsed.candidate['participation_type'], parsed.candidate['team_size_min'],
                          parsed.candidate['team_size_max']), ('both', 1, 3))
        self.assertIn('跨校组队无效', parsed.candidate['eligibility'])
        self.assertIn('2名指导教师', parsed.candidate['eligibility'])
        self.assertIn(parsed.evidence['team_size_max'], parsed.body)
        self.assertEqual(parsed.candidate['rule_version'], 'official-html-2026-09-v2')
        self.assertEqual(parsed.errors, [])

    def test_separate_single_person_rule_and_conflicting_group_limits(self):
        original = '参赛选手可单人创建队伍，每支参赛团队人数不超过3人。'
        html = AIC_HTML.replace(original, '参赛选手可单人创建队伍。</p><p>每支团队成员上限3名。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertEqual((parsed.candidate['participation_type'], parsed.candidate['team_size_min'],
                          parsed.candidate['team_size_max']), ('both', 1, 3))
        html = html.replace('每支团队成员上限3名。', '学生组每支团队成员上限3名。</p><p>综合组每支团队成员上限5名。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['team_size_max'])
        self.assertIsNone(parsed.candidate['team_size_min'])
        self.assertEqual(parsed.candidate['participation_type'], 'unknown')
        self.assertIn('ambiguous_team_size', parsed.errors)

        html = AIC_HTML.replace('参赛选手可单人创建队伍，每支参赛团队人数不超过3人。',
                                '每支团队成员上限3名，不允许单人参赛。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertEqual(parsed.candidate['participation_type'], 'team')
        self.assertIsNone(parsed.candidate['team_size_min'])

    def test_teacher_only_maximum_does_not_become_member_limit(self):
        html = AIC_HTML.replace('参赛选手可单人创建队伍，每支参赛团队人数不超过3人。',
                                '每支团队最多2名指导教师，学生人数见附件，不允许单人参赛。')
        parsed = ADAPTERS['aicomp'].parse(Page(AIC_URL, html))
        self.assertIsNone(parsed.candidate['team_size_max'])
        self.assertEqual(parsed.candidate['participation_type'], 'unknown')
        self.assertIn('ambiguous_team_size', parsed.errors)

    def test_url_allowlist_and_private_dns(self):
        for url in ('file:///tmp/a', 'http://127.0.0.1/', 'https://www.aicomp.cn@localhost/', 'https://www.aicomp.cn:8000/'):
            with self.subTest(url=url), self.assertRaises(FetchError):
                checked_url(url, ADAPTERS['aicomp'].hosts)
        with patch('ingestion.http.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), self.assertRaises(FetchError):
            checked_url(AIC_URL, ADAPTERS['aicomp'].hosts)

    def test_redirect_revalidated_and_no_private_target_request(self):
        seen = []
        def handle(request):
            seen.append(str(request.url))
            if request.url.path == '/robots.txt':
                return httpx.Response(404)
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/private'})
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(handle), resolve=False, interval=0)
        try:
            with self.assertRaises(FetchError):
                client.get(AIC_URL)
            self.assertFalse(any('127.0.0.1' in url for url in seen))
        finally:
            client.close()

    def test_robots_disallow_prevents_article_request(self):
        seen = []
        def handle(request):
            seen.append(request.url.path)
            return httpx.Response(200, text='User-agent: *\nDisallow: /tracks/')
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(handle), resolve=False, interval=0)
        try:
            with self.assertRaises(FetchError):
                client.get(AIC_URL)
            self.assertEqual(seen, ['/robots.txt'])
        finally:
            client.close()

    def test_connection_pins_public_ip_and_preserves_tls_hostname(self):
        seen = []
        def handle(request):
            seen.append((request.url.host, request.headers['host'], request.extensions.get('sni_hostname')))
            return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(200, text='<p>OK</p>')
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(handle), interval=0)
        try:
            with patch.object(client, '_public_address', return_value='120.55.167.15'):
                self.assertEqual(client.get(AIC_URL).url, AIC_URL)
            self.assertEqual(seen, [('120.55.167.15', 'www.aicomp.cn', 'www.aicomp.cn')] * 2)
        finally:
            client.close()

    def test_public_resolver_cannot_authorize_private_ip(self):
        seen = []
        def handle(request):
            seen.append(request.url.host)
            return httpx.Response(200, json={'Answer': [{'type': 1, 'data': '127.0.0.1'}]})
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(handle), interval=0)
        try:
            with patch('ingestion.http.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('198.18.1.1', 443))]), self.assertRaises(FetchError):
                client.get(AIC_URL)
            self.assertEqual(seen, ['1.1.1.1'])
        finally:
            client.close()

    def test_retry_is_bounded_and_body_size_is_limited(self):
        attempts = []
        def handle(request):
            if request.url.path == '/robots.txt':
                return httpx.Response(404)
            attempts.append(request.url.path)
            return httpx.Response(503)
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(handle), resolve=False, interval=0)
        try:
            with patch('ingestion.http.time.sleep'), self.assertRaises(FetchError):
                client.get(AIC_URL)
            self.assertEqual(len(attempts), 3)
        finally:
            client.close()
        def large(request):
            return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(200, content=b'a' * 2_000_001)
        client = OfficialClient(ADAPTERS['aicomp'].hosts, transport=httpx.MockTransport(large), resolve=False, interval=0)
        try:
            with self.assertRaises(FetchError) as caught:
                client.get(AIC_URL)
            self.assertEqual(caught.exception.code, 'page_too_large')
        finally:
            client.close()


class IngestionTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(email='crawler-test@tongji.edu.cn', password='test-password-only')
        self.source = initialize_sources(actor=self.actor)[0]

    def record(self, html=AIC_HTML):
        run = FetchRun.objects.create(source=self.source, requested_url=AIC_URL, trigger='scheduled')
        return record_extraction(self.source, run, Page(AIC_URL, html), ADAPTERS['aicomp'].parse(Page(AIC_URL, html)))

    def test_deduplication_immutable_history_and_publish_idempotence(self):
        result, unchanged = self.record()
        self.assertFalse(unchanged)
        competition = accept_candidate(result.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        created_at, updated_at = competition.published_at, competition.updated_at
        same, unchanged = self.record()
        self.assertTrue(unchanged)
        self.assertEqual(same.pk, result.pk)
        self.assertEqual(accept_candidate(result.pk, actor=self.actor).pk, competition.pk)
        competition.refresh_from_db()
        self.assertEqual(competition.published_at, created_at)
        self.assertEqual(competition.updated_at, updated_at)
        self.assertEqual(Competition.objects.count(), 1)
        self.assertEqual(SourceVersion.objects.count(), 1)
        self.assertTrue(competition.is_recruitment_open)
        self.assertIsNone(competition.registration_deadline_at)
        version = result.source_version
        version.body_text = 'cannot overwrite history'
        with self.assertRaises(ValidationError):
            version.full_clean()

    def test_changed_deadline_is_new_version_pending_and_preserves_current(self):
        first, _ = self.record()
        competition = accept_candidate(first.pk, actor=self.actor, mode='rules')
        changed, unchanged = self.record(AIC_HTML.replace('2030年10月15日', '2030年10月16日'))
        self.assertFalse(unchanged)
        self.assertEqual(SourceVersion.objects.count(), 2)
        with self.assertRaises(ValidationError):
            accept_candidate(changed.pk, actor=self.actor, mode='rules')
        competition.refresh_from_db()
        self.assertEqual(competition.registration_deadline.isoformat(), '2030-10-15')
        changed.refresh_from_db()
        self.assertEqual(changed.status, 'pending')

    def test_publication_failure_rolls_back_competition_and_decision(self):
        result, _ = self.record()
        with patch('ingestion.services.publish_competition', side_effect=ValidationError('fail')), self.assertRaises(ValidationError):
            accept_candidate(result.pk, actor=self.actor, mode='rules')
        self.assertFalse(Competition.objects.exists())
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')

    def test_manual_changes_are_never_overwritten_automatically(self):
        result, _ = self.record()
        competition = accept_candidate(result.pk, actor=self.actor, mode='rules')
        competition.summary = '管理员确认补充的信息'
        competition.save()
        changed, _ = self.record(AIC_HTML.replace('测试方向', '测试新方向'))
        with self.assertRaises(ValidationError):
            accept_candidate(changed.pk, actor=self.actor, mode='rules')
        competition.refresh_from_db()
        self.assertEqual(competition.summary, '管理员确认补充的信息')

    def test_failed_fetch_retains_previous_data_and_records_error(self):
        result, _ = self.record()
        competition = accept_candidate(result.pk, actor=self.actor, mode='rules')
        class Broken:
            def get(self, url):
                raise FetchError('timeout', '获取官方页面超时。')
        stats = sync_source(self.source, client=Broken(), auto_accept=True)
        self.assertGreater(stats['failed'], 0)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'published')
        self.assertTrue(FetchRun.objects.filter(status='failed', error_code='timeout').exists())

    def test_discovery_and_repeat_sync_are_idempotent(self):
        class FakeClient:
            def get(self, url):
                if url.endswith('tracks-5'):
                    return Page(url, f'<a href="{AIC_URL}">2030AIC·“测试主题”算法主题赛赛题及竞赛规则</a>')
                return Page(url, AIC_HTML)
        first = sync_source(self.source, client=FakeClient(), auto_accept=True)
        again = sync_source(self.source, client=FakeClient(), auto_accept=True)
        self.assertEqual(first['accepted'], 1)
        self.assertEqual(again['unchanged'], 1)
        self.assertEqual(Competition.objects.count(), 1)

    def test_expired_registration_never_opens_recruitment(self):
        result, _ = self.record(AIC_HTML.replace('2030', '2020'))
        competition = accept_candidate(result.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        self.assertEqual(competition.team_size_max, 3)
        self.assertFalse(competition.recruitment_enabled)
        self.assertFalse(competition.is_recruitment_open)
        self.assertIsNone(competition.recruitment_deadline)

    def test_ambiguous_member_limits_cannot_be_automatically_accepted(self):
        html = AIC_HTML.replace('每支参赛团队人数不超过3人。',
                                '学生组每支团队成员上限3名，综合组每支团队成员上限5名。')
        result, _ = self.record(html)
        with self.assertRaises(ValidationError):
            accept_candidate(result.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')
        self.assertFalse(Competition.objects.exists())

    def test_rule_upgrade_reuses_original_but_creates_new_candidate(self):
        old_rule = 'official-html-2026-09-v1'
        with patch('ingestion.adapters.RULE_VERSION', old_rule), patch('ingestion.services.RULE_VERSION', old_rule):
            original, _ = self.record()
            competition = accept_candidate(original.pk, actor=self.actor, mode='rules')
        revised, unchanged = self.record()
        self.assertTrue(unchanged)
        self.assertEqual(revised.source_version_id, original.source_version_id)
        self.assertNotEqual(revised.pk, original.pk)
        self.assertEqual(revised.candidate['rule_version'], RULE_VERSION)
        self.assertEqual(accept_candidate(revised.pk, actor=self.actor, mode='rules').pk, competition.pk)
        self.assertEqual(SourceVersion.objects.count(), 1)
        self.assertEqual(Competition.objects.count(), 1)


    def test_old_pending_candidate_cannot_override_latest_observation(self):
        first, _ = self.record()
        second, _ = self.record(AIC_HTML.replace('测试方向', '新的测试方向'))
        competition = accept_candidate(second.pk, actor=self.actor, mode='rules')
        for mode in ('rules', 'human'):
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                accept_candidate(first.pk, actor=self.actor, mode=mode)
        competition.refresh_from_db()
        self.assertIn('新的测试方向', competition.tracks)

    def test_source_reversion_reuses_version_but_requires_a_new_decision(self):
        first, _ = self.record()
        competition = accept_candidate(first.pk, actor=self.actor, mode='rules')
        second, _ = self.record(AIC_HTML.replace('测试方向', '新的测试方向'))
        accept_candidate(second.pk, actor=self.actor, mode='rules')
        reverted, unchanged = self.record()
        self.assertFalse(unchanged)
        self.assertEqual(reverted.source_version_id, first.source_version_id)
        self.assertNotEqual(reverted.pk, first.pk)
        self.assertEqual(reverted.status, 'pending')
        self.assertTrue(reverted.candidate['_source_reverted'])
        self.assertEqual(SourceVersion.objects.count(), 2)
        with self.assertRaises(ValidationError):
            accept_candidate(reverted.pk, actor=self.actor, mode='rules')
        again, _ = self.record()
        self.assertEqual(again.pk, reverted.pk)
        accept_candidate(reverted.pk, actor=self.actor, mode='human')
        competition.refresh_from_db()
        self.assertNotIn('新的测试方向', competition.tracks)
        self.assertEqual(ProcessingResult.objects.filter(status='accepted').count(), 3)

    def test_reused_url_cannot_rewrite_an_existing_edition_even_by_human(self):
        original, _ = self.record()
        competition = accept_candidate(original.pk, actor=self.actor, mode='rules')
        new_edition, _ = self.record(AIC_HTML.replace('2030', '2031'))
        for mode in ('rules', 'human'):
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                accept_candidate(new_edition.pk, actor=self.actor, mode=mode)
        competition.refresh_from_db()
        self.assertEqual(competition.edition, '2030')
        self.assertIn('2030', competition.title)
        new_edition.refresh_from_db()
        self.assertEqual(new_edition.status, 'pending')


class SourceMutexTests(TransactionTestCase):
    def test_other_connection_skips_until_owner_releases(self):
        ready, release = Event(), Event()
        def owner():
            try:
                with source_mutex(771) as acquired:
                    ready.set()
                    if not acquired:
                        return False
                    release.wait(10)
                    return True
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(owner)
            try:
                self.assertTrue(ready.wait(5))
                with source_mutex(771) as acquired:
                    self.assertFalse(acquired)
            finally:
                release.set()
            self.assertTrue(future.result(timeout=5))
        with source_mutex(771) as acquired:
            self.assertTrue(acquired)
