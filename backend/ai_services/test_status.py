from django.test import SimpleTestCase, override_settings


class AssistantStatusTests(SimpleTestCase):
    @override_settings(AI_CHAT={'ENABLED': True, 'API_KEY': ''})
    def test_no_key_keeps_catalog_search_available(self):
        response = self.client.get('/api/v1/ai/status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'chat_configured': False, 'catalog_search': True})
        self.assertEqual(response['Cache-Control'], 'no-store')

    @override_settings(AI_CHAT={'ENABLED': True, 'PROVIDER': 'deepseek',
        'BASE_URL': 'https://api.deepseek.com', 'API_KEY': 'offline-private-token',
        'MODEL': 'configured-model'})
    def test_status_reports_only_capabilities_not_secrets(self):
        response = self.client.get('/api/v1/ai/status/')
        self.assertEqual(response.json(), {'chat_configured': True, 'catalog_search': True})
        self.assertNotContains(response, 'offline-private-token')
        self.assertNotContains(response, 'configured-model')
