"""显式指定交付包时，在隔离测试库验证本轮有效目录；不改资料包审核标记。"""
import copy
import os
import unittest
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import TestCase
from competition_catalog.models import CatalogEntry
from competitions.models import Competition
from resources.models import Resource
from .models import KnowledgeDocument, DocumentRevision
from .package import load_package
from .importer import import_package


@unittest.skipUnless(os.environ.get('CURATION_TEST_PACKAGE'), '未指定真实交付包')
class DeliveryTests(TestCase):
    def test_full_package_five_batches_repeat_and_drafts(self):
        actor=get_user_model().objects.create_superuser(email='delivery-test@tongji.edu.cn',password='Qatest-8294-corpus-only')
        path=Path(os.environ['CURATION_TEST_PACKAGE'])
        full=load_package(path)
        for batch in range(1,6):
            data=copy.deepcopy(load_package(path,[batch]))
            data['review']={'status':'approved','reviewed_by':'isolated-test-fixture','reviewed_on':'2026-10-02'}
            import_package(data,actor=actor,apply=True)
        before=DocumentRevision.objects.count()
        for batch in range(1,6):
            data=copy.deepcopy(load_package(path,[batch]))
            data['review']={'status':'approved','reviewed_by':'isolated-test-fixture','reviewed_on':'2026-10-02'}
            import_package(data,actor=actor,apply=True)
        self.assertEqual(DocumentRevision.objects.count(),before)
        self.assertEqual(CatalogEntry.objects.filter(code__in=[r['code'] for r in full['catalog']]).count(),len(full['catalog']))
        for number in full.get('work_scope',{}).get('deferred_numbers',[]):
            self.assertFalse(CatalogEntry.objects.filter(code=f'2026{number}').exists())
        self.assertEqual(Competition.objects.count(),len(full['competitions']))
        self.assertEqual(Resource.objects.count(),len(full['resources']))
        self.assertEqual(KnowledgeDocument.objects.count(),len(full['documents']))
        self.assertFalse(Competition.objects.exclude(publication_status='draft').exists())
        self.assertFalse(Competition.objects.filter(recruitment_enabled=True).exists())
        self.assertFalse(Resource.objects.exclude(publication_status='draft').exists())
        self.assertFalse(KnowledgeDocument.objects.exclude(review_status='draft').exists())
