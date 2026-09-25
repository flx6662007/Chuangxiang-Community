"""在一次性空 PostgreSQL 数据库验证完整迁移与样例，最后只删除本脚本创建的库。"""
import io
import json
import os
from pathlib import Path
import sys
import uuid

import django
import psycopg
from psycopg import sql
from dotenv import dotenv_values, load_dotenv


def main():
    backend=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(backend))
    load_dotenv(backend/'.env')
    if os.getenv('DJANGO_DEBUG') != '1':
        raise SystemExit('Only DEBUG=1 local development is supported.')
    admin_file=backend/'.local'/'postgresql-admin.env'
    config=dotenv_values(admin_file) if admin_file.exists() else {}
    database='chuangxiang_verify_'+uuid.uuid4().hex[:12]
    kwargs={
        'host':config.get('PGHOST') or os.environ['DB_HOST'],
        'port':config.get('PGPORT') or os.environ.get('DB_PORT','5432'),
        'user':config.get('PGUSER') or os.environ['DB_USER'],
        'password':config.get('PGPASSWORD') or os.environ['DB_PASSWORD'],
        'dbname':config.get('PGDATABASE') or 'postgres',
        'autocommit':True,
    }
    created=False
    report=None
    with psycopg.connect(**kwargs) as admin:
        try:
            with admin.cursor() as cursor:
                cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s',[database])
                if cursor.fetchone():raise RuntimeError('Temporary database name collision.')
                cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(database),sql.Identifier(os.environ['DB_USER'])))
                created=True
            os.environ['DB_NAME']=database
            os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
            django.setup()
            from django.core.management import call_command
            from django.db import connection
            if connection.introspection.table_names():raise RuntimeError('Verification database was not empty.')
            output=io.StringIO()
            call_command('migrate',interactive=False,stdout=output)
            call_command('seed_demo_data',stdout=output)
            call_command('seed_remaining_demo_data',stdout=output)
            first=io.StringIO();call_command('verify_database_schema',stdout=first)
            call_command('seed_demo_data',stdout=output)
            call_command('seed_remaining_demo_data',stdout=output)
            second=io.StringIO();call_command('verify_database_schema',stdout=second)
            report=json.loads(second.getvalue())
            if json.loads(first.getvalue())['tables'] != report['tables']:
                raise RuntimeError('Repeated import changed row counts.')
            report['started_empty']=True
            report['repeat_import_counts_unchanged']=True
            report['temporary_database_removed']=False
            connection.close()
        finally:
            if created:
                # 只删除本次成功创建、使用 UUID 命名的一次性验证库。
                if 'django.db' in sys.modules:
                    from django.db import connections
                    connections.close_all()
                with admin.cursor() as cursor:
                    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
                if report:report['temporary_database_removed']=True
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
