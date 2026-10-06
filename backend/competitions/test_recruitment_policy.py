from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase
from .recruitment_policy import target


class RecruitmentPolicyTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026,10,6,12,tzinfo=ZoneInfo('Asia/Shanghai'))

    def result(self, **fields):
        return target({'id':'test','edition':'2026','fields':fields}, self.now)

    def test_unknown_deadline_allows_formation(self):
        self.assertTrue(self.result()['open'])
        self.assertEqual(self.result()['kind'], 'edition')

    def test_future_start_never_blocks_team_formation(self):
        self.assertTrue(self.result(registration_start='2026-11-01', registration_deadline='2026-12-01')['open'])

    def test_deadline_passed_opens_next_without_completion_proof(self):
        result=self.result(registration_deadline='2026-10-05')
        self.assertTrue(result['open']);self.assertEqual(result['kind'],'next_edition')
        self.assertIsNone(result['deadline'])

    def test_date_only_deadline_includes_whole_source_day(self):
        self.assertEqual(self.result(registration_deadline='2026-10-06')['kind'],'edition')

    def test_precise_cutoff_switches_at_instant(self):
        self.assertEqual(self.result(registration_deadline_at='2026-10-06T12:00:00+08:00')['kind'],'next_edition')
        self.assertEqual(self.result(registration_deadline_at='2026-10-06T12:00:01+08:00')['kind'],'edition')

    def test_completed_event_opens_next_even_without_deadline(self):
        self.assertEqual(self.result(event_completed_on='2026-10-01')['kind'],'next_edition')

    def test_submission_deadline_is_not_registration_deadline(self):
        self.assertEqual(self.result(submission_deadline='2025-01-01')['kind'],'edition')

    def test_individual_competition_keeps_its_participation_rules(self):
        self.assertFalse(self.result(participation_type='individual')['open'])
