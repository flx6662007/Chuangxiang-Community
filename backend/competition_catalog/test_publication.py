"""发布边界测试；可信提取器另有真实文本专项，本文模拟其输出验证事务与权限。"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from competitions.services import save_competition, withdraw_competition
from governance.models import AdminAction
from .models import CatalogBinding, CatalogEntry, CatalogExtraction, OfficialNotice, OfficialSite
from .publication import notice_snapshot, persist_extraction, publish_extraction, reject_extraction


class CatalogPublicationTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('catalog.publisher@tongji.edu.cn', 'test-only-Complex-123',
                                                         is_staff=True)
        self.actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='competitions',
            codename__in=['add_competition', 'change_competition', 'add_competitionsource']))
        self.entry = CatalogEntry.objects.create(code='2026001', name='全国学生软件设计大赛', grade='A+',
            levels='国家级', departments=[], source_url='https://school.example/catalog')
        self.site = OfficialSite.objects.create(entry=self.entry, url='https://contest.example/',
            evidence_url='https://school.example/notice', allowed_hosts=['contest.example'], dedicated=True)
        self.notice = self.make_notice()
        self.extracted = self.make_extracted(self.notice)
        def extract_fixture(row, *, today):
            if row['id'] == self.notice.pk:
                return deepcopy(self.extracted)
            # 同目录的其他通知仍按各自年度提取；不能把下一届误认成本届修订。
            year = int(row['title'][:4])
            return self.make_extracted(
                SimpleNamespace(title=row['title'], body=row['body']),
                deadline=f'{year}-12-31',
                disposition='historical' if year < today.year else 'ready',
            )

        parser = SimpleNamespace(extract_notice=extract_fixture)
        self.parser_patch = patch.dict('sys.modules', {'competition_catalog.extraction': parser})
        self.parser_patch.start()
        self.addCleanup(self.parser_patch.stop)
        self.today_patch = patch('competition_catalog.publication.timezone.localdate', return_value=date(2026, 9, 29))
        self.today_patch.start()
        self.addCleanup(self.today_patch.stop)

    def make_notice(self, *, year=2026, deadline='12月31日', url='https://contest.example/notice',
                    page_kind='notice', body_extra='', current=True, published_on=None):
        title = f'{year}年全国学生软件设计大赛报名通知'
        body = '\n'.join([title, '主办单位：测试教育学会。', '参赛对象：全日制在校大学生。',
                          f'报名截止：{year}年{deadline}。', '报名方式：请到赛事官方网站查看。',
                          '鼓励学生完成软件作品，展示软件设计与开发成果。', body_extra])
        published = published_on or date(year, 1, 2)
        hashed = {'title': title, 'body': body, 'attachments': [], 'source_published_on': str(published)}
        return OfficialNotice.objects.create(site=self.site, url=url, title=title, body=body,
            page_kind=page_kind, source_published_on=published, is_current_version=current,
            content_hash=hashlib.sha256(json.dumps(hashed, ensure_ascii=False, sort_keys=True).encode()).hexdigest())

    def make_extracted(self, notice, *, deadline='2026-12-31', disposition='ready', version='test-rules-v1'):
        year = notice.title[:4]
        candidate = {
            'code': f'catalog-{self.entry.code}-{year}-softdesign', 'title': f'{year}年全国学生软件设计大赛',
            'edition': year, 'summary': '鼓励学生完成软件作品，展示软件设计与开发成果。',
            'description': '参赛对象：全日制在校大学生。\n报名方式：请到赛事官方网站查看。',
            'organizer': '测试教育学会', 'eligibility': '全日制在校大学生',
            'level': 'unknown', 'participation_type': 'unknown', 'team_size_min': None, 'team_size_max': None,
            'tracks': '', 'registration_method': '请到赛事官方网站查看。',
            'registration_url': '', 'registration_deadline': deadline, 'submission_deadline': None,
            'deadline_notes': '', 'category_code': 'catalog-software', 'category_name': '软件设计',
        }
        evidence = {'title': notice.title, 'edition': notice.title,
            'summary': candidate['summary'], 'description': candidate['description'],
            'organizer': '主办单位：测试教育学会。', 'eligibility': '参赛对象：全日制在校大学生。',
            'registration_method': '报名方式：请到赛事官方网站查看。',
            'registration_deadline': next(line for line in notice.body.splitlines() if '报名截止' in line)}
        return dict(candidate=candidate, evidence=evidence, missing_fields=['team_size_max'],
                    errors=[], disposition=disposition, rule_version=version)

    def persist(self):
        return persist_extraction(self.notice, self.extracted)

    def publish(self):
        return publish_extraction(self.persist().pk, self.actor)

    def test_persist_idempotence_and_model_immutable_result(self):
        result = self.persist()
        self.assertEqual(self.persist().pk, result.pk)
        self.assertEqual(CatalogExtraction.objects.count(), 1)
        result.candidate['title'] = '伪造标题'
        with self.assertRaises(ValidationError):
            result.full_clean()
        changed = deepcopy(self.extracted)
        changed['candidate']['organizer'] = '同版本修改'
        with self.assertRaisesMessage(ValidationError, '升级提取规则'):
            persist_extraction(self.notice, changed)

    def test_rules_publish_real_model_source_binding_and_actor(self):
        result = self.persist()
        competition = publish_extraction(result.pk, self.actor)
        result.refresh_from_db()
        self.assertEqual(competition.publication_status, 'published')
        self.assertEqual(competition.level, 'unknown')  # 学校 A+ 等级不变成全国赛事级别。
        self.assertFalse(competition.recruitment_enabled)
        self.assertEqual(result.reviewed_by, self.actor)
        self.assertEqual(result.decision_mode, 'rules')
        self.assertEqual(result.status, 'published')
        self.assertTrue(CatalogBinding.objects.filter(entry=self.entry, competition=competition).exists())
        source = competition.sources.get()
        self.assertTrue(source.is_primary)
        self.assertIsNotNone(source.last_verified_at)
        self.assertEqual(source.source_published_on, self.notice.source_published_on)
        self.assertEqual(source.fetched_at, self.notice.last_seen_at)
        self.assertTrue(AdminAction.objects.filter(competition=competition, action='publish').exists())

    def test_repeated_publish_does_not_refresh_publication_or_audit(self):
        result = self.persist()
        competition = publish_extraction(result.pk, self.actor)
        first = (competition.published_at, competition.updated_at, competition.last_verified_at)
        audit_count = AdminAction.objects.count()
        repeated = publish_extraction(result.pk, self.actor)
        self.assertEqual((repeated.published_at, repeated.updated_at, repeated.last_verified_at), first)
        self.assertEqual(AdminAction.objects.count(), audit_count)
        self.assertEqual(Competition.objects.count(), 1)

    def test_candidate_database_tampering_cannot_become_verified(self):
        result = self.persist()
        forged = deepcopy(result.candidate)
        forged['organizer'] = '伪造主办方'
        CatalogExtraction.objects.filter(pk=result.pk).update(candidate=forged)
        with self.assertRaisesMessage(ValidationError, '重新提取结果不一致'):
            publish_extraction(result.pk, self.actor)
        self.assertFalse(Competition.objects.exists())

    def test_changed_evidence_is_rejected_even_if_candidate_unchanged(self):
        result = self.persist()
        CatalogExtraction.objects.filter(pk=result.pk).update(evidence={'organizer': self.notice.body})
        with self.assertRaises(ValidationError):
            publish_extraction(result.pk, self.actor)
        self.assertFalse(CompetitionSource.objects.exists())

    def test_arbitrary_verified_flag_in_payload_rejected(self):
        self.extracted['candidate']['publication_status'] = 'published'
        with self.assertRaisesMessage(ValidationError, '不允许'):
            self.publish()
        self.assertFalse(Competition.objects.exists())

    def test_current_raw_hash_must_match_saved_snapshot(self):
        result = self.persist()
        OfficialNotice.objects.filter(pk=self.notice.pk).update(body=self.notice.body + '数据库被直接改写')
        with self.assertRaisesMessage(ValidationError, '哈希不符'):
            publish_extraction(result.pk, self.actor)

    def test_obsolete_notice_cannot_publish(self):
        result = self.persist()
        OfficialNotice.objects.filter(pk=self.notice.pk).update(is_current_version=False)
        self.make_notice(body_extra='新版本')
        with self.assertRaisesMessage(ValidationError, '新版本'):
            publish_extraction(result.pk, self.actor)

    def test_conflicting_current_versions_cannot_publish(self):
        result = self.persist()
        self.make_notice(body_extra='另一个当前版本')
        with self.assertRaisesMessage(ValidationError, '版本冲突'):
            publish_extraction(result.pk, self.actor)

    def test_disabled_site_and_entry_prevent_publish(self):
        result = self.persist()
        self.site.enabled = False
        self.site.save(update_fields=['enabled'])
        with self.assertRaisesMessage(ValidationError, '停用'):
            publish_extraction(result.pk, self.actor)
        self.site.enabled = True
        self.site.save(update_fields=['enabled'])
        self.entry.is_active = False
        self.entry.save(update_fields=['is_active'])
        with self.assertRaisesMessage(ValidationError, '停用'):
            publish_extraction(result.pk, self.actor)

    def test_index_snapshot_cannot_publish_even_if_parser_says_ready(self):
        self.notice.page_kind = 'index'
        self.notice.save(update_fields=['page_kind'])
        with self.assertRaisesMessage(ValidationError, '入口快照'):
            self.publish()

    def test_unapproved_notice_host_rejected(self):
        self.site.allowed_hosts = ['another.example']
        self.site.save(update_fields=['allowed_hosts'])
        with self.assertRaisesMessage(ValidationError, '官网范围'):
            self.publish()

    def test_permission_denied_to_student_and_missing_source_permission(self):
        result = self.persist()
        student = get_user_model().objects.create_user('ordinary.student@tongji.edu.cn', 'student-test-pass')
        with self.assertRaises(PermissionDenied):
            publish_extraction(result.pk, student)
        self.actor.user_permissions.remove(Permission.objects.get(
            content_type__app_label='competitions', codename='add_competitionsource'))
        actor = get_user_model().objects.get(pk=self.actor.pk)
        with self.assertRaises(PermissionDenied):
            publish_extraction(result.pk, actor)

    def test_evidence_snippet_must_occur_in_original(self):
        self.extracted['evidence']['organizer'] = '这一句不存在于真实原文'
        with self.assertRaisesMessage(ValidationError, '依据不在'):
            self.publish()

    def test_missing_deadline_blocks_automatic_and_human_publish(self):
        self.extracted['candidate']['registration_deadline'] = None
        result = self.persist()
        for mode in ('rules', 'human'):
            with self.subTest(mode=mode), self.assertRaisesMessage(ValidationError, '至少须有'):
                publish_extraction(result.pk, self.actor, mode)

    def test_review_or_error_results_stay_pending(self):
        self.extracted['disposition'] = 'review'
        result = self.persist()
        with self.assertRaisesMessage(ValidationError, '仍需核对'):
            publish_extraction(result.pk, self.actor, 'human')
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')

    def test_historical_exact_deadline_can_archive_without_recruitment(self):
        self.notice = self.make_notice(year=2025, url='https://contest.example/archive')
        self.extracted = self.make_extracted(self.notice, deadline='2025-12-31', disposition='historical')
        result = self.persist()
        competition = publish_extraction(result.pk, self.actor)
        result.refresh_from_db()
        self.assertEqual(competition.registration_deadline, date(2025, 12, 31))
        self.assertEqual(competition.edition, '2025')
        self.assertIn('历史赛事归档', result.review_note)
        self.assertFalse(competition.recruitment_enabled)

    def test_historical_future_deadline_conflict_blocks_publish(self):
        self.extracted['disposition'] = 'historical'
        with self.assertRaisesMessage(ValidationError, '未来截止冲突'):
            self.publish()

    def test_closed_registration_can_archive_with_future_submission(self):
        self.notice = self.make_notice(deadline='09月01日', url='https://contest.example/closed-registration',
                                       body_extra='作品截止：2026年12月31日。')
        self.extracted = self.make_extracted(self.notice, deadline='2026-09-01', disposition='historical')
        self.extracted['candidate']['submission_deadline'] = '2026-12-31'
        self.extracted['evidence']['submission_deadline'] = '作品截止：2026年12月31日。'
        competition = self.publish()
        self.assertEqual(competition.registration_deadline, date(2026, 9, 1))
        self.assertEqual(competition.submission_deadline, date(2026, 12, 31))
        self.assertFalse(competition.recruitment_enabled)

    def test_date_only_deadline_today_is_not_historical(self):
        self.notice = self.make_notice(deadline='09月29日', url='https://contest.example/today')
        self.extracted = self.make_extracted(self.notice, deadline='2026-09-29', disposition='historical')
        with self.assertRaisesMessage(ValidationError, '当天'):
            self.publish()

    def test_new_year_same_url_is_separate_and_keeps_old_event(self):
        first = self.publish()
        OfficialNotice.objects.filter(pk=self.notice.pk).update(is_current_version=False)
        self.notice = self.make_notice(year=2027)
        self.extracted = self.make_extracted(self.notice, deadline='2027-12-31')
        second = self.publish()
        first.refresh_from_db()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.edition, '2026')
        self.assertEqual(second.edition, '2027')

    def test_updated_notice_does_not_overwrite_accepted_event(self):
        competition = self.publish()
        OfficialNotice.objects.filter(pk=self.notice.pk).update(is_current_version=False)
        self.notice = self.make_notice(deadline='11月30日')
        self.extracted = self.make_extracted(self.notice, deadline='2026-11-30')
        with self.assertRaisesMessage(ValidationError, '不自动覆盖'):
            self.publish()
        competition.refresh_from_db()
        self.assertEqual(competition.registration_deadline, date(2026, 12, 31))
        self.assertEqual(CatalogExtraction.objects.filter(status='pending').count(), 1)

    def test_changed_official_publication_date_stays_pending(self):
        competition = self.publish()
        OfficialNotice.objects.filter(pk=self.notice.pk).update(is_current_version=False)
        self.notice = self.make_notice(published_on=date(2026, 8, 1))
        self.extracted = self.make_extracted(self.notice)
        with self.assertRaisesMessage(ValidationError, '发布日期发生变化'):
            self.publish()
        self.assertEqual(competition.sources.get().source_published_on, date(2026, 1, 2))

    def test_new_rule_keeps_manual_changes_and_withdrawal(self):
        competition = self.publish()
        competition.summary = '管理员修订说明'
        save_competition(competition, actor=self.actor)
        self.extracted['rule_version'] = 'test-rules-v2'
        with self.assertRaisesMessage(ValidationError, '不自动覆盖'):
            self.publish()
        competition.refresh_from_db()
        self.assertEqual(competition.summary, '管理员修订说明')
        withdraw_competition(competition.pk, actor=self.actor, reason='人工下架测试')
        old = CatalogExtraction.objects.get(status='published')
        self.extracted['rule_version'] = old.rule_version
        with self.assertRaisesMessage(ValidationError, '不自动恢复'):
            publish_extraction(old.pk, self.actor)
        competition.refresh_from_db()
        self.assertEqual(competition.publication_status, 'withdrawn')

    def test_atomic_rollback_after_source_creation(self):
        result = self.persist()
        with patch('competition_catalog.publication.publish_competition', side_effect=ValidationError('中途失败')):
            with self.assertRaises(ValidationError):
                publish_extraction(result.pk, self.actor)
        self.assertFalse(Competition.objects.exists())
        self.assertFalse(CompetitionSource.objects.exists())
        self.assertFalse(CompetitionTaxonomy.objects.exists())
        self.assertFalse(AdminAction.objects.exists())
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')

    def test_category_disabled_not_reenabled_by_publication(self):
        CompetitionTaxonomy.objects.create(code='catalog-software', name='软件设计', kind='category', is_active=False)
        with self.assertRaisesMessage(ValidationError, '停用'):
            self.publish()

    def test_rejection_retains_snapshot_and_prevents_republication(self):
        result = self.persist()
        reject_extraction(result.pk, actor=self.actor)
        with self.assertRaisesMessage(ValidationError, '已拒绝'):
            publish_extraction(result.pk, self.actor)
        result.refresh_from_db()
        self.assertEqual(result.candidate, self.extracted['candidate'])
        self.assertEqual(result.reviewed_by, self.actor)

    def test_notice_snapshot_uses_source_date_not_fetch_time(self):
        snapshot = notice_snapshot(self.notice)
        self.assertEqual(snapshot['published_on'], '2026-01-02')
        self.assertEqual(snapshot['hash'], self.notice.content_hash)
        self.assertNotIn('teacher', snapshot)

    def admin_login(self):
        self.actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='competition_catalog',
            codename__in=['view_catalogextraction', 'change_catalogextraction']))
        self.client.force_login(self.actor)

    def test_admin_ordinary_change_post_denied_and_snapshot_preserved(self):
        result = self.persist()
        self.admin_login()
        response = self.client.post(reverse('admin:competition_catalog_catalogextraction_change', args=[result.pk]),
                                    {'candidate': '{"title":"伪造"}', 'status': 'published', '_save': '保存'})
        self.assertEqual(response.status_code, 403)
        result.refresh_from_db()
        self.assertEqual(result.status, 'pending')
        self.assertEqual(result.candidate, self.extracted['candidate'])

    def test_admin_special_action_uses_controlled_service(self):
        result = self.persist()
        self.admin_login()
        response = self.client.post(reverse('admin:competition_catalog_catalogextraction_changelist'),
            {'action': 'publish_selected', '_selected_action': [result.pk], 'index': '0'})
        self.assertEqual(response.status_code, 302)
        result.refresh_from_db()
        self.assertEqual(result.status, 'published')
        self.assertEqual(result.decision_mode, 'human')
        self.assertFalse(result.competition.recruitment_enabled)
