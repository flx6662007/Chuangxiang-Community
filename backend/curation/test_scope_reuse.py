"""Package scope and cross-package ownership, without changing publication rules."""
import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from django.utils import timezone
from competition_catalog.models import CatalogBinding
from resources.models import Resource
from .models import DocumentRevision, ImportedObjectRevision, ImportedObject
from .package import PackageError, digest
from .importer import import_package, entity_state
from .tests import fixture, PackageTests


class ScopeTests(PackageTests):
    def test_explicit_scope_and_batch_boundary(self):
        data = fixture()
        data['catalog_scope'] = {'start': 90, 'end': 130, 'batch_size': 25}
        data['catalog'] = [{**data['catalog'][0], 'code': '2026090'},
                           {**data['catalog'][0], 'code': '2026115'}]
        for kind in ('competitions', 'resources', 'documents'):
            data[kind][0]['catalog_codes'] = ['2026090', '2026115']
        self.assertEqual(self.load(data, batches=[1])['catalog'][0]['code'], '2026090')
        self.assertEqual(self.load(data, batches=[2])['catalog'][0]['code'], '2026115')
        del data['catalog_scope']
        with self.assertRaises(PackageError):
            self.load(data)


class ReuseTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(email='reuse@tongji.edu.cn', password='test-only')
        self.loader = PackageTests().load
        self.old = fixture()
        import_package(self.loader(self.old), actor=self.actor, apply=True)
        self.new = copy.deepcopy(self.old)
        self.new.update(package_id='test-next', catalog_scope={'start': 90, 'end': 130, 'batch_size': 25})
        self.new['catalog'][0]['code'] = '2026128'
        self.new['competitions'] = []
        self.new['resources'] = []
        self.new['documents'][0].update(code='next-document', catalog_codes=['2026128'])
        self.new['references'] = {key: [dict(code=row['code'], package_id=self.old['package_id'],
                                           payload_hash=digest(row), catalog_codes=['2026128'])]
                                  for key, row in [('competitions', self.old['competitions'][0]),
                                                   ('resources', self.old['resources'][0])]}

    def test_append_binding_preserves_contents_and_old_reimport(self):
        sources = list(CompetitionSource.objects.order_by('pk').values())
        import_package(self.loader(self.new), actor=self.actor, apply=True)
        self.assertEqual(Competition.objects.count(), 1)
        self.assertEqual(Resource.objects.count(), 1)
        self.assertEqual(set(CatalogBinding.objects.values_list('entry__code', flat=True)), {'2026131', '2026128'})
        self.assertEqual(list(CompetitionSource.objects.order_by('pk').values()), sources)
        revisions = ImportedObjectRevision.objects.count()
        document_revisions = DocumentRevision.objects.count()
        import_package(self.loader(self.new), actor=self.actor, apply=True)
        import_package(self.loader(self.old), actor=self.actor, apply=True)
        self.assertEqual(ImportedObjectRevision.objects.count(), revisions)
        self.assertEqual(DocumentRevision.objects.count(), document_revisions)
        self.assertEqual(CatalogBinding.objects.count(), 2)

    def test_changed_reference_rolls_back_new_catalog(self):
        Competition.objects.update(summary='人工修改')
        with self.assertRaises(PackageError):
            import_package(self.loader(self.new), actor=self.actor, apply=True)
        self.assertFalse(CatalogBinding.objects.filter(entry__code='2026128').exists())
        from competition_catalog.models import CatalogEntry
        self.assertFalse(CatalogEntry.objects.filter(code='2026128').exists())

    def test_missing_dependency_is_rejected(self):
        self.new['references']['resources'][0]['code'] = 'absent-resource'
        self.new['documents'][0]['resource_codes'] = ['absent-resource']
        with self.assertRaisesRegex(PackageError, '复用对象缺失'):
            import_package(self.loader(self.new), actor=self.actor, apply=True)

    def test_published_reference_cannot_gain_a_binding(self):
        category = CompetitionTaxonomy.objects.create(code='test-category', kind='category', name='测试分类')
        Competition.objects.update(publication_status='published', category=category,
                                   published_at=timezone.now(), last_verified_at=timezone.now())
        obj = Competition.objects.get()
        ImportedObject.objects.filter(kind='competition', code=obj.code).update(state_hash=digest(entity_state('competition', obj)))
        with self.assertRaisesRegex(PackageError, '复用赛事已发布'):
            import_package(self.loader(self.new), actor=self.actor, apply=True)
