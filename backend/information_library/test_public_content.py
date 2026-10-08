"""公共清理函数的独立加载与旧路径兼容；业务输出边界由现有 API 测试覆盖。"""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase

from common.public_content import public_text, safe_source_url


class PublicContentBoundaryTests(SimpleTestCase):
    def test_helpers_work_without_django_setup_or_business_model_imports(self):
        environment = {key: value for key, value in os.environ.items() if key != 'DJANGO_SETTINGS_MODULE'}
        program = '''
import sys
from django.conf import settings
assert not settings.configured
from common.public_content import public_text, safe_source_url
assert public_text('<b>Research</b>') == 'Research'
assert safe_source_url('https://www.tongji.edu.cn/info/1.htm#top') == 'https://www.tongji.edu.cn/info/1.htm'
assert not settings.configured
assert not any(name in sys.modules for name in (
    'information_library.selectors', 'research.models', 'resources.models',
    'competitions.models', 'curation.models', 'newsletters.models'))
'''
        result = subprocess.run(
            [sys.executable, '-c', program], env=environment,
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_selector_imports_use_the_same_cleaning_functions(self):
        from information_library import selectors
        self.assertIs(selectors.public_text, public_text)
        self.assertIs(selectors.safe_source_url, safe_source_url)

    def test_source_display_validation_never_resolves_remote_hosts(self):
        with patch('socket.getaddrinfo', side_effect=AssertionError('display validation must not resolve hosts')):
            self.assertEqual(safe_source_url('https://www.tongji.edu.cn/path#section'),
                             'https://www.tongji.edu.cn/path')
            self.assertEqual(safe_source_url('http://127.0.0.1/private'), '')
