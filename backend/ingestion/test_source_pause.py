"""停用来源立即阻止新轮网络访问及在途候选自动发布；人工复核仍校验权限。"""
from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from competitions.models import Competition
from .adapters import ADAPTERS
from .http import Page
from .models import FetchRun, ProcessingResult, SourceConfig, SourceVersion
from .services import accept_candidate, initialize_sources, record_extraction, source_mutex, sync_source
from .tests import AIC_HTML, AIC_URL


class SourcePauseTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            email='source-pause-test@tongji.edu.cn', password='test-password-only',
        )
        self.source = next(source for source in initialize_sources(actor=self.actor)
                           if source.adapter_key == 'aicomp')

    def record(self):
        run = FetchRun.objects.create(source=self.source, requested_url=AIC_URL, trigger='scheduled')
        page = Page(AIC_URL, AIC_HTML)
        result, _ = record_extraction(self.source, run, page, ADAPTERS['aicomp'].parse(page))
        return result

    def pause(self):
        SourceConfig.objects.filter(pk=self.source.pk).update(is_active=False)

    def assert_unpublished(self):
        self.assertEqual(Competition.objects.count(), 0)
        self.assertFalse(ProcessingResult.objects.filter(status='accepted').exists())

    def test_stale_source_stopped_before_client_or_fetch_run_creation(self):
        self.pause()
        self.assertTrue(self.source.is_active)  # 模拟命令提前读取的旧对象。
        with patch('ingestion.services.OfficialClient') as client:
            stats = sync_source(self.source, auto_accept=True)
        client.assert_not_called()
        self.assertEqual(stats['skipped'], 'inactive')
        self.assertEqual(stats['fetched'], 0)
        self.assertEqual(FetchRun.objects.count(), 0)
        self.assertEqual(SourceVersion.objects.count(), 0)
        self.assert_unpublished()

    def test_pause_when_mutex_is_acquired_is_seen_before_network(self):
        @contextmanager
        def pause_after_lock(source_id):
            with source_mutex(source_id) as acquired:
                self.assertTrue(acquired)
                self.pause()
                yield acquired

        client = Mock()
        with patch('ingestion.services.source_mutex', side_effect=pause_after_lock):
            stats = sync_source(self.source, auto_accept=True, client=client)
        client.get.assert_not_called()
        self.assertEqual(stats['skipped'], 'inactive')
        self.assertEqual(FetchRun.objects.count(), 0)
        self.assert_unpublished()

    def test_rules_rejects_paused_source_without_changing_pending_candidate(self):
        result = self.record()
        self.pause()
        with self.assertRaisesMessage(ValidationError, '来源已停用'):
            accept_candidate(result.pk, actor=self.actor, mode='rules', enable_recruitment=True)
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')
        self.assertIsNone(result.reviewed_at)
        self.assertIsNone(result.competition_id)
        self.assert_unpublished()

    def test_pause_during_fetch_leaves_inflight_result_pending(self):
        def get(url):
            if url == self.source.base_url:
                return Page(url, f'<a href="{AIC_URL}">2030AIC·“测试主题”算法主题赛赛题及竞赛规则</a>')
            self.assertEqual(url, AIC_URL)
            self.pause()  # 请求已发出，此时暂停应阻止返回结果自动发布。
            return Page(url, AIC_HTML)

        client = Mock()
        client.get.side_effect = get
        stats = sync_source(self.source, auto_accept=True, enable_recruitment=True, client=client)
        self.assertEqual(client.get.call_count, 2)
        self.assertEqual((stats['fetched'], stats['pending'], stats['accepted']), (1, 1, 0))
        result = ProcessingResult.objects.get()
        self.assertEqual(result.status, 'pending')
        self.assertIn('来源已停用', result.candidate['_review_reason'])
        self.assert_unpublished()

    def test_human_review_of_paused_source_still_requires_editor(self):
        result = self.record()
        self.pause()
        reader = get_user_model().objects.create_user(
            email='source-pause-reader@tongji.edu.cn', password='test-password-only', is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            accept_candidate(result.pk, actor=reader, mode='human')
        self.assert_unpublished()
        competition = accept_candidate(result.pk, actor=self.actor, mode='human')
        self.assertEqual(competition.publication_status, 'published')
        result.refresh_from_db()
        self.assertEqual((result.status, result.decision_mode), ('accepted', 'human'))
        self.assertEqual(result.reviewed_by_id, self.actor.pk)
        self.assertFalse(SourceConfig.objects.get(pk=self.source.pk).is_active)
