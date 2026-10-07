import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
from django.core.management import call_command
from django.core.management.base import CommandError
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


class ResearchMergeTests(TestCase):
    def card(self, identity, **overrides):
        return {'id': identity, 'title': '实验室介绍', 'unit': '高校',
                'summary': '研究方向', 'participation': '', 'evidenceNote': '',
                'date': '', 'verifiedOn': '2026-10-07',
                'sourceUrl': f'https://example.edu.cn/{identity}', **overrides}

    def run_import(self, folder, current, incoming, **options):
        dest = Path(folder) / 'target.json'
        source = Path(folder) / 'source.json'
        dest.write_text(json.dumps(current), encoding='utf-8')
        source.write_text(json.dumps(incoming), encoding='utf-8')
        output = StringIO()
        call_command('import_research_materials', source=source, target=dest, stdout=output, **options)
        return json.loads(output.getvalue()), json.loads(dest.read_text(encoding='utf-8'))

    def test_merge_retains_other_rows_order_and_publication_controls(self):
        first = self.card('first', publication_status='draft')
        kept = self.card('kept')
        with TemporaryDirectory() as folder:
            report, result = self.run_import(folder,
                {'laboratories': [first, kept], 'newsletters': [{'id': 'news'}]},
                {'laboratories': [self.card('first', title='新标题'), self.card('new')]}, apply=True)
        self.assertEqual([r['id'] for r in result['laboratories']], ['first', 'kept', 'new'])
        self.assertEqual(result['laboratories'][0]['publication_status'], 'draft')
        self.assertEqual(result['newsletters'], [{'id': 'news'}])
        self.assertEqual((report['added'], report['updated'], report['retained']), (1, 1, 1))

    def test_duplicate_source_conflict_is_previewed_and_apply_is_atomic(self):
        current = {'laboratories': [self.card('one')]}
        incoming = {'laboratories': [self.card('two', sourceUrl='https://example.edu.cn/one/')]}
        with TemporaryDirectory() as folder:
            report, result = self.run_import(folder, current, incoming)
            self.assertTrue(report['conflicts'])
            self.assertEqual(result, current)
            with self.assertRaises(CommandError):
                self.run_import(folder, current, incoming, apply=True)
            self.assertEqual(json.loads((Path(folder) / 'target.json').read_text()), current)

    def test_national_scope_refuses_mixing_with_unscoped_archive(self):
        with TemporaryDirectory() as folder:
            report, result = self.run_import(folder,
                {'laboratories': [self.card('archive')]},
                {'scope': 'national', 'laboratories': [self.card('research-cn-example')]})
            self.assertTrue(report['conflicts'])
            self.assertEqual(len(result['laboratories']), 1)
            with self.assertRaises(CommandError):
                self.run_import(folder, result,
                    {'scope': 'national', 'laboratories': [self.card('research-cn-example')]}, apply=True)

    def test_new_independent_target_and_repeat(self):
        with TemporaryDirectory() as folder:
            source, target = Path(folder) / 'source.json', Path(folder) / 'new' / 'target.json'
            source.write_text(json.dumps({'scope': 'national', 'laboratories': [self.card('research-cn-example')]}))
            call_command('import_research_materials', source=source, target=target, stdout=StringIO())
            self.assertFalse(target.exists())
            call_command('import_research_materials', source=source, target=target, apply=True, stdout=StringIO())
            first = target.read_bytes()
            output = StringIO()
            call_command('import_research_materials', source=source, target=target, apply=True, stdout=output)
            self.assertEqual(first, target.read_bytes())
            self.assertTrue(json.loads(output.getvalue())['unchanged'])

    def test_national_target_refuses_unscoped_incoming_archive(self):
        current = {'scope': 'national', 'laboratories': [self.card('research-cn-example')]}
        with TemporaryDirectory() as folder:
            report, result = self.run_import(folder, current, {'laboratories': [self.card('archive')]})
            self.assertTrue(report['conflicts'])
            self.assertEqual(result, current)
            with self.assertRaises(CommandError):
                self.run_import(folder, current, {'laboratories': [self.card('archive')]}, apply=True)

    def test_invalid_source_and_existing_duplicate_ids_do_not_write(self):
        for bad in [self.card('bad', sourceUrl='javascript:alert(1)'), self.card('bad', date='2026-15-01')]:
            with TemporaryDirectory() as folder, self.assertRaises(CommandError):
                self.run_import(folder, {'laboratories': []}, {'laboratories': [bad]}, apply=True)
        with TemporaryDirectory() as folder, self.assertRaises(CommandError):
            self.run_import(folder, {'laboratories': [self.card('same'), self.card('same')]},
                            {'laboratories': [self.card('new')]}, apply=True)
