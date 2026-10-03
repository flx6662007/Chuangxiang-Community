"""Real 90--130 delivery acceptance with the preceding package as a dependency."""
import copy
import os
import unittest
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import TestCase
from competition_catalog.models import CatalogBinding, CatalogEntry
from competitions.models import Competition, CompetitionSource
from resources.models import Resource
from .models import DocumentRevision, KnowledgeDocument, ImportedObjectRevision
from .package import load_package
from .importer import import_package


@unittest.skipUnless(os.environ.get('CURATION_RESEARCH_PACKAGE'), 'Explicit research package required')
class ResearchDeliveryTests(TestCase):
    def test_two_batches_repeat_reuse_and_historical_rules(self):
        actor = get_user_model().objects.create_superuser(email='research-test@tongji.edu.cn', password='test-only')
        old = load_package(Path(os.environ['CURATION_TEST_PACKAGE']))
        old['review'] = {'status': 'approved', 'reviewed_by': 'isolated test fixture', 'reviewed_on': '2026-10-03'}
        import_package(old, actor=actor, apply=True)
        source_snapshot = list(CompetitionSource.objects.order_by('pk').values())
        path = Path(os.environ['CURATION_RESEARCH_PACKAGE'])
        full = load_package(path)
        for batch in (1, 2):
            data = copy.deepcopy(load_package(path, [batch]))
            data['review'] = old['review']
            import_package(data, actor=actor, apply=True)
        self.assertEqual(CatalogEntry.objects.filter(code__in=[r['code'] for r in full['catalog']]).count(), 41)
        self.assertEqual(Competition.objects.count(), len(old['competitions']) + len(full['competitions']))
        self.assertEqual(Resource.objects.count(), len(old['resources']) + len(full['resources']))
        self.assertEqual(KnowledgeDocument.objects.count(), len(old['documents']) + len(full['documents']))
        self.assertFalse(CatalogBinding.objects.filter(entry__code='2026118').exists())
        first = set(CatalogBinding.objects.filter(entry__code='2026122').values_list('competition_id', flat=True))
        self.assertEqual(first, set(CatalogBinding.objects.filter(entry__code='2026123').values_list('competition_id', flat=True)))
        self.assertEqual(set(CatalogBinding.objects.filter(entry__code='2026128').values_list('competition_id', flat=True)),
                         set(CatalogBinding.objects.filter(entry__code='2026135').values_list('competition_id', flat=True)))
        self.assertTrue(Competition.objects.filter(code='curated-c94-2022-2', edition__startswith='2022').exists())
        revisions = (DocumentRevision.objects.count(), ImportedObjectRevision.objects.count())
        repeated = copy.deepcopy(full)
        repeated['review'] = old['review']
        import_package(repeated, actor=actor, apply=True)
        import_package(old, actor=actor, apply=True)
        self.assertEqual(revisions, (DocumentRevision.objects.count(), ImportedObjectRevision.objects.count()))
        self.assertEqual(source_snapshot, list(CompetitionSource.objects.filter(pk__in=[s['id'] for s in source_snapshot]).order_by('pk').values()))
        self.assertFalse(Competition.objects.exclude(publication_status='draft').exists())
        self.assertFalse(Competition.objects.filter(recruitment_enabled=True).exists())
        self.assertFalse(Resource.objects.exclude(publication_status='draft').exists())
        self.assertFalse(KnowledgeDocument.objects.exclude(review_status='draft').exists())
