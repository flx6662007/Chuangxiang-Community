"""评审配置隔离、静态资源边界和真实 allauth/CSRF 接口回归。"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import Http404
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings

from .portable import frontend


BACKEND = Path(__file__).resolve().parent.parent
LOOPBACK_MIDDLEWARE = 'config.portable.PortableLoopbackMiddleware'
PORTABLE_HTTP_SETTINGS = {
    'ROOT_URLCONF': 'config.portable_urls', 'DEBUG': False,
    'ALLOWED_HOSTS': ['127.0.0.1', 'localhost'],
    'SECURE_SSL_REDIRECT': False, 'SECURE_PROXY_SSL_HEADER': None,
    'SESSION_COOKIE_SECURE': False, 'CSRF_COOKIE_SECURE': False,
    'SESSION_COOKIE_NAME': 'portable_sessionid', 'CSRF_COOKIE_NAME': 'csrftoken',
    'CSRF_TRUSTED_ORIGINS': ['http://127.0.0.1:8765'],
    'MIDDLEWARE': [LOOPBACK_MIDDLEWARE, *[
        item for item in settings.MIDDLEWARE if item != LOOPBACK_MIDDLEWARE]],
}


class PortableSettingsTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        (self.dist / 'index.html').write_text('<html>review</html>', encoding='utf-8')
        self.environment = {
            **{key: value for key, value in os.environ.items() if not key.startswith('PORTABLE_')},
            'DJANGO_SETTINGS_MODULE': 'config.portable_settings',
            'PORTABLE_DATA_DIR': str(self.root / 'data'),
            'PORTABLE_FRONTEND_DIST': str(self.dist), 'PORTABLE_PORT': '8765',
            'PORTABLE_SECRET_KEY': 'portable-isolated-test-secret-' * 3,
        }

    def run_settings(self, code, **environment):
        return subprocess.run([sys.executable, '-c', code],
                              env={**self.environment, **environment}, cwd=BACKEND,
                              capture_output=True, text=True, encoding='utf-8', errors='replace')

    def test_settings_do_not_read_dotenv_or_inherit_development_connections(self):
        result = self.run_settings('''
import os
from pathlib import Path
from unittest.mock import patch
with patch('dotenv.main.DotEnv', side_effect=AssertionError('dotenv must not be opened')):
    import config.portable_settings as s
assert not s.DEBUG and s.PORTABLE
assert s.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
assert s.DATABASES['default']['NAME'] == Path(os.environ['PORTABLE_DATA_DIR']) / 'demo.sqlite3'
assert s.DATABASES['default']['OPTIONS']['transaction_mode'] == 'IMMEDIATE'
assert s.EMAIL_BACKEND == 'django.core.mail.backends.filebased.EmailBackend'
assert s.EMAIL_FILE_PATH == Path(os.environ['PORTABLE_DATA_DIR']) / 'mail'
assert s.CACHES['default']['LOCATION'] == Path(os.environ['PORTABLE_DATA_DIR']) / 'cache'
assert s.REDIS_URL == s.EMAIL_HOST_PASSWORD == s.AI_CHAT['API_KEY'] == ''
assert not s.AI_SERVICES['ENABLED'] and s.AI_SERVICES['API_KEY'] == ''
assert s.ALLOWED_HOSTS == ['127.0.0.1', 'localhost']
assert not s.SESSION_COOKIE_SECURE and not s.CSRF_COOKIE_SECURE
assert not s.SECURE_SSL_REDIRECT and s.SECURE_PROXY_SSL_HEADER is None
assert os.environ['DB_NAME'] == 'portable_unused'
assert os.environ['COMPETITION_SEMANTIC_INDEX'] == ''
assert os.environ['UNIFIED_SEMANTIC_INDEX'] == ''
assert os.environ['COMPETITION_EMBEDDING_MODEL_PATH'] == ''
assert os.environ['HF_HUB_OFFLINE'] == os.environ['TRANSFORMERS_OFFLINE'] == '1'
''', DB_NAME='development_database', DEEPSEEK_API_KEY='inherited-secret-do-not-use',
            AI_API_KEY='inherited-legacy-secret', AI_ENABLED='1', REDIS_URL='redis://unrelated',
            COMPETITION_SEMANTIC_INDEX='development.npz', UNIFIED_SEMANTIC_INDEX='development.npz',
            COMPETITION_EMBEDDING_MODEL_PATH='development-model',
            EMAIL_HOST_PASSWORD='inherited-mail-secret', EMAIL_USE_TLS='1', EMAIL_USE_SSL='1')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_semantic_files_are_loaded_only_from_the_current_package(self):
        package = self.root / 'package'
        (package / 'models' / 'bge-small-zh-v1.5').mkdir(parents=True)
        (package / 'index').mkdir()
        for name in ('competitions.npz', 'unified.npz'):
            (package / 'index' / name).write_bytes(b'test-placeholder')
        result = self.run_settings('''
import os
from pathlib import Path
import config.portable_settings
root = Path(os.environ['PORTABLE_PACKAGE_ROOT'])
assert Path(os.environ['COMPETITION_EMBEDDING_MODEL_PATH']) == root / 'models' / 'bge-small-zh-v1.5'
assert Path(os.environ['COMPETITION_SEMANTIC_INDEX']) == root / 'index' / 'competitions.npz'
assert Path(os.environ['UNIFIED_SEMANTIC_INDEX']) == root / 'index' / 'unified.npz'
''', PORTABLE_PACKAGE_ROOT=str(package))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_portable_ai_key_is_used_without_returning_it(self):
        result = self.run_settings('''
import config.portable_settings as s
assert s.AI_CHAT['API_KEY'] == 'review-only-key'
assert s.AI_CHAT['MODEL'] == 'review-model'
''', PORTABLE_DEEPSEEK_API_KEY='review-only-key', PORTABLE_DEEPSEEK_MODEL='review-model')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_insecure_or_ambiguous_directory_and_port_settings_are_rejected(self):
        for changes in (
            {'PORTABLE_SECRET_KEY': ''}, {'PORTABLE_DATA_DIR': 'relative-data'},
            {'PORTABLE_DATA_DIR': str(self.dist / 'secrets')},
            {'PORTABLE_DATA_DIR': str(self.root)},
            {'PORTABLE_FRONTEND_DIST': str(self.root / 'missing-dist')},
            {'PORTABLE_PORT': '0'}, {'PORTABLE_PORT': '65536'}, {'PORTABLE_PORT': 'invalid'},
        ):
            with self.subTest(changes=changes):
                result = self.run_settings('import config.portable_settings', **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)


@override_settings(**PORTABLE_HTTP_SETTINGS)
class PortableHTTPTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        dist = self.root / 'dist'
        (dist / 'assets').mkdir(parents=True)
        (dist / 'index.html').write_text('<html>portable-spa</html>', encoding='utf-8')
        (dist / 'assets' / 'app.js').write_text('window.review = true;', encoding='utf-8')
        (self.root / 'secret.txt').write_text('not-public', encoding='utf-8')
        (dist / '.env').write_text('not-public', encoding='utf-8')
        config = override_settings(PORTABLE_FRONTEND_DIST=dist, STATIC_ROOT=self.root / 'staticfiles')
        config.enable()
        self.addCleanup(config.disable)
        self.client = Client(HTTP_HOST='127.0.0.1:8765')

    def body(self, response):
        if response.streaming:
            body = b''.join(response.streaming_content)
            response.close()
            return body
        return response.content

    def test_spa_deep_links_and_javascript_work_with_debug_false(self):
        for url in ('/', '/teams/42', '/account/teams', '/competitions/catalog/example'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], 'no-store')
                self.assertIn(b'portable-spa', self.body(response))
        response = self.client.get('/assets/app.js')
        self.assertEqual(response['Content-Type'], 'text/javascript')
        self.assertIn(b'window.review', self.body(response))

    def test_missing_api_and_assets_do_not_return_spa(self):
        for url in ('/api/unknown', '/api/v1/not-a-real-route/', '/assets/missing.js',
                    '/missing.css', '/.env'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b'portable-spa', self.body(response))
        # Django 管理入口保留自身的登录跳转，不能被 SPA 覆盖。
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/admin/login/'))

    def test_static_admin_assets_work_without_collectstatic(self):
        response = self.client.get('/static/admin/css/base.css')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/css')
        self.assertTrue(self.body(response))

    def test_path_traversal_and_hidden_files_are_rejected(self):
        request = RequestFactory().get('/')
        for path in ('../secret.txt', r'..\secret.txt', 'C:/secret.txt', '.env', 'assets/../../secret.txt'):
            with self.subTest(path=path), self.assertRaises(Http404):
                frontend(request, path)

    def test_health_identifies_instance_and_cannot_be_called_from_remote_address(self):
        with patch.dict(os.environ, {'PORTABLE_INSTANCE_TOKEN': 'instance-test', 'PORTABLE_PACKAGE_ID': 'package-test'}):
            response = self.client.get('/api/portable/health/')
        self.assertEqual(response.json(), {
            'status': 'ok', 'instance_token': 'instance-test', 'package_id': 'package-test'})
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/api/v1/health/').status_code, 200)
        self.assertEqual(self.client.get('/api/portable/health/', REMOTE_ADDR='192.0.2.1',
                                         HTTP_X_FORWARDED_FOR='127.0.0.1').status_code, 400)
        self.assertEqual(self.client.get('/', HTTP_HOST='example.com').status_code, 400)


@override_settings(**PORTABLE_HTTP_SETTINGS)
class PortableAccountTests(TestCase):
    def test_verified_demo_account_can_log_in_with_csrf_over_http_and_access_business_apis(self):
        cache.clear()
        user = get_user_model().objects.create_user('portable-test@tongji.edu.cn', 'Portable!Review2026')
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        client = Client(enforce_csrf_checks=True, HTTP_HOST='127.0.0.1:8765')
        self.assertEqual(client.get('/api/v1/accounts/csrf/').status_code, 200)
        login_path = '/api/auth/browser/v1/auth/login'
        body = json.dumps({'email': user.email, 'password': 'Portable!Review2026'})
        self.assertEqual(client.post(login_path, body, content_type='application/json').status_code, 403)
        response = client.post(login_path, body, content_type='application/json',
                               HTTP_ORIGIN='http://127.0.0.1:8765',
                               HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(client.cookies['portable_sessionid']['secure'])
        self.assertFalse(client.cookies['csrftoken']['secure'])
        self.assertTrue(client.get('/api/v1/accounts/me/').json()['school_email_verified'])
        for path in ('/api/v1/teams/mine/', '/api/v1/governance/reports/', '/api/v1/ai/status/'):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
