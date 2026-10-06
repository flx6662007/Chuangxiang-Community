"""验证内测入口、生产校验隔离、静态文件边界和 CSRF，不读取真实数据库。"""

import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import InterfaceError, OperationalError
from django.test import Client, SimpleTestCase, override_settings

from .private_beta import (
    GATE_COOKIE_AGE, GATE_COOKIE_NAME,
    beta_maintenance_loop, configure_local_admin, run_beta_maintenance_once,
    start_beta_maintenance, validate_private_beta_environment, wait_for_beta_database,
)


ORIGIN = 'https://beta-example.trycloudflare.com'
USERNAME = 'invited-test'
PASSWORD = 'private-beta-test-password-123456789'
BASIC = 'Basic ' + base64.b64encode(f'{USERNAME}:{PASSWORD}'.encode()).decode()


class PrivateBetaDatabaseReadinessTests(SimpleTestCase):
    def setUp(self):
        self.clock = 0
        self.sleeps = []
        self.config = patch('config.private_beta.settings', PRIVATE_BETA=True,
                            DATABASES={'default': {'NAME': 'chuangxiang_beta_readiness'}})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.database = patch('config.private_beta.connection')
        self.conn = self.database.start()
        self.addCleanup(self.database.stop)
        self.conn.vendor = 'postgresql'
        self.conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ('chuangxiang_beta_readiness',)
        self.monotonic = patch('config.private_beta.time.monotonic', side_effect=lambda: self.clock)
        self.monotonic.start()
        self.addCleanup(self.monotonic.stop)
        self.sleep = patch('config.private_beta.time.sleep', side_effect=self.advance)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def advance(self, seconds):
        self.sleeps.append(seconds)
        self.clock += seconds

    def test_ready_database_must_match_and_connection_is_closed(self):
        wait_for_beta_database()
        self.conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with('SELECT current_database()')
        self.conn.close.assert_called_once()
        self.assertEqual(self.sleeps, [])

    def test_recovery_is_retried_without_sleeping_in_the_test(self):
        cursor = self.conn.cursor.return_value
        self.conn.cursor.side_effect = [OperationalError('private-connection-data'), InterfaceError('private-driver-data'), cursor]
        wait_for_beta_database()
        self.assertEqual(self.sleeps, [2, 2])
        self.assertEqual(self.conn.close.call_count, 3)

    def test_timeout_is_bounded_and_driver_error_is_redacted(self):
        self.conn.cursor.side_effect = OperationalError('private-host-user-password')
        with self.assertRaisesMessage(ImproperlyConfigured, '等待内测数据库就绪超时') as result:
            wait_for_beta_database(timeout=3)
        self.assertEqual(self.clock, 3)
        self.assertEqual(self.sleeps, [2, 1])
        self.assertEqual(self.conn.cursor.call_count, 2)
        self.assertEqual(self.conn.close.call_count, 2)
        self.assertNotIn('private-host-user-password', str(result.exception))

    def test_recovery_can_exceed_old_thirty_second_startup_window(self):
        cursor = self.conn.cursor.return_value
        self.conn.cursor.side_effect = [OperationalError('database recovering') for _ in range(23)] + [cursor]
        wait_for_beta_database()
        self.assertEqual(self.clock, 46)
        self.assertEqual(self.conn.close.call_count, 24)

    def test_wrong_actual_database_fails_immediately(self):
        self.conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ('regular_database',)
        with self.assertRaisesMessage(ImproperlyConfigured, '实际连接的数据库与内测配置不一致'):
            wait_for_beta_database()
        self.assertEqual(self.sleeps, [])
        self.conn.close.assert_called_once()

    def test_non_beta_regular_name_and_non_postgres_do_not_connect(self):
        for enabled, name, vendor in ((False, 'chuangxiang_beta_readiness', 'postgresql'),
                                      (True, 'regular_database', 'postgresql'),
                                      (True, 'chuangxiang_beta_readiness', 'sqlite')):
            with self.subTest(enabled=enabled, name=name, vendor=vendor), patch(
                'config.private_beta.settings', PRIVATE_BETA=enabled, DATABASES={'default': {'NAME': name}},
            ):
                self.conn.vendor = vendor
                with self.assertRaisesMessage(ImproperlyConfigured, '仅允许独立 PostgreSQL 内测库'):
                    wait_for_beta_database()
        self.conn.cursor.assert_not_called()

    def test_unexpected_failure_is_redacted_and_connection_closed(self):
        self.conn.cursor.side_effect = RuntimeError('private-connection-detail')
        with self.assertRaisesMessage(ImproperlyConfigured, '内测数据库检查失败') as result:
            wait_for_beta_database()
        self.assertNotIn('private-connection-detail', str(result.exception))
        self.assertEqual(self.sleeps, [])
        self.conn.close.assert_called_once()


class PrivateBetaSettingsTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.values = {
            'PRIVATE_BETA_ORIGIN': ORIGIN,
            'PRIVATE_BETA_USERNAME': USERNAME, 'PRIVATE_BETA_PASSWORD': PASSWORD,
            'PRIVATE_BETA_SECRET_KEY': 'private-test-key-' * 5,
            'PRIVATE_BETA_DB_NAME': 'chuangxiang_beta_unittest',
            'PRIVATE_BETA_DB_USER': 'beta_test_user', 'PRIVATE_BETA_DB_PASSWORD': 'isolated-test-secret',
            'PRIVATE_BETA_STATE_DIR': self.directory.name,
        }

    def test_requires_every_private_credential(self):
        for name in ('PRIVATE_BETA_ORIGIN', 'PRIVATE_BETA_USERNAME', 'PRIVATE_BETA_PASSWORD',
                     'PRIVATE_BETA_SECRET_KEY', 'PRIVATE_BETA_DB_USER', 'PRIVATE_BETA_DB_PASSWORD'):
            with self.subTest(name=name):
                values = {key: value for key, value in self.values.items() if key != name}
                with self.assertRaises(ImproperlyConfigured):
                    validate_private_beta_environment(values)

    def test_requires_independent_named_database(self):
        for name in ('postgres', 'chuangxiang', 'chuangxiang_beta_', 'chuangxiang_beta_../../source'):
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):
                validate_private_beta_environment({**self.values, 'PRIVATE_BETA_DB_NAME': name})
        with self.assertRaises(ImproperlyConfigured):
            validate_private_beta_environment(self.values, regular_db_name=self.values['PRIVATE_BETA_DB_NAME'])

    def test_rejects_inexact_or_insecure_origin(self):
        for origin in ('http://test.trycloudflare.com', 'https://*.trycloudflare.com',
                       'https://test.trycloudflare.com/', 'https://test.trycloudflare.com/path',
                       'https://test.trycloudflare.com:443', 'https://127.0.0.1',
                       'https://user@test.trycloudflare.com', 'https://test.trycloudflare.com?x=1'):
            with self.subTest(origin=origin), self.assertRaises(ImproperlyConfigured):
                validate_private_beta_environment({**self.values, 'PRIVATE_BETA_ORIGIN': origin})

    def test_rejects_private_files_under_public_dist(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_private_beta_environment(self.values, frontend_dist=self.directory.name)
        public = Path(self.directory.name) / 'frontend' / 'public' / 'secrets'
        with self.assertRaises(ImproperlyConfigured):
            validate_private_beta_environment({**self.values, 'PRIVATE_BETA_STATE_DIR': str(public)},
                                              frontend_dist=public.parent.parent / 'dist')

    def test_standard_production_settings_still_require_redis(self):
        environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings',
                       'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': 'isolated-production-settings-test',
                       'DJANGO_PUBLIC_ORIGIN': ORIGIN,
                       'DJANGO_ALLOWED_HOSTS': 'beta-example.trycloudflare.com',
                       'DB_NAME': 'unused', 'DB_USER': 'unused', 'DB_PASSWORD': 'unused',
                       'EMAIL_USE_TLS': '1', 'EMAIL_USE_SSL': '0', 'REDIS_URL': ''}
        result = subprocess.run([sys.executable, '-c', 'import config.settings'],
                                env=environment, cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REDIS_URL', result.stderr)

    def test_standard_production_settings_still_require_real_smtp(self):
        environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings',
                       'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': 'isolated-production-settings-test',
                       'DJANGO_PUBLIC_ORIGIN': ORIGIN,
                       'DJANGO_ALLOWED_HOSTS': 'beta-example.trycloudflare.com',
                       'DB_NAME': 'unused', 'DB_USER': 'unused', 'DB_PASSWORD': 'unused',
                       'EMAIL_USE_TLS': '1', 'EMAIL_USE_SSL': '0', 'REDIS_URL': 'redis://127.0.0.1:6379/0',
                       'EMAIL_BACKEND': 'django.core.mail.backends.filebased.EmailBackend'}
        result = subprocess.run([sys.executable, '-c', 'import config.settings'],
                                env=environment, cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SMTP', result.stderr)

    def test_private_settings_import_without_redis_or_smtp(self):
        environment = {**os.environ, **self.values,
                       'DJANGO_SETTINGS_MODULE': 'config.private_beta_settings',
                       'REDIS_URL': '', 'PRIVATE_BETA_ENV_FILE': ''}
        code = '''import config.private_beta_settings as s
assert s.DEBUG is False
assert s.PRIVATE_BETA is True
assert s.DATABASES['default']['NAME'] == 'chuangxiang_beta_unittest'
assert s.EMAIL_BACKEND == 'django.core.mail.backends.filebased.EmailBackend'
assert s.CACHES['default']['BACKEND'] == 'django.core.cache.backends.filebased.FileBasedCache'
assert s.CSRF_COOKIE_SECURE and s.SESSION_COOKIE_SECURE
assert s.ALLOWED_HOSTS == ['beta-example.trycloudflare.com']
assert s.CSRF_TRUSTED_ORIGINS == ['https://beta-example.trycloudflare.com']
assert s.REST_FRAMEWORK['NUM_PROXIES'] == 0
'''
        result = subprocess.run([sys.executable, '-c', code], env=environment,
                                cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stderr)


@override_settings(
    ROOT_URLCONF='config.private_beta_urls', DEBUG=False, PRIVATE_BETA=True,
    PRIVATE_BETA_USERNAME=USERNAME, PRIVATE_BETA_PASSWORD=PASSWORD,
    ALLOWED_HOSTS=['beta-example.trycloudflare.com'],
    CSRF_TRUSTED_ORIGINS=[ORIGIN],
    SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
    MIDDLEWARE=[
        'config.private_beta.PrivateBetaGateMiddleware',
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'allauth.account.middleware.AccountMiddleware',
    ],
)
class PrivateBetaHTTPTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dist = Path(self.directory.name) / 'dist'
        self.dist.mkdir()
        (self.dist / 'assets').mkdir()
        (self.dist / 'index.html').write_text('<html>private beta app</html>', encoding='utf-8')
        (self.dist / 'assets' / 'app.js').write_text('export const app = true', encoding='utf-8')
        (self.dist / 'assets' / 'app.js.map').write_text('private sourcemap', encoding='utf-8')
        (Path(self.directory.name) / 'credentials.json').write_text('private credentials', encoding='utf-8')
        self.override = override_settings(PRIVATE_BETA_FRONTEND_DIST=self.dist)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.client = Client(enforce_csrf_checks=True,
                             HTTP_HOST='beta-example.trycloudflare.com',
                             HTTP_X_FORWARDED_PROTO='https', HTTP_AUTHORIZATION=BASIC)

    def test_all_content_including_health_requires_invitation(self):
        for path in ('/', '/api/v1/health/', '/assets/app.js', '/api/v1/private-beta/'):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_AUTHORIZATION='')
                self.assertEqual(response.status_code, 401)
                self.assertIn('Basic', response['WWW-Authenticate'])
                self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_wrong_or_malformed_credentials_never_pass(self):
        credentials = ('Basic !!!', 'Bearer token', 'Basic ' + base64.b64encode(b'wrong:wrong').decode(),
                       'Basic ' + base64.b64encode(USERNAME.encode()).decode(), 'Basic ' + 'x' * 5000)
        for value in credentials:
            with self.subTest(value=value[:30]):
                self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION=value).status_code, 401)

    def test_valid_invitation_preserves_application_response(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')
        self.assertEqual(self.client.get('/api/v1/accounts/me/').status_code, 403)

    def test_valid_basic_issues_secure_gate_cookie_for_followup_requests(self):
        response = self.client.get('/api/v1/health/')
        cookie = response.cookies[GATE_COOKIE_NAME]
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/')
        self.assertFalse(cookie['domain'])
        self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='').status_code, 200)
        # 入口 cookie 不等于学生登录，私人账号接口仍拒绝匿名用户。
        self.assertEqual(self.client.get('/api/v1/accounts/me/', HTTP_AUTHORIZATION='').status_code, 403)

    def test_tampered_and_expired_gate_cookies_require_invitation_again(self):
        self.client.get('/api/v1/health/')
        original = self.client.cookies[GATE_COOKIE_NAME].value
        self.client.cookies[GATE_COOKIE_NAME] = original + 'tampered'
        response = self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'private_beta_gate_required')
        self.client.cookies[GATE_COOKIE_NAME] = original
        with patch('django.core.signing.time.time', return_value=time.time() + GATE_COOKIE_AGE + 1):
            self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='').status_code, 401)

    def test_gate_credential_rotation_revokes_previously_issued_cookie(self):
        self.client.get('/api/v1/health/')
        with override_settings(PRIVATE_BETA_PASSWORD=PASSWORD + '-rotated'):
            self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='').status_code, 401)
        with override_settings(PRIVATE_BETA_USERNAME=USERNAME + '-rotated'):
            self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='').status_code, 401)

    def test_gate_cookie_cannot_be_replayed_on_another_allowed_host(self):
        self.client.get('/api/v1/health/')
        with override_settings(ALLOWED_HOSTS=['beta-example.trycloudflare.com', 'other.trycloudflare.com']):
            self.assertEqual(self.client.get('/api/v1/health/', HTTP_AUTHORIZATION='',
                                             HTTP_HOST='other.trycloudflare.com').status_code, 401)

    def test_host_spoofing_is_rejected(self):
        for host in ('127.0.0.1', 'localhost', 'another.trycloudflare.com', 'attacker.example'):
            with self.subTest(host=host):
                self.assertEqual(self.client.get('/api/v1/health/', HTTP_HOST=host).status_code, 400)

    def test_admin_and_native_auth_are_unreachable(self):
        for path in ('/admin', '/admin/', '/admin/login/', '/admin/information-library/',
                     '/accounts/', '/accounts/login/', '/accounts/password/reset/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_no_public_signup_reset_or_verification_in_beta(self):
        for path in ('auth/signup', 'auth/password/request', 'auth/password/reset',
                     'auth/email/verify', 'account/email'):
            with self.subTest(path=path):
                response = self.client.post('/api/auth/browser/v1/' + path, {}, content_type='application/json')
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()['code'], 'private_beta_endpoint_disabled')

    def test_gate_does_not_remove_login_csrf_requirement(self):
        response = self.client.post('/api/auth/browser/v1/auth/login', {}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')

    def test_csrf_cookie_is_secure_and_foreign_origin_is_rejected(self):
        response = self.client.get('/api/v1/accounts/csrf/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['csrftoken']['secure'])
        response = self.client.post('/api/auth/browser/v1/auth/login', {}, content_type='application/json',
                                    HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value,
                                    HTTP_ORIGIN='https://attacker.example')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')

    def test_spa_routes_and_built_assets_are_served(self):
        for path in ('/', '/teams', '/resources/example', '/account/governance'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'private beta app', b''.join(response.streaming_content))
        response = self.client.get('/assets/app.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/javascript')
        response.close()

    def test_private_files_traversal_unknown_assets_and_unknown_api_are_404(self):
        for path in ('/../credentials.json', '/%2e%2e/credentials.json', '/assets/../../credentials.json',
                     '/assets/app.js.map', '/assets/missing.js', '/assets/missing', '/fonts/missing',
                     '/.env', '/backend/.env', '/mail/test.log', '/cache/test', '/api/unknown',
                     '/C:/credentials.json', '/assets\\..\\credentials.json'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_frontend_never_handles_mutations(self):
        response = self.client.post('/teams', {})
        self.assertEqual(response.status_code, 403)  # CSRF checks apply even before the GET-only view.

    def test_beta_status_explains_test_accounts_without_leaking_secrets(self):
        response = self.client.get('/api/v1/private-beta/')
        self.assertTrue(response.json()['private_beta'])
        self.assertFalse(response.json()['registration_enabled'])
        self.assertEqual(response.json()['mail_delivery'], 'local-test-files')
        self.assertNotIn(PASSWORD, response.content.decode())

    def test_guide_rate_limit_cannot_be_bypassed_by_changing_forwarded_for(self):
        rest_settings = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': 0}
        isolated_cache = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                     'LOCATION': 'private-beta-guide-throttle-test'}}
        with override_settings(REST_FRAMEWORK=rest_settings, CACHES=isolated_cache), patch(
            'ai_services.guide_views.run_guide', return_value=({}, {'answer': {'mode': 'rules'}})
        ) as run_guide:
            for number in range(10):
                response = self.client.get('/api/v1/ai/guide/', HTTP_CF_CONNECTING_IP='198.51.100.23',
                                           HTTP_X_FORWARDED_FOR=f'203.0.113.{number}')
                self.assertEqual(response.status_code, 200)
            response = self.client.get('/api/v1/ai/guide/', HTTP_CF_CONNECTING_IP='198.51.100.23',
                                       HTTP_X_FORWARDED_FOR='203.0.113.250')
            self.assertEqual(response.status_code, 429)
            self.assertEqual(run_guide.call_count, 10)


class LocalBetaAdminTests(SimpleTestCase):
    def setUp(self):
        self.override = override_settings(PRIVATE_BETA=True, DEBUG=False)
        self.override.enable()
        self.addCleanup(self.override.disable)
        configure_local_admin(8011)
        self.client = Client(HTTP_HOST='127.0.0.1:8011', REMOTE_ADDR='127.0.0.1')

    def test_local_admin_login_has_isolated_cookie(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('beta_admin_csrftoken', response.cookies)
        self.assertFalse(response.cookies['beta_admin_csrftoken']['secure'])

    def test_tunnel_and_remote_requests_cannot_reach_local_admin(self):
        for headers in (
            {'HTTP_HOST': 'beta-example.trycloudflare.com'},
            {'REMOTE_ADDR': '192.0.2.1'},
            {'HTTP_CF_CONNECTING_IP': '192.0.2.1'},
            {'HTTP_CF_RAY': 'example'},
            {'HTTP_X_FORWARDED_PROTO': 'https'},
        ):
            with self.subTest(headers=headers):
                self.assertIn(self.client.get('/admin/login/', **headers).status_code, (400, 403))

    def test_admin_styles_are_available_only_locally(self):
        response = self.client.get('/static/admin/css/base.css')
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.get('/static/admin/css/base.css', HTTP_CF_RAY='example').status_code, 403)


class BetaMaintenanceTests(SimpleTestCase):
    def test_each_valid_round_calls_existing_command_and_closes_its_connection(self):
        database = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'chuangxiang_beta_maintenance'}}
        with patch('config.private_beta.settings', PRIVATE_BETA=True, DATABASES=database), \
                patch('config.private_beta.connection') as conn, \
                patch('config.private_beta.close_old_connections') as close_old, \
                patch('config.private_beta.call_command') as command:
            conn.vendor = 'postgresql'
            conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ('chuangxiang_beta_maintenance',)
            run_beta_maintenance_once()
            command.assert_called_once()
            self.assertEqual(command.call_args.args, ('settle_team_deadlines',))
            conn.close.assert_called_once()
            close_old.assert_called_once()

    def test_config_or_actual_database_mismatch_prevents_maintenance(self):
        for configured, actual in [('chuangxiang', 'chuangxiang'),
                                   ('chuangxiang_beta_expected', 'chuangxiang'),
                                   ('chuangxiang_beta_expected', 'chuangxiang_beta_other')]:
            with self.subTest(configured=configured, actual=actual), \
                    patch('config.private_beta.settings', PRIVATE_BETA=True, DATABASES={'default': {'NAME': configured}}), \
                    patch('config.private_beta.connection') as conn, \
                    patch('config.private_beta.close_old_connections'), \
                    patch('config.private_beta.call_command') as command:
                conn.vendor = 'postgresql'
                conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (actual,)
                with self.assertRaises(ImproperlyConfigured):
                    run_beta_maintenance_once()
                command.assert_not_called()
                conn.close.assert_called_once()

    def test_non_beta_and_local_admin_do_not_start_background_thread(self):
        with patch('config.private_beta.threading.Thread') as worker:
            with override_settings(PRIVATE_BETA=False):
                self.assertIsNone(start_beta_maintenance())
            with override_settings(PRIVATE_BETA=True):
                self.assertIsNone(start_beta_maintenance(local_admin=True))
            worker.assert_not_called()

    def test_beta_worker_is_daemon_and_waits_sixty_seconds_between_rounds(self):
        with override_settings(PRIVATE_BETA=True), patch('config.private_beta.threading.Thread') as worker:
            started = start_beta_maintenance()
            self.assertTrue(worker.call_args.kwargs['daemon'])
            worker.return_value.start.assert_called_once()
            self.assertIs(started[1], worker.return_value)
        event = Mock()
        event.is_set.return_value = False
        event.wait.side_effect = [False, True]
        with patch('config.private_beta.run_beta_maintenance_once') as cycle:
            beta_maintenance_loop(event)
            self.assertEqual(cycle.call_count, 2)
            self.assertEqual([call.args for call in event.wait.call_args_list], [(60,), (60,)])

    def test_failed_round_retries_without_logging_exception_contents(self):
        event = Mock()
        event.is_set.return_value = False
        event.wait.side_effect = [False, True]
        with patch('config.private_beta.run_beta_maintenance_once', side_effect=[RuntimeError('secret-connection-text'), None]) as cycle, \
                self.assertLogs('config.private_beta', level='WARNING') as logs:
            beta_maintenance_loop(event)
            self.assertEqual(cycle.call_count, 2)
            self.assertNotIn('secret-connection-text', '\n'.join(logs.output))
