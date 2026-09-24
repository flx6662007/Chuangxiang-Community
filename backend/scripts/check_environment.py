"""Check installed dependencies and the local PostgreSQL connection.

This script does not create a Django application or any database tables.
Run it with backend/.venv/Scripts/python.exe on Windows.
"""

from importlib.metadata import version
from pathlib import Path
import os
import sys

import django
from django.conf import settings
from django.db import connection


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    print("Python:", sys.version.split()[0])
    for package in ("Django", "djangorestframework", "psycopg", "python-dotenv"):
        print(f"{package}: {version(package)}")

    django.setup()
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise SystemExit('Project settings are not configured to use PostgreSQL.')
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), current_user, "
                "current_setting('server_version'), current_setting('listen_addresses')"
            )
            database, role, pg_version, host = cursor.fetchone()
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise RuntimeError("Unexpected database query result.")
        print(f"PostgreSQL: {pg_version}; database={database}; role={role}; listen={host}")
        print("PASS: Django connected to PostgreSQL and executed a query.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
