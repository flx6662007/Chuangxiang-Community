"""NCDA 构造样本只供测试；不作为真实赛事导入。"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from competitions.models import Competition
from .adapters import ADAPTERS, RULE_VERSION
from .http import FetchError, Page
from .models import FetchRun, ProcessingResult, SourceVersion
from .services import accept_candidate, initialize_sources, record_extraction, sync_source


URL = 'https://www.ncda.org.cn/dsjs/dsnr/mtsd/9B6/'
HTML = '''<html><title>无年度标题</title><div id="main"><div class="dsjs">
<p><strong>2030未来设计师NCDA产教融合赛之<br>测试设计专项赛</strong></p>
<table class="peixun_table"><tbody>
<tr><td rowspan="2">赛项名称</td><td>【赛项名称】测试设计专项赛<a href="https://www.fd.show/member/login/ds">提交作品</a></td></tr>
<tr><td>【归类代码】9B6--2030产教融合赛</td></tr>
<tr><td rowspan="2">命题单位</td><td>【主办单位】：测试设计组委会</td></tr>
<tr><td>【承办单位】不应当作主办的单位</td></tr>
<tr><td rowspan="2">参赛对象<br>及赛程</td><td>【参赛对象】普通高校在读研究生、本科生、专科生；个人/团队（最多3名作者、2名指导教师）均可参赛。</td></tr>
<tr><td>【时间节点】<br>投稿时间：2030年9月1日—2030年9月22日；<br>校方审核：2030年9月23日—2030年9月24日；<br>获奖公布：2030年10月1日。</td></tr>
<tr><td>竞赛内容</td><td>围绕工程设计、艺术表达与产品创新设计完整作品，提交规范图稿及创作说明。</td></tr>
<tr><td>作品要求</td><td>每件作品最多三名作者、两名指导教师。提交原创作品。</td></tr>
<tr><td>投稿方式<br>及要求</td><td>在官方作品平台在线提交作品文件和设计说明。</td></tr>
</tbody></table></div></div><footer>2099届，主办单位：错误单位；投稿时间2099年1月1日</footer>
<!-- <div class="dsjs">伪造页脚</div> --></html>'''


class NcdaAdapterTests(SimpleTestCase):
    def parse(self, html=HTML):
        return ADAPTERS['ncda'].parse(Page(URL, html))

    def test_rowspan_fields_are_complete_and_submission_is_not_registration(self):
        result = self.parse()
        self.assertEqual(result.candidate['organizer'], '测试设计组委会')
        self.assertEqual(result.candidate['submission_deadline'], '2030-09-22')
        self.assertIsNone(result.candidate['registration_deadline'])
        self.assertIn('校方审核', result.candidate['deadline_notes'])
        self.assertEqual(result.candidate['edition'], '2030')
        self.assertEqual(result.candidate['code'], 'ncda-2030-9b6')
        self.assertEqual(result.candidate['rule_version'], RULE_VERSION)
        self.assertIsNone(result.published_on)
        self.assertNotIn('2099', result.body)
        self.assertEqual(result.errors, [])

    def test_authors_are_not_automatically_team_members_or_teachers(self):
        result = self.parse()
        self.assertEqual(result.candidate['participation_type'], 'both')
        self.assertIsNone(result.candidate['team_size_min'])
        self.assertIsNone(result.candidate['team_size_max'])
        self.assertIn('三名作者、两名指导教师', result.candidate['author_limit_note'])
        self.assertIn('不直接作为平台招募队伍人数上限', result.candidate['description'])

    def test_scoped_discovery_ignores_comments_awards_and_unapproved_domains(self):
        listing = '''<div class="zbdw">
        <div><a href="/dsjs/dsnr/mtsd/9B6/"><img></a><p>征稿中，2030年9月22日</p></div>
        <div><a href="https://ncda.org.cn/dsjs/dsnr/mtsd/9B6"><img></a><p>投稿中</p></div>
        <div><a href="/dsjs/dsnr/mtsd/9B4/">旧赛</a><p>奖项已公布</p></div>
        <div><a href="https://evil.example/dsjs/dsnr/mtsd/9B8/">伪链接</a><p>征稿中</p></div>
        <div><a onclick="openSomething()">活动</a><p>征稿中</p></div>
        <!-- <div><a href="/dsjs/dsnr/mtsd/9C3/">注释旧代码</a><p>征稿中</p></div> -->
        </div><a href="/dsjs/dsnr/mtsd/9C2/">正文范围外</a>'''
        self.assertEqual(ADAPTERS['ncda'].discover(Page(ADAPTERS['ncda'].base_url, listing)), [URL])

    def test_year_requires_current_identity_not_schedule_or_footer(self):
        html = HTML.replace('2030未来设计师', '未来设计师').replace('9B6--2030', '9B6--')
        with self.assertRaises(FetchError) as caught:
            self.parse(html)
        self.assertEqual(caught.exception.code, 'missing_edition_evidence')
        with self.assertRaises(FetchError):
            self.parse(HTML.replace('2030未来设计师', '2031未来设计师'))
        next_year = self.parse(HTML.replace('2030', '2031'))
        self.assertEqual(next_year.candidate['code'], 'ncda-2031-9b6')

    def test_unknown_deadline_stays_missing_and_code_mismatch_is_rejected(self):
        result = self.parse(HTML.replace('2030年9月1日—2030年9月22日', '时间另行通知'))
        self.assertIsNone(result.candidate['submission_deadline'])
        self.assertIn('submission_deadline', result.missing)
        with self.assertRaises(FetchError):
            self.parse(HTML.replace('9B6--2030', '9C3--2030'))

    def test_single_provincial_submission_date_is_not_award_or_final_date(self):
        result = self.parse(HTML.replace('投稿时间：2030年9月1日—2030年9月22日',
                                         '1、省赛征稿：即日起－2030年10月31日'))
        self.assertEqual(result.candidate['submission_deadline'], '2030-10-31')
        self.assertIsNone(result.candidate['registration_deadline'])

    def test_changed_or_conflicting_submission_deadline_requires_review(self):
        for line in ('投稿时间：原定2030年9月22日，延期至2030年10月1日',
                     '投稿时间：2030年9月22日或2030年10月1日',
                     '投稿时间：2030年9月22日；<br>省赛征稿：2030年10月1日'):
            with self.subTest(line=line):
                result = self.parse(HTML.replace('投稿时间：2030年9月1日—2030年9月22日', line))
                self.assertIsNone(result.candidate['submission_deadline'])
                self.assertIn('ambiguous_deadline:submission_deadline', result.errors)

    def test_registration_entry_must_be_from_current_table(self):
        result = self.parse(HTML.replace('https://www.fd.show/member/login/ds', 'https://evil.example/')
                            .replace('</footer>', '<a href="https://www.fd.show/">页脚提交入口</a></footer>'))
        self.assertEqual(result.candidate['registration_url'], '')
        result = self.parse()
        self.assertIn(result.evidence['registration_url'], result.body)

    def test_missing_organizer_is_a_validation_error(self):
        result = self.parse(HTML.replace('【主办单位】：测试设计组委会', '【协办单位】：测试协办单位'))
        self.assertEqual(result.candidate['organizer'], '')
        self.assertIn('missing_required_evidence', result.errors)

    def test_broken_merged_rows_are_not_silently_mapped(self):
        with self.assertRaises(FetchError) as caught:
            self.parse(HTML.replace('rowspan="2">命题单位', 'rowspan="3">命题单位'))
        self.assertEqual(caught.exception.code, 'layout_changed')


class NcdaIngestionTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(email='ncda-test@tongji.edu.cn', password='test-only')
        self.source = next(source for source in initialize_sources(actor=self.actor) if source.code == 'ncda')

    def record(self, html=HTML):
        run = FetchRun.objects.create(source=self.source, requested_url=URL, trigger='scheduled')
        page = Page(URL, html)
        return record_extraction(self.source, run, page, ADAPTERS['ncda'].parse(page))[0]

    def test_realistic_submission_card_publishes_without_automatically_opening_recruitment(self):
        result = self.record()
        competition = accept_candidate(result.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        self.assertEqual(competition.publication_status, 'published')
        self.assertEqual(competition.submission_deadline.isoformat(), '2030-09-22')
        self.assertIsNone(competition.registration_deadline)
        self.assertFalse(competition.recruitment_enabled)
        self.assertFalse(competition.is_recruitment_open)
        self.assertEqual(competition.category.code, 'art-and-design')
        self.assertIsNone(competition.sources.get().source_published_on)

    def test_repeated_scheduled_sync_deduplicates_and_keeps_public_timestamps(self):
        class FakeClient:
            def get(self, url):
                if url == ADAPTERS['ncda'].base_url:
                    return Page(url, f'<div class="zbdw"><div><a href="{URL}">设计赛</a><p>征稿中</p></div></div>')
                return Page(url, HTML)
        first = sync_source(self.source, client=FakeClient(), auto_accept=True, enable_recruitment=True)
        competition = Competition.objects.get()
        timestamps = (competition.published_at, competition.updated_at)
        repeat = sync_source(self.source, client=FakeClient(), auto_accept=True, enable_recruitment=True)
        competition.refresh_from_db()
        self.assertEqual((first['accepted'], repeat['accepted'], repeat['unchanged']), (1, 1, 1))
        self.assertEqual((competition.published_at, competition.updated_at), timestamps)
        self.assertEqual(SourceVersion.objects.count(), 1)
        self.assertEqual(ProcessingResult.objects.count(), 1)

    def test_submission_date_change_stays_pending_and_expired_date_never_recruits(self):
        original = self.record(HTML.replace('2030', '2020'))
        competition = accept_candidate(original.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        self.assertFalse(competition.is_recruitment_open)
        revised = self.record(HTML.replace('2030', '2020').replace('2020年9月22日', '2020年9月23日'))
        with self.assertRaises(ValidationError):
            accept_candidate(revised.pk, actor=self.actor, mode='rules')
        competition.refresh_from_db()
        self.assertEqual(competition.submission_deadline.isoformat(), '2020-09-22')
