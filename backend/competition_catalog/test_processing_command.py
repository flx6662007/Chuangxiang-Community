"""真实提取器、管理命令、事务发布与游客 API 的隔离 PostgreSQL 串联。"""
from datetime import date
from io import StringIO
import hashlib
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from competitions.models import Competition, CompetitionSource
from competitions.services import withdraw_competition
from governance.models import AdminAction
from .extraction import extract_notice
from .models import CatalogBinding, CatalogEntry, CatalogExtraction, OfficialNotice, OfficialSite
from .publication import notice_snapshot


@override_settings(COMPETITION_CATALOG_ONLY=True, CATALOG_AUTO_PUBLISH=False, CATALOG_PUBLISH_ACTOR_ID=None)
class CatalogProcessingCommandTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('command.publisher@tongji.edu.cn', None, is_staff=True)
        self.actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='competitions',
            codename__in=['add_competition', 'change_competition', 'add_competitionsource']))
        self.entry = CatalogEntry.objects.create(code='2026111', name='全国大学生软件创新大赛',
            grade='A', levels='国家级', source_url='https://school.example/catalog', departments=[])
        self.site = OfficialSite.objects.create(entry=self.entry, url='https://contest.example/',
            evidence_url='https://school.example/notice', allowed_hosts=['contest.example'], dedicated=True)
        today = timezone.localdate()
        self.current = self.notice(today.year + 1)
        self.historical = self.notice(today.year - 1)

    def notice(self, year, *, suffix='', deadline=None, page_kind='notice'):
        title = f'{year}年全国大学生软件创新大赛报名通知'
        cutoff = deadline or date(year, 12, 31)
        body = '\n'.join([
            title, '一、主办单位', '测试教育学会',
            '二、参赛对象', '全日制普通高等学校在校大学生。本竞赛为个人赛。',
            '三、报名方式', '请在官方报名平台 https://contest.example/signup 提交软件作品。',
            '四、报名时间', f'报名截止：{cutoff.year}年{cutoff.month}月{cutoff.day}日。',
            '五、作品要求', '参赛作品由学生独立完成，展示面向真实问题的软件设计与开发成果。',
            '六、联系方式', '联系老师：测试联系人，电子邮箱：private@contest.example。',
        ])
        data = dict(title=title, body=body, attachments=[], source_published_on=str(date(year, 1, 1)))
        return OfficialNotice.objects.create(site=self.site, url=f'https://contest.example/{year}{suffix}',
            title=title, body=body, page_kind=page_kind, source_published_on=date(year, 1, 1),
            content_hash=hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest())

    def command(self, **kwargs):
        out = StringIO()
        call_command('process_catalog_notices', stdout=out, **kwargs)
        rows = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
        return rows[-1]['summary']

    def test_actual_parser_command_publish_repeat_and_public_api(self):
        for notice, expected in ((self.current, 'ready'), (self.historical, 'historical')):
            result = extract_notice(notice_snapshot(notice), today=timezone.localdate())
            self.assertEqual(result['disposition'], expected, result['errors'])
        before = self.client.get(reverse('competitions:list')).json()['count']
        first = self.command(publish=True, actor_id=self.actor.pk)
        self.assertEqual(first.get('published'), 2, first)
        self.assertEqual(CatalogExtraction.objects.filter(status='published').count(), 2)
        self.assertEqual(CatalogBinding.objects.count(), 2)
        self.assertEqual(CompetitionSource.objects.count(), 2)
        self.assertEqual(CatalogExtraction.objects.filter(reviewed_by=self.actor).count(), 2)
        times = list(Competition.objects.order_by('pk').values_list('published_at', 'updated_at', 'last_verified_at'))
        audit_count = AdminAction.objects.count()
        second = self.command(publish=True, actor_id=self.actor.pk)
        self.assertEqual(second.get('unchanged'), 2, second)
        self.assertNotIn('published', second)
        self.assertEqual(Competition.objects.count(), 2)
        self.assertEqual(CatalogExtraction.objects.count(), 2)
        self.assertEqual(AdminAction.objects.count(), audit_count)
        self.assertEqual(times, list(Competition.objects.order_by('pk').values_list('published_at', 'updated_at', 'last_verified_at')))
        public = self.client.get(reverse('competitions:list')).json()
        self.assertEqual(public['count'] - before, 1)
        self.assertEqual(public['results'][0]['deadline_status'], 'open')
        self.assertFalse(public['results'][0]['is_recruitment_open'])
        self.assertEqual(self.client.get(reverse('competitions:list'), {'time_status': 'all'}).json()['count'], 2)
        history = self.client.get(reverse('competitions:list'), {'time_status': 'expired'}).json()
        self.assertEqual(history['count'], 1)
        self.assertEqual(history['results'][0]['deadline_status'], 'closed')
        for competition in Competition.objects.all():
            detail = self.client.get(reverse('competitions:detail', args=[competition.pk])).json()
            self.assertEqual(len(detail['sources']), 1)
            self.assertTrue(detail['sources'][0]['source_url'].startswith('https://contest.example/'))
            self.assertNotIn('private@contest.example', json.dumps(detail, ensure_ascii=False))
            self.assertNotIn('reviewed_by', detail)
            self.assertEqual(detail['campus_arrangements'], '')
            self.assertIsNone(detail['campus_deadline'])

    def test_dry_run_is_read_only_even_with_publish_flag(self):
        summary = self.command(dry_run=True, publish=True)
        self.assertEqual(summary['processed'], 2)
        self.assertFalse(CatalogExtraction.objects.exists())
        self.assertFalse(Competition.objects.exists())
        self.assertFalse(AdminAction.objects.exists())

    def test_incomplete_updated_notice_blocks_complete_older_notice(self):
        year = timezone.localdate().year + 1
        updated = self.notice(year, suffix='-updated')
        updated.title += '【更新版】'
        updated.body = updated.title + '\n报名截止时间另行公布。'
        updated.source_published_on = date(year, 2, 1)
        payload = dict(title=updated.title, body=updated.body, attachments=[],
                       source_published_on=str(updated.source_published_on))
        updated.content_hash = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        updated.save()
        summary = self.command(publish=True, actor_id=self.actor.pk,
                               notice_id=[self.current.pk, updated.pk])
        self.assertEqual(summary.get('publication_blocked'), 1, summary)
        self.assertFalse(Competition.objects.exists())

    def test_publish_rejects_unprivileged_actor_before_any_write(self):
        student = get_user_model().objects.create_user('command.student@tongji.edu.cn', None)
        with self.assertRaisesMessage(CommandError, '维护账号'):
            self.command(publish=True, actor_id=student.pk)
        self.assertFalse(CatalogExtraction.objects.exists())
        self.assertFalse(Competition.objects.exists())

    def test_repeated_command_never_restores_withdrawn_event(self):
        self.command(publish=True, actor_id=self.actor.pk)
        current = Competition.objects.get(edition=self.current.title[:4])
        withdraw_competition(current.pk, actor=self.actor, reason='维护人员核查后下架')
        result = self.command(publish=True, actor_id=self.actor.pk)
        self.assertEqual(result.get('publication_blocked'), 1, result)
        current.refresh_from_db()
        self.assertEqual(current.publication_status, 'withdrawn')
        self.assertEqual(self.client.get(reverse('competitions:list')).json()['count'], 0)
        self.assertEqual(Competition.objects.count(), 2)

    def test_noisy_index_is_recorded_but_not_published(self):
        extra = self.notice(timezone.localdate().year, suffix='-index', page_kind='index')
        summary = self.command(publish=True, actor_id=self.actor.pk, notice_id=[extra.pk])
        self.assertEqual(summary.get('publication_blocked'), 1, summary)
        self.assertFalse(Competition.objects.exists())
        self.assertEqual(CatalogExtraction.objects.get().status, 'pending')
