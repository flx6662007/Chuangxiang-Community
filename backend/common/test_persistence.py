from unittest.mock import Mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .persistence import clean_save


class CleanSaveTests(SimpleTestCase):
    def test_validation_failure_prevents_writes(self):
        obj = Mock()
        obj.full_clean.side_effect = ValidationError('invalid fields')
        with self.assertRaises(ValidationError):
            clean_save(obj, update_fields=['title'])
        obj.save.assert_not_called()

    def test_update_fields_and_return_value_are_preserved(self):
        obj = Mock()
        self.assertIs(clean_save(obj, update_fields=['title']), obj)
        self.assertEqual([call[0] for call in obj.mock_calls], ['full_clean', 'save'])
        obj.save.assert_called_once_with(update_fields=['title'])
