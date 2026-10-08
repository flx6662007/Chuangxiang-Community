"""采集来源互斥；避免调用方为使用锁加载采纳和发布服务。"""
from contextlib import contextmanager
import hashlib

from django.core.exceptions import ValidationError
from django.db import connection


@contextmanager
def source_mutex(source_id):
    """连接级 PostgreSQL advisory lock；不在整个网络请求期间持有事务/行锁。"""
    if connection.vendor != 'postgresql':
        raise ValidationError('持续采集需要 PostgreSQL 来源级互斥。')
    key = int.from_bytes(hashlib.sha256(f'chuangxiang-ingestion-{source_id}'.encode()).digest()[:8], 'big', signed=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [key])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [key])
