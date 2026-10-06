import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
from django.core.management import call_command
from django.test import TestCase, override_settings
from information_library.public_selectors import research_cards
from information_library.selectors import collect_records
from ai_services.chat import chat

@override_settings(PUBLIC_RESEARCH_ENABLED=False)
class ResearchPauseTests(TestCase):
    def test_public_api_and_retrieval_are_closed(self):
        response=self.client.get('/api/v1/editorial/research/?page=99')
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['available'])
        self.assertEqual(response.json()['results'],[])
        self.assertEqual(research_cards(),[])
        self.assertEqual(collect_records(['research']),[])
        model=Mock()
        answer=chat([{'role':'user','content':'推荐本校实验室科研项目'}],client=model,details=True)
        self.assertEqual(answer['sources'],[])
        model.complete_text.assert_not_called()
    def test_six_existing_entries_are_archived_and_present_in_ninety_package(self):
        root=Path(__file__).resolve().parents[2]
        archive=json.loads((root/'docs/undergraduate-research/site-before-pause.json').read_text(encoding='utf-8'))
        package=json.loads((root/'docs/undergraduate-research/tongji-20261003-verified/科研卡片候选.json').read_text(encoding='utf-8'))
        self.assertEqual(len(archive['laboratories']),6)
        self.assertTrue({r['id'] for r in archive['laboratories']} <= {r['id'] for r in package['laboratories']})
    def test_independent_import_preview_repeat_and_newsletter_preservation(self):
        root=Path(__file__).resolve().parents[2]
        source=root/'docs/undergraduate-research/site-before-pause.json'
        with TemporaryDirectory() as folder:
            dest=Path(folder)/'editorial.json';dest.write_text(json.dumps({'laboratories':[],'newsletters':[{'id':'retained'}]}),encoding='utf-8')
            with patch('information_library.selectors.EDITORIAL_PATH',dest):
                call_command('import_research_materials',source=source,stdout=StringIO())
                self.assertEqual(json.loads(dest.read_text())['laboratories'],[])
                call_command('import_research_materials',source=source,apply=True,stdout=StringIO())
                first=dest.read_bytes()
                call_command('import_research_materials',source=source,apply=True,stdout=StringIO())
                self.assertEqual(first,dest.read_bytes())
                self.assertEqual(json.loads(first)['newsletters'],[{'id':'retained'}])
                self.assertEqual(research_cards(),[])
