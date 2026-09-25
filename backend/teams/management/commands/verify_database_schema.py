"""只读核对项目表、列、命名约束、索引和迁移状态。"""
import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone


PROJECT_APPS = {'accounts','competitions','teams','research','resources','newsletters','favorites','governance','notifications','ingestion'}


class Command(BaseCommand):
    help = '只读检查实际数据库与项目模型/迁移是否一致，输出不含密码的 JSON。'

    def handle(self, *args, **options):
        executor=MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError('存在尚未应用的迁移。')
        tables=set(connection.introspection.table_names())
        if 'auth_user' in tables:
            raise CommandError('检测到不应使用的默认 auth_user 表。')
        result={}
        with connection.cursor() as cursor:
            for model in apps.get_models(include_auto_created=True):
                if model._meta.app_label not in PROJECT_APPS:continue
                table=model._meta.db_table
                if table not in tables:raise CommandError(f'缺失表：{table}')
                actual=connection.introspection.get_constraints(cursor,table)
                columns={c.name:c for c in connection.introspection.get_table_description(cursor,table)}
                for field in model._meta.local_fields:
                    if field.column not in columns or columns[field.column].null_ok != field.null:
                        raise CommandError(f'缺失字段或 NULL 约束不符：{table}.{field.column}')
                    if field.is_relation and not any(v.get('foreign_key') and v['columns']==[field.column] for v in actual.values()):
                        raise CommandError(f'缺少外键：{table}.{field.column}')
                for constraint in model._meta.constraints:
                    if constraint.name not in actual:raise CommandError(f'缺少命名约束：{constraint.name}')
                for index in model._meta.indexes:
                    if index.name not in actual or not actual[index.name]['index']:raise CommandError(f'缺少索引：{index.name}')
                result[table]={'rows':model.objects.count(),'columns':len(columns),'named_constraints':len(model._meta.constraints),'declared_indexes':len(model._meta.indexes)}
            if connection.vendor=='postgresql':
                cursor.execute('SELECT version()')
                version=cursor.fetchone()[0].split(',')[0]
            else:version=connection.vendor
        report={'checked_at':timezone.now().isoformat(),'database':connection.settings_dict['NAME'],
                'engine':version,'total_tables':len(tables),'project_tables':len(result),
                'applied_migrations':len(MigrationRecorder(connection).applied_migrations()),
                'named_constraints':sum(v['named_constraints'] for v in result.values()),
                'declared_indexes':sum(v['declared_indexes'] for v in result.values()),'tables':result}
        self.stdout.write(json.dumps(report,ensure_ascii=False,indent=2))
