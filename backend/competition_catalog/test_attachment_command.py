"""附件调度使用隔离测试数据库；网络和附件解析全部替换，不读取正式来源。"""
from contextlib import contextmanager, nullcontext
from datetime import timedelta
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from ingestion.http import FetchError
from .models import CatalogEntry, OfficialNotice, OfficialSite

COMMAND = 'competition_catalog.management.commands.fetch_catalog_attachments'


class AttachmentCommandTests(TestCase):
    def setUp(self):
        self.site = self.make_site('2026001')
        self.urls = [f'https://contest.example/rules-{number}.pdf' for number in range(1, 5)]
        self.notice = self.make_notice(self.site, self.urls)
        self.fetch_patch = patch(COMMAND + '.fetch_attachment')
        self.fetch = self.fetch_patch.start()
        self.addCleanup(self.fetch_patch.stop)
        self.fetch.side_effect = FetchError('timeout', '测试下载超时。')
        self.client_patch = patch(COMMAND + '.OfficialClient', autospec=True)
        self.client = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def make_site(self, code):
        entry = CatalogEntry.objects.create(code=code, name='测试竞赛', grade='A',
            levels='国家级', departments=[], source_url='https://school.example/catalog')
        return OfficialSite.objects.create(entry=entry, url='https://contest.example/' + code,
            evidence_url='https://school.example/notice', allowed_hosts=['contest.example'])

    def make_notice(self, site, urls, suffix='notice', **kwargs):
        return OfficialNotice.objects.create(site=site, url=f'https://contest.example/{suffix}',
            title='2030年测试竞赛参赛规则', body='原始参赛规则。', content_hash=suffix,
            attachments=[{'url': url, 'title': f'竞赛规则附件{index}'} for index, url in enumerate(urls)], **kwargs)

    def run_command(self, **kwargs):
        output = StringIO()
        call_command('fetch_catalog_attachments', stdout=output, **kwargs)
        return [json.loads(line) for line in output.getvalue().splitlines() if line]

    def requested(self):
        return [call.args[1]['url'] for call in self.fetch.call_args_list]

    def success(self, site, attachment, *, client):
        return dict(url=attachment['url'], title='规则附件', body='参赛学生与截止时间以官方规则为准。',
            attachments=[], source_published_on=None, page_kind='notice', status='pending',
            document_format='pdf', page_count=1)

    def test_failed_first_two_rotate_to_later_attachments_across_runs(self):
        first = self.run_command(limit=2, max_per_notice=2)
        second = self.run_command(limit=2, max_per_notice=2)
        self.assertEqual(self.requested(), self.urls)
        self.assertEqual(first[-1]['summary']['failed'], 2)
        self.assertEqual(second[-1]['summary']['attempted'], 2)
        self.site.refresh_from_db()
        for url in self.urls:
            self.assertGreater(self.site.page_attempts['attachment:' + url], 0)
            self.assertNotIn('attachment-success:' + url, self.site.page_attempts)
        self.assertEqual(OfficialNotice.objects.count(), 1)

    def test_global_budget_prefers_oldest_attempt_across_notices(self):
        other = self.make_site('2026002')
        other_url = 'https://contest.example/older.docx'
        self.make_notice(other, [other_url], suffix='new-notice')
        self.site.page_attempts = {'attachment:' + url: 200 for url in self.urls}
        self.site.save(update_fields=['page_attempts'])
        other.page_attempts = {'attachment:' + other_url: 100}
        other.save(update_fields=['page_attempts'])
        self.run_command(limit=1)
        self.assertEqual(self.requested(), [other_url])

    def test_recent_success_skips_without_consuming_notice_or_global_budget(self):
        self.make_notice(self.site, [], suffix='stored', page_kind='notice')
        OfficialNotice.objects.filter(content_hash='stored').update(url=self.urls[0])
        result = self.run_command(limit=1, max_per_notice=1)
        self.assertEqual(self.requested(), [self.urls[1]])
        self.assertEqual(result[-1]['summary']['not_due'], 1)
        self.assertEqual(result[-1]['summary']['attempted'], 1)

    def test_old_success_is_due_again_and_force_bypasses_recent_success(self):
        self.notice.attachments = self.notice.attachments[:1]
        self.notice.save(update_fields=['attachments'])
        self.site.page_attempts = {'attachment-success:' + self.urls[0]:
                                   (timezone.now() - timedelta(hours=7)).timestamp()}
        self.site.save(update_fields=['page_attempts'])
        self.fetch.side_effect = self.success
        self.run_command()
        self.assertEqual(self.fetch.call_count, 1)
        self.run_command()
        self.assertEqual(self.fetch.call_count, 1)
        self.run_command(force=True)
        self.assertEqual(self.fetch.call_count, 2)

    def test_redirected_success_is_cached_by_original_requested_url(self):
        self.notice.attachments = self.notice.attachments[:1]
        self.notice.save(update_fields=['attachments'])
        def redirect(site, attachment, *, client):
            parsed = self.success(site, attachment, client=client)
            parsed['url'] = 'https://contest.example/downloads/final.pdf'
            return parsed
        self.fetch.side_effect = redirect
        self.run_command()
        result = self.run_command()
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(result[-1]['summary']['not_due'], 1)
        self.site.refresh_from_db()
        self.assertIn('attachment-success:' + self.urls[0], self.site.page_attempts)
        self.assertTrue(OfficialNotice.objects.filter(url='https://contest.example/downloads/final.pdf').exists())

    def test_global_lock_failure_leaves_state_untouched(self):
        with patch(COMMAND + '.source_mutex', return_value=nullcontext(False)) as mutex:
            output = self.run_command()
        self.assertEqual(output, [{'skipped': 'already_running'}])
        mutex.assert_called_once_with('catalog-attachments')
        self.fetch.assert_not_called()
        self.client.assert_not_called()
        self.site.refresh_from_db()
        self.assertEqual(self.site.page_attempts, {})

    def test_locked_site_does_not_spend_other_sites_budget(self):
        other = self.make_site('2026002')
        other_url = 'https://contest.example/other.pdf'
        self.make_notice(other, [other_url], suffix='older-notice')
        with patch(COMMAND + '.source_mutex', side_effect=lambda name: nullcontext(name != f'catalog-{self.site.pk}')):
            result = self.run_command(limit=2)
        self.assertEqual(self.requested(), [other_url])
        self.assertEqual(result[-1]['summary']['attempted'], 1)
        self.assertEqual(result[-1]['summary']['locked'], 4)
        self.site.refresh_from_db()
        self.assertEqual(self.site.page_attempts, {})

    def test_refresh_under_site_lock_preserves_new_html_progress(self):
        html_url = 'https://contest.example/new-html-notice'
        @contextmanager
        def mutex(name):
            if name == f'catalog-{self.site.pk}':
                OfficialSite.objects.filter(pk=self.site.pk).update(page_attempts={html_url: 123456})
            yield True
        with patch(COMMAND + '.source_mutex', side_effect=mutex):
            self.run_command(limit=1)
        self.site.refresh_from_db()
        self.assertEqual(self.site.page_attempts[html_url], 123456)
        self.assertIn('attachment:' + self.urls[0], self.site.page_attempts)

    def test_pause_after_selection_prevents_client_creation_and_attempt(self):
        @contextmanager
        def mutex(name):
            if name == f'catalog-{self.site.pk}':
                CatalogEntry.objects.filter(pk=self.site.entry_id).update(is_active=False)
            yield True
        with patch(COMMAND + '.source_mutex', side_effect=mutex):
            result = self.run_command()
        self.fetch.assert_not_called()
        self.client.assert_not_called()
        self.assertEqual(result[-1]['summary']['disabled'], 4)
        self.site.refresh_from_db()
        self.assertEqual(self.site.page_attempts, {})

    def test_replaced_parent_notice_is_not_downloaded(self):
        @contextmanager
        def mutex(name):
            if name == f'catalog-{self.site.pk}':
                OfficialNotice.objects.filter(pk=self.notice.pk).update(is_current_version=False)
            yield True
        with patch(COMMAND + '.source_mutex', side_effect=mutex):
            result = self.run_command()
        self.fetch.assert_not_called()
        self.assertEqual(result[-1]['summary']['obsolete'], 4)

    def test_soft_budget_finishes_current_save_then_next_run_rotates(self):
        clock = {'now': 0}
        def slow_success(site, attachment, *, client):
            clock['now'] += 11
            return self.success(site, attachment, client=client)
        self.fetch.side_effect = slow_success
        with patch(COMMAND + '.time.monotonic', side_effect=lambda: clock['now']):
            result = self.run_command(max_seconds=10)
            self.assertTrue(OfficialNotice.objects.filter(url=self.urls[0]).exists())
            self.assertEqual(result[-1]['summary']['created'], 1)
            self.assertEqual(result[-1]['summary']['time_budget_reached'], 1)
            clock['now'] = 0
            self.run_command(max_seconds=10)
        self.assertEqual(self.requested(), self.urls[:2])
        self.assertTrue(OfficialNotice.objects.filter(url=self.urls[1]).exists())
        self.client.return_value.close.assert_called()

    def test_attempt_survives_unexpected_parser_failure_and_client_closes(self):
        self.fetch.side_effect = RuntimeError('simulated process failure')
        with self.assertRaises(RuntimeError):
            self.run_command(limit=1)
        self.site.refresh_from_db()
        self.assertIn('attachment:' + self.urls[0], self.site.page_attempts)
        self.client.return_value.close.assert_called_once()
        self.fetch.side_effect = FetchError('timeout', '测试下载超时。')
        self.run_command(limit=1)
        self.assertEqual(self.requested(), self.urls[:2])

    def test_invalid_budgets_are_rejected_before_download(self):
        for kwargs in ({'max_seconds': 9}, {'max_seconds': 1801}, {'limit': 0}, {'max_per_notice': 6}):
            with self.subTest(kwargs=kwargs), self.assertRaises(CommandError):
                self.run_command(**kwargs)
        self.fetch.assert_not_called()

    def test_code_filter_and_existing_private_attachment_exclusions_remain(self):
        self.notice.attachments = [
            {'url': 'https://contest.example/contacts.pdf', 'title': '教师通讯录'},
            {'url': 'https://contest.example/receipts.docx', 'title': '报名回执'},
            {'url': 'https://contest.example/old.doc', 'title': '旧格式规则'},
            *self.notice.attachments,
        ]
        self.notice.save(update_fields=['attachments'])
        self.run_command(code=['2099999'])
        self.fetch.assert_not_called()
        self.run_command(code=[self.site.entry.code], limit=1)
        self.assertEqual(self.requested(), [self.urls[0]])

    def test_index_matching_competition_pdf_is_saved_without_reclassifying_parent(self):
        self.notice.page_kind = 'index'
        self.notice.title = '中国数学会竞赛列表'
        self.notice.attachments = [
            {'url': self.urls[0], 'title': '关于举办第十八届全国大学生数学竞赛的通知'},
            {'url': self.urls[1], 'title': '全国中学生数学竞赛通知'},
            {'url': self.urls[2], 'title': '全国大学生数学竞赛获奖名单'},
            {'url': self.urls[3], 'title': '报名通知'},
        ]
        self.notice.save(update_fields=['page_kind', 'title', 'attachments'])
        self.site.entry.name = '第十八届全国大学生数学竞赛'
        self.site.entry.save(update_fields=['name'])
        self.fetch.side_effect = self.success
        self.run_command()
        self.assertEqual(self.requested(), [self.urls[0]])
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.page_kind, 'index')
        child = OfficialNotice.objects.get(url=self.urls[0])
        self.assertEqual(child.page_kind, 'notice')
        self.assertEqual(child.status, 'pending')

    def test_dedicated_index_rule_attachment_retains_title_and_domain_checks(self):
        self.notice.page_kind = 'index'
        self.notice.attachments = [
            {'url': self.urls[0], 'title': '参赛章程'},
            {'url': self.urls[1], 'title': '报名回执'},
            {'url': self.urls[2], 'title': '校园地图'},
        ]
        self.notice.save(update_fields=['page_kind', 'attachments'])
        self.site.dedicated = True
        self.site.save(update_fields=['dedicated'])
        self.run_command()
        self.assertEqual(self.requested(), [self.urls[0]])
        self.assertEqual(self.fetch.call_args.args[0].allowed_hosts, ['contest.example'])

    def test_competitor_memorials_do_not_spend_budget_but_rules_remain(self):
        rejected = [
            ('2023/05/u-of-vienna-claimant.pdf', 'University of Vienna'),
            ('2023/05/u-of-vienna-respondent.pdf', 'University of Vienna'),
            ('memoranda/university-paper.pdf', 'University paper'),
            ('best-memorial-2023.pdf', 'Best written submission'),
            ('student-paper.pdf', 'Claimant Memorandum'),
        ]
        allowed = [
            ('rules-for-claimants.pdf', 'Rules for Claimants'),
            ('memoranda/registration.pdf', 'Registration'),
            ('invitation.pdf', 'Invitation'),
        ]
        self.notice.attachments = [
            {'url': 'https://contest.example/' + path, 'title': title}
            for path, title in rejected + allowed
        ]
        self.notice.save(update_fields=['attachments'])
        result = self.run_command(limit=3, max_per_notice=3)
        self.assertEqual(self.requested(), ['https://contest.example/' + path for path, _ in allowed])
        self.assertEqual(result[-1]['summary']['attempted'], 3)
        self.site.refresh_from_db()
        self.assertFalse(any('attachment:https://contest.example/' + path in self.site.page_attempts
                             for path, _ in rejected))
