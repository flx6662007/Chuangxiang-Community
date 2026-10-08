from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .locks import source_mutex


class SourceMutexContractTests(SimpleTestCase):
    def test_old_service_import_keeps_same_lock(self):
        from .services import source_mutex as old_mutex
        self.assertIs(old_mutex, source_mutex)

    @patch('ingestion.locks.connection')
    def test_acquired_lock_is_released_when_body_fails(self, connection):
        connection.vendor = 'postgresql'
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = [True]
        with self.assertRaisesRegex(RuntimeError, 'caller failed'):
            with source_mutex(771) as acquired:
                self.assertTrue(acquired)
                raise RuntimeError('caller failed')
        calls = cursor.execute.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[0], 'SELECT pg_try_advisory_lock(%s)')
        self.assertEqual(calls[1].args[0], 'SELECT pg_advisory_unlock(%s)')
        self.assertEqual(calls[0].args[1], calls[1].args[1])

    @patch('ingestion.locks.connection')
    def test_busy_lock_does_not_unlock_other_owner(self, connection):
        connection.vendor = 'postgresql'
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = [False]
        with source_mutex('catalog-attachments') as acquired:
            self.assertFalse(acquired)
        self.assertEqual(cursor.execute.call_count, 1)

    @patch('ingestion.locks.connection')
    def test_non_postgresql_still_rejected(self, connection):
        connection.vendor = 'sqlite'
        with self.assertRaises(ValidationError):
            with source_mutex(771):
                self.fail('unsupported database acquired a lock')
        connection.cursor.assert_not_called()
