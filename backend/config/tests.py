from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class BootstrapTests(SimpleTestCase):
    # SimpleTestCase 禁止访问数据库，保证这些检查在建表前也能通过。
    def test_public_health_works_without_tables_and_with_a_stale_cookie(self):
        self.client.cookies['sessionid'] = 'stale-session-from-an-earlier-project'
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {'status': 'ok', 'service': 'chuangxiang-backend'},
        )

    def test_health_does_not_accept_writes(self):
        response = self.client.post(reverse('health'), {'status': 'changed'})
        self.assertEqual(response.status_code, 405)

    @override_settings(AUTH_USER_MODEL='auth.User')
    def test_initial_migration_is_blocked_until_user_model_is_configured(self):
        with self.assertRaisesMessage(CommandError, '用户模型尚未确定'):
            call_command('migrate', interactive=False, verbosity=0)
