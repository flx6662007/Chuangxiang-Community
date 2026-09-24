"""离线验证业务输入、来源依据与缺失字段，不调用模型或数据库。"""

from copy import deepcopy
from unittest.mock import Mock

from django.test import SimpleTestCase

from . import extract_notice, generate_newsletter
from .exceptions import AIConfigurationError, AIInputError, AIValidationError
from .validators import NOTICE_FIELDS


class AIServiceTests(SimpleTestCase):
    source = '示例竞赛由书院举办，报名截止2026年10月15日。'
    url = 'https://example.edu/notice/1'

    def notice(self):
        data = {name: {'value': None, 'evidence': None} for name in NOTICE_FIELDS}
        data['title'] = {'value': '示例竞赛', 'evidence': '示例竞赛由书院举办'}
        data['registration_deadline'] = {
            'value': '2026-10-15', 'evidence': '报名截止2026年10月15日',
        }
        return data

    def test_notice_preserves_source_and_missing_fields(self):
        client = Mock()
        client.complete_json.return_value = self.notice()
        result = extract_notice(self.source, self.url, client=client)
        self.assertEqual(result['source_url'], self.url)
        self.assertEqual(result['missing_fields'], ['organizer', 'eligibility', 'submission_deadline'])
        self.assertTrue(result['requires_review'])
        self.assertEqual(result['fields']['registration_deadline']['value'], '2026-10-15')

    def test_bad_input_does_not_call_model(self):
        client = Mock()
        for text, url in [('', self.url), ('x' * 20001, self.url), (self.source, 'file:///tmp/test')]:
            with self.subTest(text_length=len(text)), self.assertRaises(AIInputError):
                extract_notice(text, url, client=client)
        client.complete_json.assert_not_called()

    def test_notice_rejects_unfounded_and_malformed_results(self):
        for bad in [
            {'value': '另一竞赛', 'evidence': '示例竞赛由书院举办'},
            {'value': '示例竞赛', 'evidence': '不存在的原文'},
            {'value': None, 'evidence': '示例竞赛'},
            {'value': 123, 'evidence': '示例竞赛'},
        ]:
            data = self.notice()
            data['title'] = bad
            with self.subTest(bad=bad), self.assertRaises(AIValidationError):
                extract_notice(self.source, self.url, client=Mock(complete_json=Mock(return_value=data)))

    def test_deadline_cannot_invent_date_or_year(self):
        for value, evidence in [
            ('2027-10-15', '报名截止2026年10月15日'),
            ('2026-02-30', '2026年2月30日'),
            ('2026-10-15', '10月15日'),
        ]:
            data = self.notice()
            data['registration_deadline'] = {'value': value, 'evidence': evidence}
            with self.subTest(value=value, evidence=evidence), self.assertRaises(AIValidationError):
                extract_notice(self.source + evidence, self.url, client=Mock(complete_json=Mock(return_value=data)))

    def test_output_fields_must_be_explicit(self):
        missing = self.notice()
        del missing['title']
        extra = {**self.notice(), 'published': True}
        for data in [missing, extra, [], None]:
            with self.subTest(data=data), self.assertRaises(AIValidationError):
                extract_notice(self.source, self.url, client=Mock(complete_json=Mock(return_value=data)))

    def test_newsletter_uses_known_sources_and_remains_draft(self):
        item = {'id': 'evt-1', 'title': '示例竞赛', 'source_url': self.url, 'content': self.source}
        payload = {'title': '科创快讯', 'items': [
            {'source_id': 'evt-1', 'summary': '示例竞赛开始报名。', 'evidence': '示例竞赛由书院举办'},
        ]}
        result = generate_newsletter([item], client=Mock(complete_json=Mock(return_value=payload)))
        self.assertEqual(result['items'][0]['source_url'], self.url)
        self.assertEqual(result['items'][0]['title'], item['title'])
        self.assertTrue(result['requires_review'])

    def test_newsletter_rejects_unknown_or_forged_sources(self):
        item = {'id': 'evt-1', 'title': '示例竞赛', 'source_url': self.url, 'content': self.source}
        good = {'source_id': 'evt-1', 'summary': '快讯摘要', 'evidence': '示例竞赛'}
        for bad in [{**good, 'source_id': 'fake'}, {**good, 'evidence': '伪造引文'},
                    {**good, 'source_url': 'https://evil.example'}, {**good, 'summary': ''}]:
            with self.subTest(bad=bad), self.assertRaises(AIValidationError):
                generate_newsletter([item], client=Mock(complete_json=Mock(return_value={'title': '快讯', 'items': [bad]})))

    def test_newsletter_rejects_duplicate_input_before_call(self):
        item = {'id': 'evt-1', 'title': '示例竞赛', 'source_url': self.url, 'content': self.source}
        client = Mock()
        for data in [[], [item] * 2, [item] * 11, [{**item, 'content': ''}],
                     [{**item, 'content': 'x' * 20000}]]:
            with self.subTest(count=len(data)), self.assertRaises(AIInputError):
                generate_newsletter(deepcopy(data), client=client)
        client.complete_json.assert_not_called()

    def test_disabled_ai_does_not_require_credentials(self):
        with self.settings(AI_SERVICES={'ENABLED': False}), self.assertRaises(AIConfigurationError):
            extract_notice(self.source, self.url)
