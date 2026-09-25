"""通过真实 HTTP 视图验证认证、验证码、CSRF 和资料边界，不调用外部邮件。"""
import json
import re
import smtplib
from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import User, UserRestriction
from .permissions import account_eligibility, school_email_verified

AUTH = '/api/auth/browser/v1/'
EMAIL = 'rounds-test@tongji.edu.cn'
PASSWORD = 'Forest!River82-Bicycle'


class AccountAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/api/v1/accounts/csrf/')

    def request(self, method, path, data=None, client=None):
        client = client or self.client
        return getattr(client, method)(path, data=json.dumps(data or {}),
            content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)

    def signup(self, email=EMAIL):
        response = self.request('post', AUTH + 'auth/signup', {'email': email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        return User.objects.get(email=email.strip().lower())

    def send_code(self):
        response = self.request('put', AUTH + 'account/email', {'email': EMAIL})
        self.assertEqual(response.status_code, 200, response.content)
        return re.search(r'验证码：(\S+)', mail.outbox[-1].body).group(1)

    def test_signup_normalizes_email_hashes_password_and_allows_unverified_login(self):
        user = self.signup(' ROUNDS-TEST@TONGJI.EDU.CN ')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertRegex(user.public_code, r'^CX-[A-Z0-9]{8}$')
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['school_email_verified'])
        self.assertFalse(response.json()['account_eligibility']['eligible'])
        self.assertEqual(len(mail.outbox), 0)

    def test_signup_rejects_domain_weak_password_and_missing_csrf(self):
        for email in ('someone@gmail.com', 'name@tongji.edu.cn.evil.test'):
            response = self.request('post', AUTH + 'auth/signup', {'email': email, 'password': PASSWORD})
            self.assertEqual(response.status_code, 400)
        response = self.request('post', AUTH + 'auth/signup', {'email': EMAIL, 'password': '12345678'})
        self.assertEqual(response.status_code, 400)
        response = Client(enforce_csrf_checks=True).post(AUTH + 'auth/signup',
            json.dumps({'email': EMAIL, 'password': PASSWORD}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)

    def test_duplicate_signup_cannot_replace_password(self):
        user = self.signup()
        self.request('delete', AUTH + 'auth/session')
        response = self.request('post', AUTH + 'auth/signup', {'email': EMAIL, 'password': 'Another!Password93'})
        self.assertEqual(response.status_code, 400, response.content)
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(User.objects.count(), 1)

    def test_similar_password_is_a_field_error_and_signup_is_atomic(self):
        response = self.request('post', AUTH + 'auth/signup', {'email': 'forest!river82-bicycle@tongji.edu.cn', 'password': PASSWORD})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(User.objects.count(), 0)
        with patch('allauth.account.forms.setup_user_email', side_effect=IntegrityError('private')):
            response = self.request('post', AUTH + 'auth/signup', {'email': EMAIL, 'password': PASSWORD})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(User.objects.count(), 0)

    def test_admin_created_user_can_login_and_verify(self):
        User.objects.create_user(EMAIL, PASSWORD)
        response = self.request('post', AUTH + 'auth/login', {'email': EMAIL, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        address = EmailAddress.objects.get(user__email=EMAIL)
        self.assertTrue(address.primary)
        self.assertFalse(address.verified)
        code = self.send_code()
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': code}).status_code, 200)

    def test_login_logout_and_inactive_account(self):
        user = self.signup()
        self.assertEqual(self.request('delete', AUTH + 'auth/session').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/accounts/me/').status_code, 403)
        response = self.request('post', AUTH + 'auth/login', {'email': EMAIL.upper(), 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        user.is_active = False
        user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/v1/accounts/me/').status_code, 403)

    def test_admin_session_can_request_its_first_email_verification(self):
        user = User.objects.create_superuser(EMAIL, PASSWORD)
        response = self.client.post('/admin/login/', {'username': EMAIL, 'password': PASSWORD, 'next': '/admin/'},
            HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())
        code = self.send_code()
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': code}).status_code, 200)
        self.assertTrue(school_email_verified(user))

    def test_verification_wrong_code_success_and_reuse(self):
        user = self.signup()
        code = self.send_code()
        self.assertRegex(code, r'^\d{6}$')
        bad = '000000' if code != '000000' else '111111'
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': bad}).status_code, 400)
        self.assertFalse(school_email_verified(user))
        response = self.request('post', AUTH + 'auth/email/verify', {'key': code})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(school_email_verified(user))
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': code}).status_code, 409)

    def test_code_expiry_and_attempt_limit(self):
        self.signup()
        code = self.send_code()
        session = self.client.session
        state = session['account_email_verification_code']
        state['at'] -= 601
        session['account_email_verification_code'] = state
        session.save()
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': code}).status_code, 409)
        cache.clear()
        code = self.send_code()
        bad = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': bad}).status_code, 400)
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': code}).status_code, 409)

    def test_resend_limits_and_invalidates_old_code(self):
        self.signup()
        with patch('accounts.adapters.SchoolAccountAdapter.generate_email_verification_code', return_value='123456'):
            old = self.send_code()
        self.assertEqual(self.request('put', AUTH + 'account/email', {'email': EMAIL}).status_code, 429)
        cache.clear()  # 模拟冷却已过，专门验证重发后的失效行为。
        with patch('accounts.adapters.SchoolAccountAdapter.generate_email_verification_code', return_value='654321'):
            new = self.send_code()
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': old}).status_code, 400)
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': new}).status_code, 200)

    def test_mail_failure_is_safe_and_does_not_verify(self):
        user = self.signup()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            with patch('django.core.mail.backends.smtp.EmailBackend.open', side_effect=smtplib.SMTPException('PRIVATE-SMTP-DETAIL')):
                response = self.request('put', AUTH + 'account/email', {'email': EMAIL})
        self.assertEqual(response.status_code, 503, response.content)
        self.assertNotIn('PRIVATE-SMTP-DETAIL', response.content.decode())
        self.assertFalse(school_email_verified(user))
        self.assertNotIn('account_email_verification_code', self.client.session)

    def test_resend_quota_and_original_expiration_are_preserved(self):
        self.signup()
        self.send_code()
        original = self.client.session['account_email_verification_code']['at']
        for _ in range(3):
            cache.clear()
            self.send_code()
            self.assertEqual(self.client.session['account_email_verification_code']['at'], original)
        cache.clear()
        response = self.request('put', AUTH + 'account/email', {'email': EMAIL})
        self.assertEqual(response.status_code, 403, response.content)

    def test_failed_resend_preserves_the_previous_code_and_expiration(self):
        self.signup()
        with patch('accounts.adapters.SchoolAccountAdapter.generate_email_verification_code', return_value='123456'):
            old_code = self.send_code()
        previous = dict(self.client.session['account_email_verification_code'])
        cache.clear()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            with patch('accounts.adapters.SchoolAccountAdapter.generate_email_verification_code', return_value='654321'):
                with patch('django.core.mail.backends.smtp.EmailBackend.open', side_effect=smtplib.SMTPException('private')):
                    response = self.request('put', AUTH + 'account/email', {'email': EMAIL})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.session['account_email_verification_code'], previous)
        self.assertEqual(self.request('post', AUTH + 'auth/email/verify', {'key': old_code}).status_code, 200)

    def test_contacts_whitelist_and_verification_binding(self):
        user = self.signup()
        address = EmailAddress.objects.get(user=user)
        address.verified = True
        address.save()
        response = self.request('patch', '/api/v1/accounts/me/', {'wechat_id': 'student_demo'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['account_eligibility']['eligible'])
        self.assertIsNotNone(response.json()['contact_updated_at'])
        for field, value in [('email', 'other@tongji.edu.cn'), ('is_staff', True), ('school_email_verified', True)]:
            self.assertEqual(self.request('patch', '/api/v1/accounts/me/', {field: value}).status_code, 400)
        user.refresh_from_db()
        address.email = 'previous@tongji.edu.cn'
        address.save()
        self.assertFalse(school_email_verified(user))
        self.assertFalse(account_eligibility(user)['eligible'])

    def test_email_self_rebinding_endpoints_are_closed(self):
        self.signup()
        for method in ('post', 'patch', 'delete'):
            self.assertEqual(self.request(method, AUTH + 'account/email', {'email': 'other@tongji.edu.cn'}).status_code, 405)
        self.assertEqual(self.client.get('/api/auth/app/v1/auth/session').status_code, 404)

    def test_current_restriction_blocks_only_new_business_actions(self):
        user = self.signup()
        user.wechat_id = 'student_demo'
        user.save()
        EmailAddress.objects.filter(user=user).update(verified=True)
        now = timezone.now()
        UserRestriction.objects.create(user=user, created_by=user, reason='测试限制', starts_at=now,
            expires_at=now + timedelta(hours=24))
        self.assertIn('account_restricted', account_eligibility(user)['reasons'])
        self.assertEqual(self.client.get('/api/v1/accounts/me/').status_code, 200)
        self.assertEqual(self.request('patch', '/api/v1/accounts/me/', {'wechat_id': 'updated_demo'}).status_code, 200)

    def test_password_reset_uses_code_and_requires_login_again(self):
        user = self.signup()
        self.request('delete', AUTH + 'auth/session')
        response = self.request('post', AUTH + 'auth/password/request', {'email': EMAIL})
        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn({'id': 'password_reset_by_code', 'is_pending': True}, response.json()['data']['flows'])
        code = re.search(r'验证码：(\S+)', mail.outbox[-1].body).group(1)
        response = self.request('post', AUTH + 'auth/password/reset', {'key': code, 'password': 'NewForest!River95'})
        self.assertEqual(response.status_code, 401, response.content)
        self.assertFalse(response.json()['meta']['is_authenticated'])
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewForest!River95'))

    def test_user_admin_uses_email_form_and_disallows_manual_verification(self):
        admin_user = User.objects.create_superuser('admin-rounds@tongji.edu.cn', PASSWORD)
        self.client.force_login(admin_user, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.get('/admin/accounts/user/add/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertNotContains(response, 'name="username"')
        self.assertEqual(self.client.get('/admin/account/emailaddress/add/').status_code, 403)
