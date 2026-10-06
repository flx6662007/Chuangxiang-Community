from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from competitions.recruitment_policy import target_code
from resources.models import Resource
from resources.selectors import filter_catalog, visible_resources
from .activation import activate_release
from .models import DocumentRevision
from .package import PackageError


class ActivationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor=get_user_model().objects.create_superuser('activation@tongji.edu.cn','isolated-test-only')
        CatalogEntry.objects.create(code='2026001',name='测试赛事',grade='A',levels='国家级',departments=['测试'],source_url='https://www.ccf.org.cn/activation-test/catalog')

    def setUp(self):
        self.now=datetime(2026,10,6,12,tzinfo=ZoneInfo('Asia/Shanghai'))
        self.record={'id':'test-edition','title':'测试赛事','edition':'2026','catalog_code':'2026001','catalog_codes':['2026001'],
            'fields':{'participation_type':'team','registration_deadline':'2026-10-07','team_size_max':4},
            'summary':'测试简介','content_hash':'a'*64,'level':'national',
            'sections':[{'text':'测试要求'}], 'sources':[{'title':'官方通知','url':'https://www.ccf.org.cn/activation-test/event'}],
            'learning_resources':[{'id':'guide','title':'学习教程','url':'https://www.ccf.org.cn/activation-test/guide','summary':'教程介绍'}]}

    def activate(self, records=None):
        return activate_release(records or [self.record],actor=self.actor,now=self.now)

    def test_import_publishes_resource_with_catalog_and_competition_links(self):
        self.activate()
        r=Resource.objects.get()
        self.assertEqual(r.publication_status,'published')
        self.assertEqual(r.competitions.count(),1)
        self.assertEqual(filter_catalog(visible_resources(),'2026001').get().pk,r.pk)
        before=DocumentRevision.objects.count()
        self.activate()
        self.assertEqual(Resource.objects.count(),1)
        self.assertEqual(DocumentRevision.objects.count(),before)

    def test_rollover_retains_previous_target_and_clears_old_eligibility(self):
        self.activate()
        previous=Competition.objects.get()
        self.now+=timedelta(days=3)
        self.activate()
        previous.refresh_from_db()
        self.assertFalse(previous.recruitment_enabled)
        nxt=Competition.objects.exclude(pk=previous.pk).get()
        self.assertEqual(nxt.edition,'下一届（官方届次未公布）')
        self.assertIsNone(nxt.team_size_max)
        self.assertIsNone(nxt.registration_deadline)
        self.assertTrue(nxt.is_recruitment_open)

    def test_manual_edit_is_preserved(self):
        self.activate()
        r=Resource.objects.get();r.title='维护人员改名';r.save()
        with self.assertRaises(PackageError):self.activate()
        self.assertEqual(Resource.objects.get().title,'维护人员改名')

    def test_resource_url_is_deduplicated_across_editions(self):
        other=deepcopy(self.record);other['id']='other-track'
        self.activate([self.record,other])
        self.assertEqual(Resource.objects.count(),1)
        self.assertEqual(Resource.objects.get().competitions.count(),2)

    def test_maintenance_rolls_over_once_and_preserves_resource_links(self):
        from .activation import refresh_team_targets
        self.activate()
        previous = Competition.objects.get()
        with patch('information_library.competition_search.database_corpus', return_value={'records':[self.record]}):
            result = refresh_team_targets(now=self.now+timedelta(days=3))
            self.assertEqual(result['next_edition_targets'],1)
            self.assertEqual(refresh_team_targets(now=self.now+timedelta(days=3)),{})
        previous.refresh_from_db()
        self.assertFalse(previous.recruitment_enabled)
        self.assertEqual(Resource.objects.get().competitions.get().edition,'下一届（官方届次未公布）')

    def test_unknown_deadline_can_create_a_recruitment_target(self):
        self.record['fields'] = {}
        self.activate()
        competition = Competition.objects.get()
        self.assertIsNone(competition.effective_recruitment_deadline)
        self.assertTrue(competition.is_recruitment_open)

    def test_official_cutoff_caps_manual_recruitment_deadline(self):
        self.activate()
        competition = Competition.objects.get()
        competition.recruitment_deadline = self.now+timedelta(days=10)
        self.assertEqual(competition.effective_recruitment_deadline,
                         datetime(2026,10,8,tzinfo=ZoneInfo('Asia/Shanghai')))
