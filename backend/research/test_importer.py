from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from information_library.public_selectors import research_cards
from .importer import import_cards
from .models import ResearchOpportunity, ResearchRevision


@override_settings(PUBLIC_RESEARCH_ENABLED=True)
class ResearchDatabaseImportTests(TestCase):
    def row(self, identity='research-cn-example', **changes):
        return {'id': identity, 'title': '计算实验室', 'unit': '示例高校',
                'summary': '计算与生命科学交叉研究', 'participation': '',
                'evidenceNote': '实验室介绍，未提取招募信息', 'date': '2026-09-01',
                'verifiedOn': '2026-10-07', 'sourceUrl': f'https://example.edu.cn/{identity}', **changes}

    def test_preview_rolls_back_and_published_card_preserves_fields(self):
        row = self.row()
        report = import_cards([row], publish=True)
        self.assertEqual(report['created'], 1)
        self.assertFalse(ResearchOpportunity.objects.exists())
        self.assertFalse(ResearchRevision.objects.exists())
        import_cards([row], apply=True, publish=True)
        card = next(c for c in research_cards() if c['sourceUrl'] == row['sourceUrl'])
        for field in ('title', 'unit', 'summary', 'participation', 'evidenceNote', 'date', 'verifiedOn'):
            self.assertEqual(card[field], row[field])
        self.assertEqual(ResearchRevision.objects.count(), 1)

    def test_repeat_and_versioned_update_retain_other_rows(self):
        import_cards([self.row(), self.row('kept')], apply=True, publish=True)
        published = ResearchOpportunity.objects.get(code='research-cn-example').published_at
        self.assertEqual(import_cards([self.row()], apply=True, publish=True)['unchanged'], 1)
        self.assertEqual(ResearchRevision.objects.count(), 2)
        result = import_cards([self.row(title='新的实验室名称')], apply=True, publish=True)
        obj = ResearchOpportunity.objects.get(code='research-cn-example')
        self.assertEqual(result['retained'], 1)
        self.assertEqual(obj.published_at, published)
        self.assertEqual(obj.content_version, 2)
        self.assertEqual(ResearchRevision.objects.count(), 3)

    def test_conflict_and_invalid_later_row_rollback_whole_batch(self):
        import_cards([self.row()], apply=True)
        with self.assertRaises(ValidationError):
            import_cards([self.row('second', sourceUrl=self.row()['sourceUrl'] + '/')], apply=True)
        with self.assertRaises(ValidationError):
            import_cards([self.row('valid'), self.row('bad', summary='')], apply=True, publish=True)
        self.assertEqual(ResearchOpportunity.objects.count(), 1)

    def test_draft_and_withdrawn_are_not_implicitly_published(self):
        import_cards([self.row()], apply=True)
        obj = ResearchOpportunity.objects.get()
        self.assertEqual(obj.publication_status, 'draft')
        obj.publication_status, obj.published_at = 'withdrawn', timezone.now()
        obj.withdrawal_reason = '待重新核实'
        obj.full_clean()
        obj.save()
        result = import_cards([self.row()], apply=True, publish=True)
        obj.refresh_from_db()
        self.assertEqual(result['withdrawn_preserved'], 1)
        self.assertEqual(obj.publication_status, 'withdrawn')

    def test_structured_details_are_versioned_and_bad_profile_rolls_back(self):
        profiles = {'research-cn-example': {'direction': '合成生物学', 'recruitment': {
            'roles': '科研助理', 'eligibility': '相关专业本科学历', 'commitment': '可兼职'},
            'hasRecruitmentSource': True}}
        import_cards([self.row()], profiles=profiles, apply=True, publish=True)
        obj = ResearchOpportunity.objects.get()
        self.assertEqual(obj.card_details, profiles[obj.code])
        self.assertEqual(ResearchRevision.objects.get().snapshot['card_details'], obj.card_details)
        self.assertEqual(import_cards([self.row()], profiles=profiles, apply=True)['unchanged'], 1)
        with self.assertRaises(ValidationError):
            import_cards([self.row()], profiles={obj.code: {'recruitment': {'internalNote': 'secret'}}}, apply=True)
        obj.refresh_from_db()
        self.assertEqual(obj.content_version, 1)

    def test_field_links_survive_import_api_and_revision_and_reject_unsafe_links(self):
        row = self.row()
        links = {'summary': [{'label': '研究介绍', 'url': 'https://example.edu.cn/research'}],
                 'roles': [{'label': '招募详情', 'url': 'https://example.edu.cn/join'}]}
        profile = {'fieldLinks': links, 'recruitment': {'roles': '研究生'}, 'hasRecruitmentSource': True}
        import_cards([row], profiles={row['id']: profile}, apply=True, publish=True)
        obj = ResearchOpportunity.objects.get()
        card = next(c for c in research_cards() if c['sourceUrl'] == row['sourceUrl'])
        self.assertEqual(card['details']['fieldLinks'], links)
        self.assertEqual(ResearchRevision.objects.get().snapshot['card_details']['fieldLinks'], links)
        self.assertEqual(import_cards([row], profiles={row['id']: profile}, apply=True)['unchanged'], 1)
        for url in ('javascript:alert(1)', 'http://127.0.0.1/private', 'https://user:password@example.edu.cn/'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                import_cards([row], profiles={row['id']: {'fieldLinks': {'summary': [{'label': '介绍', 'url': url}]}}}, apply=True)
        obj.refresh_from_db()
        self.assertEqual(obj.card_details, profile)
        self.assertEqual(obj.content_version, 1)
