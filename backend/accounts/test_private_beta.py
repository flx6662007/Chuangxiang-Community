"""隔离内测账号命令：仅模拟数据库身份，邮箱确认使用真实 allauth + 本地邮件。"""
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .management.commands.prepare_private_beta import ACCOUNT_SPECS, FILE_BACKEND, account_specs, validate_environment
from .models import User
from .permissions import account_eligibility


class PrivateBetaAccountsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.database = 'chuangxiang_beta_20261006'
        self.state = self.base / '.local' / 'private-beta' / self.database
        self.settings_override = override_settings(
            PRIVATE_BETA=True, PRIVATE_BETA_STATE_DIR=self.state, BASE_DIR=self.base / 'backend',
            EMAIL_BACKEND=FILE_BACKEND, EMAIL_FILE_PATH=self.state / 'mail',
            PUBLIC_ORIGIN='http://localhost:5175', ALLOWED_HOSTS=['localhost'],
            PRIVATE_BETA_USERNAME='unit-test-invitation',
            PRIVATE_BETA_PASSWORD='unit-test-gate-password-for-private-export',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.identity = patch('accounts.management.commands.prepare_private_beta.database_identity',
                              return_value=('postgresql', self.database))
        self.identity.start()
        self.addCleanup(self.identity.stop)

    def prepare(self, **kwargs):
        output = StringIO()
        call_command('prepare_private_beta', stdout=output, **kwargs)
        data = json.loads((self.state / 'accounts.json').read_text(encoding='utf-8'))
        return data, output.getvalue()

    def test_creates_seven_separate_accounts_using_real_local_mail_confirmation(self):
        with patch('smtplib.SMTP', side_effect=AssertionError('No SMTP')):
            data, output = self.prepare()
        self.assertEqual(User.objects.count(), 7)
        self.assertEqual(User.objects.filter(is_staff=True).count(), 2)
        self.assertFalse(User.objects.filter(is_superuser=True).exists())
        self.assertEqual(EmailAddress.objects.filter(primary=True, verified=True).count(), 7)
        self.assertEqual(data['database'], self.database)
        self.assertEqual(data['purpose'], 'private-beta-test-accounts')
        self.assertEqual(len({row['password'] for row in data['accounts']}), 7)
        self.assertTrue(list((self.state / 'mail').glob('*.log')))
        for record in data['accounts']:
            user = User.objects.get(pk=record['user_id'])
            self.assertTrue(user.check_password(record['password']))
            self.assertNotIn(record['password'], output)
            self.assertTrue(account_eligibility(user)['eligible'])
            self.assertEqual(record['verification'], 'allauth-local-mail')
            self.assertEqual(user.has_perm('curation.add_importrun'), user.is_staff)
            self.assertFalse(user.has_perm('accounts.change_user'))

    def test_rerun_preserves_password_verification_contacts_and_permissions(self):
        first, _ = self.prepare()
        user = User.objects.get(email=ACCOUNT_SPECS[0][2])
        user.wechat_id = 'changed_by_tester'
        user.save()
        passwords = dict(User.objects.values_list('email', 'password'))
        with patch('accounts.management.commands.prepare_private_beta.confirm_test_email') as confirm:
            second, output = self.prepare()
        confirm.assert_not_called()
        self.assertEqual(first, second)
        self.assertEqual(passwords, dict(User.objects.values_list('email', 'password')))
        self.assertEqual(User.objects.get(pk=user.pk).wechat_id, 'changed_by_tester')
        self.assertIn('创建 0', output)

    def test_existing_accounts_and_real_emails_are_never_changed_or_verified(self):
        preset = User.objects.create_user(ACCOUNT_SPECS[0][2], 'Existing-test-password')
        real = User.objects.create_user('actual-student@tongji.edu.cn', 'Real-existing-password')
        data, _ = self.prepare()
        preset.refresh_from_db()
        real.refresh_from_db()
        self.assertTrue(preset.check_password('Existing-test-password'))
        self.assertTrue(real.check_password('Real-existing-password'))
        self.assertFalse(EmailAddress.objects.filter(user__in=[preset, real], verified=True).exists())
        row = next(row for row in data['accounts'] if row['email'] == preset.email)
        self.assertNotIn('password', row)
        self.assertEqual(row['credential_status'], 'existing-password-unchanged')

    def test_guards_reject_normal_database_non_beta_and_smtp(self):
        with override_settings(PRIVATE_BETA=False), self.assertRaises(CommandError):
            validate_environment()
        with patch('accounts.management.commands.prepare_private_beta.database_identity',
                   return_value=('postgresql', 'chuangxiang')), self.assertRaises(CommandError):
            validate_environment()
        with patch('accounts.management.commands.prepare_private_beta.database_identity',
                   return_value=('sqlite', self.database)), self.assertRaises(CommandError):
            validate_environment()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'), self.assertRaises(CommandError):
            validate_environment()
        self.assertFalse(User.objects.exists())

    def test_credentials_and_mail_must_remain_inside_ignored_state_directory(self):
        with self.assertRaises(CommandError):
            validate_environment(self.base / 'public-accounts.json')
        with override_settings(EMAIL_FILE_PATH=self.base / 'public-mail'), self.assertRaises(CommandError):
            validate_environment()
        with override_settings(PRIVATE_BETA_STATE_DIR=self.base / 'outside'), self.assertRaises(CommandError):
            validate_environment()

    def test_unrelated_output_file_is_not_overwritten(self):
        self.state.mkdir(parents=True)
        output = self.state / 'accounts.json'
        original = '{"other": "keep this file"}'
        output.write_text(original, encoding='utf-8')
        with self.assertRaises(CommandError):
            call_command('prepare_private_beta', stdout=StringIO())
        self.assertEqual(output.read_text(encoding='utf-8'), original)
        self.assertFalse(User.objects.exists())

    def test_invalid_local_mail_code_rolls_back_accounts(self):
        with patch('accounts.management.commands.prepare_private_beta._mail_code', return_value='invalid'):
            with self.assertRaises(CommandError):
                call_command('prepare_private_beta', stdout=StringIO())
        self.assertFalse(User.objects.exists())
        self.assertFalse((self.state / 'accounts.json').exists())

    def test_increasing_student_count_only_adds_new_accounts(self):
        first, _ = self.prepare()
        owner = User.objects.get(email=ACCOUNT_SPECS[0][2])
        owner.wechat_id = 'preserve_my_contact'
        owner.save()
        initial = {user.email: (user.password, user.wechat_id, user.is_staff,
                               set(user.user_permissions.values_list('pk', flat=True)))
                   for user in User.objects.all()}
        with patch('smtplib.SMTP', side_effect=AssertionError('No SMTP')):
            expanded, output = self.prepare(students=10)
        self.assertEqual(User.objects.count(), 12)
        self.assertEqual(User.objects.filter(is_staff=True).count(), 2)
        self.assertEqual(EmailAddress.objects.filter(primary=True, verified=True).count(), 12)
        self.assertIn('创建 5', output)
        self.assertIn('保留 7', output)
        expanded_by_email = {row['email']: row for row in expanded['accounts']}
        for row in first['accounts']:
            self.assertEqual(expanded_by_email[row['email']], row)
        for email, previous in initial.items():
            user = User.objects.get(email=email)
            self.assertEqual((user.password, user.wechat_id, user.is_staff,
                              set(user.user_permissions.values_list('pk', flat=True))), previous)

    def test_smaller_rerun_preserves_all_saved_accounts_and_passwords(self):
        expanded, _ = self.prepare(students=10)
        with patch('accounts.management.commands.prepare_private_beta.confirm_test_email') as confirm:
            smaller, output = self.prepare(students=3)
        self.assertEqual(smaller, expanded)
        self.assertEqual(User.objects.count(), 12)
        confirm.assert_not_called()
        self.assertIn('创建 0', output)
        self.assertIn('保留 12', output)

    def test_only_bounded_synthetic_accounts_are_allowed(self):
        for number in (0, 51, -1, True, '10'):
            with self.subTest(number=number), self.assertRaises(CommandError):
                account_specs(number)
        self.assertEqual(len(account_specs(50)), 52)
        original, _ = self.prepare()
        original['accounts'][0]['email'] = 'private-beta-test-student-51@tongji.edu.cn'
        destination = self.state / 'accounts.json'
        destination.write_text(json.dumps(original), encoding='utf-8')
        before = destination.read_bytes()
        with self.assertRaises(CommandError):
            self.prepare(students=10)
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(User.objects.count(), 7)

    def test_markdown_is_private_and_each_invitation_has_only_its_own_account(self):
        data, output = self.prepare(students=10, markdown=True)
        summary_path = self.state / '内测账号清单-仅负责人.md'
        summary = summary_path.read_text(encoding='utf-8')
        self.assertIn('http://localhost:5175/', summary)
        self.assertIn('http://127.0.0.1:8011/admin/', summary)
        self.assertIn('负责人使用（04，已分配）', summary)
        self.assertIn('本次新增，待分配', summary)
        self.assertIn('unit-test-invitation', summary)
        self.assertIn('unit-test-gate-password-for-private-export', summary)
        self.assertNotIn('unit-test-gate-password-for-private-export', output)
        self.assertEqual(len(list((self.state / 'invitations').glob('*.md'))), 10)
        for row in data['accounts']:
            self.assertIn(row['email'], summary)
            self.assertIn(row['password'], summary)
            self.assertNotIn(row['password'], output)
            if row['role'] != 'student':
                continue
            number = int(row['email'].split('@')[0].rsplit('-', 1)[-1])
            invitation = (self.state / 'invitations' / f'内测邀请-{number:02}.md').read_text(encoding='utf-8')
            self.assertIn(row['email'], invitation)
            self.assertIn(row['password'], invitation)
            self.assertIn('unit-test-gate-password-for-private-export', invitation)
            self.assertNotIn('127.0.0.1:8011', invitation)
            for other in data['accounts']:
                if other['email'] != row['email']:
                    self.assertNotIn(other['email'], invitation)
                    self.assertNotIn(other['password'], invitation)

    def test_markdown_export_rejects_public_mail_outside_and_invitation_summary_paths(self):
        for target in (self.base / 'public.md', self.state / 'mail' / 'secret.md',
                       self.state / 'cache' / 'secret.md', self.state / 'frontend-dist' / 'secret.md',
                       self.state / 'invitations' / 'all-secrets.md'):
            with self.subTest(target=target), self.assertRaises(CommandError):
                self.prepare(markdown=target)
        self.assertFalse(User.objects.exists())
        with self.assertRaises(CommandError):
            validate_environment(self.state / 'frontend-dist' / 'credentials.json')

    def test_markdown_does_not_overwrite_an_unrelated_file(self):
        self.state.mkdir(parents=True)
        destination = self.state / 'existing.md'
        destination.write_text('Keep my notes.', encoding='utf-8')
        with self.assertRaises(CommandError):
            self.prepare(markdown=destination)
        self.assertEqual(destination.read_text(encoding='utf-8'), 'Keep my notes.')
        self.assertFalse(User.objects.exists())

    def test_markdown_rerun_updates_origin_without_resetting_accounts(self):
        first, _ = self.prepare(markdown=True)
        with override_settings(PUBLIC_ORIGIN='https://new-beta.example.com'), \
                patch('accounts.management.commands.prepare_private_beta.confirm_test_email') as confirm:
            second, output = self.prepare(students=1, markdown=True)
        self.assertEqual(first, second)
        confirm.assert_not_called()
        for path in [self.state / '内测账号清单-仅负责人.md', *self.state.glob('invitations/*.md')]:
            content = path.read_text(encoding='utf-8')
            self.assertIn('https://new-beta.example.com/', content)
            self.assertNotIn('http://localhost:5175/', content)
