from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from ingestion.models import SourceConfig
from teams.demo_data import SOURCE_CODE
from teams.models import Application, Recruitment


@override_settings(DEBUG=True)
class RemainingSeedTests(TestCase):
    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label not in ['auth','contenttypes','sessions','admin']}

    def test_full_import_repeat_preserves_manual_edit_and_all_rows(self):
        call_command('seed_remaining_demo_data',stdout=StringIO())
        card=Recruitment.objects.get(code='demo-r2-card-1')
        paused=Application.objects.get(recruitment=card,applicant__email='cxdemo-r2-003@tongji.edu.cn')
        self.assertTrue(paused.is_paused)
        source=SourceConfig.objects.get(code=SOURCE_CODE);source.name+='（人工修改）';source.save()
        before=self.snapshot()
        output=StringIO();call_command('seed_remaining_demo_data',stdout=output)
        self.assertIn('SKIPPED',output.getvalue());self.assertEqual(self.snapshot(),before)

    @override_settings(DEBUG=False)
    def test_production_config_refuses_import(self):
        with self.assertRaises(CommandError):call_command('seed_remaining_demo_data',stdout=StringIO())
        self.assertEqual(SourceConfig.objects.count(),0)

    def test_failure_rolls_back_whole_batch(self):
        with patch('teams.demo_data.DemoBuilder.build_teams',side_effect=ValueError('synthetic failure')):
            with self.assertRaises(ValueError):call_command('seed_remaining_demo_data',stdout=StringIO())
        self.assertEqual(SourceConfig.objects.count(),0)
        from django.contrib.auth import get_user_model
        self.assertEqual(get_user_model().objects.count(),0)
