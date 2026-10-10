import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import OperationalError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from common.portable_export import build_public_fixture, readonly_snapshot, validate_fixture_relations
from competition_catalog.models import CatalogBinding, CatalogEntry, OfficialSite
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from curation.models import DocumentLink, DocumentRevision, KnowledgeDocument
from information_library.competition_search import database_corpus
from research.models import ResearchOpportunity
from resources.models import Resource, ResourceCompetition, ResourceTaxonomy
from teams.models import RecruitmentOption


@override_settings(COMPETITION_CATALOG_ONLY=True, PUBLIC_RESEARCH_ENABLED=False)
class PortableExportTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(email='private-curator@tongji.edu.cn', password='source-test-only')
        self.catalog = CatalogEntry.objects.create(code='review01', name='公开目录', grade='A', levels='全国',
                                                   departments=['学院'], source_url='https://www.tongji.edu.cn/catalog')
        category = CompetitionTaxonomy.objects.create(code='portable-cat', kind='category', name='导出分类')
        self.competition = Competition.objects.create(
            code='portable-event', title='公开赛事', edition='2026', summary='公开简介', description='公开正文',
            category=category, publication_status='published', publication_method='direct', published_at=timezone.now(),
            created_by=self.actor, updated_by=self.actor, recruitment_enabled=True, recruitment_note='内部核验记录',
        )
        CatalogBinding.objects.create(entry=self.catalog, competition=self.competition, basis='内部归属说明')
        CompetitionSource.objects.create(competition=self.competition, source_type='official', source_name='学校',
                                         source_url='https://www.tongji.edu.cn/rules', is_primary=True)
        self.draft = Competition.objects.create(code='portable-draft', title='私有草稿', edition='2027')
        resource_category = ResourceTaxonomy.objects.create(code='portable-res-cat', name='学习资源分类', kind='category')
        self.resource = Resource.objects.create(code='portable-resource', title='公开资源', description='公开教程',
            category=resource_category, access_url='https://www.tongji.edu.cn/tutorial', publication_status='published',
            published_at=timezone.now(), created_by=self.actor)
        ResourceCompetition.objects.create(resource=self.resource, competition=self.competition)
        ResourceCompetition.objects.create(resource=self.resource, competition=self.draft)
        OfficialSite.objects.create(entry=self.catalog, url='https://www.tongji.edu.cn/',
            evidence_url='https://www.tongji.edu.cn/evidence', allowed_hosts=['www.tongji.edu.cn'],
            last_error='raw private task log', note='internal setup note', page_attempts={'private': 'log'})
        self.document = KnowledgeDocument.objects.create(code='portable-document', title='公开规则', review_status='published')
        old = DocumentRevision.objects.create(document=self.document, version=1, title='旧稿', body='旧私有记录',
            sources=[], created_by=self.actor, content_hash='old')
        body = '规则正文\nEmail: secret@example.com\n学校公开信息\nC:\\Users\\private\\source.txt\n电话：13812345678'
        sources = [{'id': 's1', 'title': '规则', 'url': 'https://www.tongji.edu.cn/rules', 'raw_path': 'private.txt'}]
        raw = {'id': 'event-2026', 'title': '公开规则', 'edition': '2026', 'content_hash': 'source-hash',
               'review_status': 'published', 'publication_status': 'published', 'fields': {}, 'sources': sources,
               'sections': [{'id': 'rules', 'heading': '参赛规则', 'text': body, 'evidence_ids': ['s1']}],
               'raw_task_log': 'private job trace', 'learning_resources': []}
        self.revision = DocumentRevision.objects.create(document=self.document, version=2, title='公开规则', edition='2026',
            body='## 参赛规则\n\n' + body, sources=sources, created_by=self.actor, content_hash='current',
            attachments=[{'path': 'private.pdf'}], metadata={'search_record': raw, 'package_root': 'C:\\private',
                'api_key': 'sk-private-credential-123456789', 'why_useful': '公开说明'})
        self.document.current_revision = self.revision
        self.document.save(update_fields=['current_revision'])
        DocumentLink.objects.create(revision=self.revision, competition=self.competition)
        DocumentLink.objects.create(revision=self.revision, catalog=self.catalog)
        DocumentLink.objects.create(revision=self.revision, resource=self.resource)
        KnowledgeDocument.objects.create(code='private-document', title='私有正文', review_status='draft', current_revision=None)
        self.research = ResearchOpportunity.objects.create(code='portable-research', title='公开科研',
            description='科研介绍', recruiting_entity='学校实验室', official_url='https://www.tongji.edu.cn/lab',
            publication_status='published', published_at=timezone.now(), application_email='researcher@tongji.edu.cn',
            verification_note='private internal research notes', created_by=self.actor)
        self.old_revision_id = old.pk
        self.public_options = [RecruitmentOption.objects.create(code='review-' + kind, kind=kind, name=name)
                               for kind, name in [('role', '开发角色'), ('skill', '开发技能'), ('campus', '测试校区')]]
        RecruitmentOption.objects.create(code='review-inactive', kind='skill', name='已停用技能', is_active=False)
        RecruitmentOption.objects.create(code='demo-r1-role', kind='role', name='【虚构样例】旧角色')

    def export(self):
        with readonly_snapshot():
            return build_public_fixture(demo_actor_id=9001)

    def test_allowlist_redaction_and_relations_preserve_only_current_public_content(self):
        fixture = self.export()
        by_id = {(row['model'], row['pk']): row['fields'] for row in fixture}
        self.assertNotIn(('competitions.competition', self.draft.pk), by_id)
        self.assertNotIn(('curation.documentrevision', self.old_revision_id), by_id)
        self.assertFalse(any(row['model'].startswith(('accounts.', 'research.')) for row in fixture))
        self.assertEqual(sum(row['model'] == 'resources.resourcecompetition' for row in fixture), 1)
        self.assertIsNone(by_id[('competitions.competition', self.competition.pk)]['created_by'])
        revision = by_id[('curation.documentrevision', self.revision.pk)]
        self.assertEqual(revision['created_by'], 9001)
        self.assertEqual(revision['sources'], revision['metadata']['search_record']['sources'])
        self.assertEqual(revision['attachments'], [])
        serialized = json.dumps(fixture, ensure_ascii=False, default=str)
        for forbidden in ('secret@example.com', 'private-curator@', '13812345678', 'raw_path', 'package_root',
                          'api_key', 'raw_task_log', '内部核验记录', '内部归属说明', 'private job trace', 'private.txt'):
            self.assertNotIn(forbidden, serialized)
        validate_fixture_relations(fixture, demo_actor_id=9001)
        # Export is a projection, not a model update.
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.created_by_id, self.actor.pk)
        self.assertIn('secret@example.com', self.revision.body)

    @override_settings(PUBLIC_RESEARCH_ENABLED=True)
    def test_research_gate_and_contacts(self):
        fixture = self.export()
        research = next(row['fields'] for row in fixture if row['model'] == 'research.researchopportunity')
        self.assertEqual(research['application_email'], '')
        self.assertEqual(research['verification_note'], '')
        self.assertIsNone(research['created_by'])

    def test_public_recruitment_dictionary_preserves_ids_without_team_activity(self):
        fixture = self.export()
        terms = [row for row in fixture if row['model'] == 'teams.recruitmentoption']
        self.assertEqual([row['pk'] for row in terms], [obj.pk for obj in self.public_options])
        self.assertEqual({row['fields']['kind'] for row in terms}, {'role', 'skill', 'campus'})
        self.assertTrue(all(set(row['fields']) == {'code', 'kind', 'name', 'is_active', 'sort_order'} for row in terms))
        self.assertFalse(any(row['model'].startswith('teams.') and row['model'] != 'teams.recruitmentoption' for row in fixture))
        self.assertEqual(RecruitmentOption.objects.count(), 5)

    def test_database_enforces_readonly_and_no_output_is_written_after_attempted_write(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'fixture.json'
            def attempt_write(**kwargs):
                self.competition.title = 'must not persist'
                self.competition.save(update_fields=['title'])
            with patch('curation.management.commands.export_portable_demo.build_public_fixture', side_effect=attempt_write):
                with self.assertRaises(OperationalError):
                    call_command('export_portable_demo', output=output, stdout=io.StringIO())
            self.assertFalse(output.exists())
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.title, '公开赛事')

    def test_loaddata_roundtrip_retains_ids_and_database_corpus(self):
        get_user_model().objects.create_user(pk=9001, email='synthetic@tongji.edu.cn', password='synthetic-test-only')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.json'
            call_command('export_portable_demo', output=path, demo_actor_id=9001, stdout=io.StringIO())
            manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
            self.assertFalse(manifest['contains_users'])
            self.assertEqual(manifest['bytes'], path.stat().st_size)
            call_command('loaddata', str(path), stdout=io.StringIO())
        options = self.client.get('/api/v1/recruitments/options/')
        self.assertEqual(options.status_code, 200)
        self.assertEqual({key: len(options.json()[key]) for key in ('roles', 'skills', 'campuses')},
                         {'roles': 1, 'skills': 1, 'campuses': 1})
        corpus = database_corpus()
        self.assertEqual(corpus['diagnostics'], [])
        self.assertEqual([record['id'] for record in corpus['records']], ['event-2026'])
        self.assertEqual(corpus['records'][0]['competition_id'], self.competition.pk)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.created_by_id, 9001)
