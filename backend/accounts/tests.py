from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase


User = get_user_model()
PASSWORD = 'Model-test-secret!47'


class UserModelTests(TestCase):
    def test_create_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user('  Student@TONGJI.EDU.CN ', PASSWORD)
        self.assertEqual(user.email, 'student@tongji.edu.cn')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertRegex(user.public_code, r'^CX-[A-Z0-9]{8}$')
        self.assertEqual(str(user), user.public_code)
        self.assertEqual(user.get_full_name(), user.public_code)
        self.assertFalse(user.has_contact_details)
        self.assertIsNone(user.contact_updated_at)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_email_login_uses_normalized_identifier(self):
        user = User.objects.create_user('student@tongji.edu.cn', PASSWORD)
        self.assertEqual(authenticate(email=' STUDENT@TONGJI.EDU.CN ', password=PASSWORD), user)

    def test_invalid_email_and_weak_password_are_rejected(self):
        for email in ('student@example.org', 'student@tongji.edu.cn.example.org', 'not-an-email'):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                User.objects.create_user(email, PASSWORD)
        with self.assertRaises(ValueError):
            User.objects.create_user('  ', PASSWORD)
        with self.assertRaises(ValidationError):
            User.objects.create_user('student@tongji.edu.cn', '123')
        self.assertEqual(User.objects.count(), 0)

    def test_case_variant_duplicate_does_not_replace_existing_user(self):
        user = User.objects.create_user('student@tongji.edu.cn', PASSWORD)
        with self.assertRaises(ValidationError):
            User.objects.create_user('STUDENT@TONGJI.EDU.CN', 'Another-secret!91')
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(User.objects.count(), 1)

    def test_database_blocks_bypassing_email_validation(self):
        first = User.objects.create_user('first@tongji.edu.cn', PASSWORD)
        second = User.objects.create_user('second@tongji.edu.cn', PASSWORD)
        for bad in (first.email, first.email.upper(), 'outside@example.org', '', ' first@tongji.edu.cn '):
            with self.subTest(email=bad), self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.filter(pk=second.pk).update(email=bad)

    def test_plaintext_password_is_not_saved(self):
        with self.assertRaises(ValidationError):
            User(email='student@tongji.edu.cn', password=PASSWORD).save()

    def test_superuser_creation_and_privilege_validation(self):
        user = User.objects.create_superuser('Admin@tongji.edu.cn', PASSWORD)
        self.assertTrue(user.is_staff and user.is_superuser and user.is_active)
        for flags in ({'is_staff': False}, {'is_superuser': False}):
            with self.assertRaises(ValueError):
                User.objects.create_superuser('other@tongji.edu.cn', PASSWORD, **flags)

    def test_public_code_cannot_be_supplied_or_changed(self):
        with self.assertRaises(ValueError):
            User.objects.create_user('student@tongji.edu.cn', PASSWORD, public_code='CX-AAAAAAAA')
        user = User.objects.create_user('student@tongji.edu.cn', PASSWORD)
        user.public_code = 'CX-AAAAAAAA'
        with self.assertRaises(ValidationError):
            user.save()

    def test_public_code_collision_retries_without_losing_user(self):
        with patch('accounts.models.secrets.choice', return_value='A'):
            first = User.objects.create_user('first@tongji.edu.cn', PASSWORD)
            with patch('accounts.models.generate_public_code', return_value='CX-BBBBBBBB'):
                second = User.objects.create_user('second@tongji.edu.cn', PASSWORD)
        self.assertEqual(first.public_code, 'CX-AAAAAAAA')
        self.assertEqual(second.public_code, 'CX-BBBBBBBB')
        self.assertEqual(User.objects.count(), 2)

    def test_public_code_collision_has_bounded_retries(self):
        with patch('accounts.models.secrets.choice', return_value='A'):
            User.objects.create_user('first@tongji.edu.cn', PASSWORD)
            with self.assertRaises(IntegrityError):
                User.objects.create_user('second@tongji.edu.cn', PASSWORD)
        self.assertEqual(User.objects.count(), 1)

    def test_contact_changes_update_timestamp_on_partial_save(self):
        user = User.objects.create_user('student@tongji.edu.cn', PASSWORD)
        user.wechat_id = '  student_wechat  '
        user.save(update_fields=['wechat_id'])
        user.refresh_from_db()
        self.assertEqual(user.wechat_id, 'student_wechat')
        self.assertTrue(user.has_contact_details)
        changed = user.contact_updated_at
        self.assertIsNotNone(changed)
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        user.refresh_from_db()
        self.assertEqual(user.contact_updated_at, changed)

    def test_optional_contacts_accept_both_and_reject_links(self):
        user = User.objects.create_user(
            'student@tongji.edu.cn', PASSWORD, wechat_id='student_wechat', phone_number='+44 7700 900123',
        )
        self.assertTrue(user.has_contact_details)
        self.assertIsNotNone(user.contact_updated_at)
        user.wechat_id = 'https://example.org/contact'
        with self.assertRaises(ValidationError):
            user.save()
