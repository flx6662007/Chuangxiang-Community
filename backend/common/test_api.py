"""Shared API contracts remain identical for all existing callers."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from .api import BusinessView, CompetitionPagination, StrictSerializer
from .errors import BusinessError, check


class SharedAPIContractTests(SimpleTestCase):
    def test_old_imports_keep_the_same_objects(self):
        from competitions.models import CleanFieldsModel as old_model
        from competitions.views import CompetitionPagination as old_pagination
        from teams.errors import BusinessError as old_error, check as old_check
        from teams.serializers import StrictSerializer as old_serializer
        from teams.views import BusinessView as old_view
        from .model_base import CleanFieldsModel

        for original, current in (
            (old_model, CleanFieldsModel), (old_pagination, CompetitionPagination),
            (old_error, BusinessError), (old_check, check),
            (old_serializer, StrictSerializer), (old_view, BusinessView),
        ):
            self.assertIs(original, current)

    def test_unknown_input_fields_are_rejected(self):
        class Input(StrictSerializer):
            title = serializers.CharField()

        serializer = Input(data={'title': 'valid', 'owner_id': 9, 'is_admin': True})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors, {'unknown_fields': ['is_admin', 'owner_id']})

    def test_pagination_keeps_bounds_and_validation_errors(self):
        factory = APIRequestFactory()
        paginator = CompetitionPagination()
        for params, expected in (({}, 20), ({'page_size': '4'}, 4), ({'page_size': '100'}, 50)):
            with self.subTest(params=params):
                self.assertEqual(paginator.get_page_size(Request(factory.get('/', params))), expected)
        for value in ('0', '-1', 'x', '1.5', ''):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                paginator.get_page_size(Request(factory.get('/', {'page_size': value})))

    def test_business_view_preserves_error_envelopes(self):
        view = BusinessView()
        view.request = Request(APIRequestFactory().get('/'))
        view.args, view.kwargs = (), {}
        cases = (
            (ObjectDoesNotExist(), 404, 'not_found', None),
            (DjangoValidationError({'title': ['invalid']}), 400, 'invalid_fields', {'title': ['invalid']}),
            (ValidationError({'unknown_fields': ['owner_id']}), 400, 'invalid_fields', {'unknown_fields': ['owner_id']}),
            (IntegrityError('private SQL detail'), 409, 'conflict', None),
        )
        for error, status, code, fields in cases:
            with self.subTest(error=type(error).__name__):
                response = view.handle_exception(error)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.data['code'], code)
                self.assertEqual(response.data.get('fields'), fields)
                self.assertNotIn('private SQL detail', str(response.data))

    def test_common_view_does_not_broaden_permissions(self):
        from rest_framework.views import APIView
        self.assertIs(BusinessView.permission_classes, APIView.permission_classes)
        self.assertIs(BusinessView.authentication_classes, APIView.authentication_classes)
