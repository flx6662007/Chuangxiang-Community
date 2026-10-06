"""Archive the old public fixture in the copied AI beta database, without deleting history.

Run with PRIVATE_BETA_ENV_FILE pointing to this beta's private configuration:
  python scripts/retire-private-beta-snapshot.py --snapshot <public-content.json> --actor-id 6
Append --apply only after inspecting the preview. This is a one-off beta migration,
not a production maintenance command. It never reassigns a team to another edition.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DATABASE = 'chuangxiang_beta_20261006_ai'
VERSION = 'd744beaf5c993b25'
PREFIXES = ('final-', 'learning-', 'knowledge-edition-', 'knowledge-next-', 'knowledge-resource-')
EXPECTED = {'competitions.competition': 197, 'resources.resource': 430, 'curation.knowledgedocument': 813}
REASON = '内测副本迁移至统一赛事知识版本 d744beaf5c993b25；旧资料保留历史，队伍仍属于原赛事届次。'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_snapshot(path):
    raw = path.resolve(strict=True).read_bytes()
    rows = json.loads(raw)
    require(isinstance(rows, list), '快照必须是公开资料 JSON fixture。')
    selected = {label: {} for label in EXPECTED}
    for row in rows:
        require(isinstance(row, dict), '快照记录格式错误。')
        label = row.get('model')
        if label not in selected:
            continue
        pk, fields = row.get('pk'), row.get('fields')
        require(type(pk) is int and pk > 0 and isinstance(fields, dict), '快照主键或字段无效。')
        code = fields.get('code')
        require(isinstance(code, str) and code and not code.startswith(PREFIXES), '旧快照不能包含新版资料编码。')
        require(pk not in selected[label], '快照含重复主键。')
        require(code not in {r['code'] for r in selected[label].values()}, '快照含重复编码。')
        selected[label][pk] = fields
    require({label: len(items) for label, items in selected.items()} == EXPECTED,
            '快照数量不是本次 197 赛事 / 430 资源 / 813 文档，拒绝执行。')
    return selected, hashlib.sha256(raw).hexdigest()


def check_database():
    from django.conf import settings
    from django.db import connection
    require(getattr(settings, 'PRIVATE_BETA', False) is True, '仅允许 PRIVATE_BETA 配置。')
    require(connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == DATABASE,
            f'仅允许副本数据库 {DATABASE}。')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        require(cursor.fetchone()[0] == DATABASE, '实际数据库与配置不一致。')
    state = Path(settings.PRIVATE_BETA_STATE_DIR).resolve()
    expected = (ROOT / '.local' / 'private-beta' / DATABASE).resolve()
    require(state == expected, '审计目录必须在本工作树对应内测目录。')
    return state


def check_release():
    from curation.activation import PACKAGE, _latest
    from curation.knowledge_loader import load_knowledge_packages
    from curation.models import ImportedObject, KnowledgeDocument
    from competitions.models import Competition
    from competitions.recruitment_policy import target_code
    from django.utils import timezone
    from information_library.competition_search import database_corpus
    from resources.models import Resource
    packages, version = load_knowledge_packages()
    require(version == VERSION, '当前代码资料包不是本次约定版本。')
    documents = {row['code'] for p in packages for row in p['documents']}
    require(len(documents) == 198, '新版资料包文档数量不是 198。')
    require(KnowledgeDocument.objects.filter(code__in=documents, review_status__in=('approved', 'published')).count() == 198,
            '新版 198 篇知识文档尚未全部启用。')
    require(ImportedObject.objects.filter(kind='document', code__in=documents,
            package_id__in=[p['package_id'] for p in packages]).count() == 198, '新版文档导入归属不完整。')
    corpus = database_corpus()
    records = corpus['records']
    require(not corpus.get('diagnostics') and len(records) == 198, '公开结构化语料不完整或存在异常。')
    codes = {target_code(record, timezone.now()) for record in _latest(records)}
    require(len(codes) == 188, '本次新版赛事目标数量不是 188。')
    require(Competition.objects.filter(code__in=codes, publication_status='published').count() == 188,
            '新版 188 个赛事目标尚未全部激活。')
    require(ImportedObject.objects.filter(kind='competition', package_id=PACKAGE, code__in=codes).count() == 188,
            '新版赛事目标导入归属不完整。')
    urls = {resource['url'] for record in records for resource in record.get('learning_resources', [])}
    resource_codes = {'knowledge-resource-' + hashlib.sha256(url.encode()).hexdigest()[:24] for url in urls}
    require(len(resource_codes) == 302, '本次新版学习资源数量不是 302。')
    require(Resource.objects.filter(code__in=resource_codes, publication_status='published', availability='available').count() == 302,
            '新版学习资源尚未全部公开。')
    return {'version': version, 'documents': 198, 'targets': 188, 'resources': 302,
            'database_corpus_version': corpus['version']}


def checked_objects(snapshot):
    from django.apps import apps
    from curation.models import ImportedObject
    objects = {}
    for label, records in snapshot.items():
        model = apps.get_model(label)
        # Competition services acquire user -> competition -> team locks themselves.
        items = list(model.objects.filter(pk__in=records).order_by('pk'))
        require(len(items) == len(records), f'{label} 存在缺失的旧快照对象。')
        for obj in items:
            original = records[obj.pk]
            require(obj.code == original['code'] and not obj.code.startswith(PREFIXES), f'{label} 旧对象身份已变化。')
            if label == 'curation.knowledgedocument':
                require(obj.current_revision_id == original['current_revision'], '旧知识正文版本已变化，须重新审阅。')
                status = obj.review_status
            else:
                require(obj.title == original['title'], '旧资料标题已变化，须重新审阅。')
                status = obj.publication_status
            require(status in ('published', 'approved', 'withdrawn'), '旧快照对象状态已变化，拒绝批量归档。')
        # The sanitized old fixture contains no import ownership; do not fabricate it.
        kind = {'competitions.competition': 'competition', 'resources.resource': 'resource',
                'curation.knowledgedocument': 'document'}[label]
        require(not ImportedObject.objects.filter(kind=kind, code__in=[o.code for o in items]).exists(),
                '旧对象已关联导入记录，不能按无归属快照处理。')
        objects[label] = items
    return objects


def state_snapshot(objects):
    from django.apps import apps
    from teams.models import Team, Membership, Recruitment, Application
    result = {}
    for label, items in objects.items():
        model = apps.get_model(label)
        fields = ['id', 'code', 'review_status', 'current_revision_id'] if label == 'curation.knowledgedocument' else [
            'id', 'code', 'publication_status', 'withdrawal_reason']
        if label == 'competitions.competition':
            fields += ['recruitment_enabled']
        result[label] = list(model.objects.filter(pk__in=[o.pk for o in items]).order_by('pk').values(*fields))
    result['teams'] = list(Team.objects.order_by('pk').values('id', 'code', 'competition_id', 'recruiter_id', 'dissolved_at'))
    result['memberships'] = list(Membership.objects.order_by('pk').values('id', 'team_id', 'competition_id', 'user_id', 'ended_at'))
    result['recruitments'] = list(Recruitment.objects.order_by('pk').values('id', 'team_id', 'publication_status', 'closed_at', 'close_reason'))
    result['applications'] = list(Application.objects.order_by('pk').values('id', 'recruitment_id', 'status', 'end_reason'))
    # Preserve report identity and target references, without putting report prose in this log.
    report = apps.get_model('governance', 'Report')
    fields = [f.attname for f in report._meta.concrete_fields if f.primary_key or f.is_relation]
    result['reports'] = list(report.objects.order_by('pk').values(*fields))
    return result


def archive(objects, actor):
    from competitions.services import withdraw_competition
    from curation.services import review_document
    from governance.models import AdminAction
    # Services settle old recruitment/applications; existing teams and membership FKs stay put.
    for item in objects['competitions.competition']:
        if item.publication_status == 'published':
            withdraw_competition(item.pk, actor=actor, reason=REASON)
    for item in objects['curation.knowledgedocument']:
        if item.review_status != 'withdrawn':
            review_document(item.code, revision=item.current_revision.version, status='withdrawn', reason=REASON, actor=actor)
    for item in objects['resources.resource']:
        if item.publication_status == 'withdrawn':
            continue
        # No resource-withdraw service exists. This explicit status-only transition uses
        # model validation + immutable AdminAction, within the same guarded transaction.
        item.publication_status, item.withdrawal_reason, item.updated_by = 'withdrawn', REASON, actor
        item.full_clean()
        item.save(update_fields=['publication_status', 'withdrawal_reason', 'updated_by', 'updated_at'])
        audit = AdminAction(action='withdraw', resource=item, actor=actor, reason=REASON,
                            changes={'before_status': 'published', 'after_status': 'withdrawn'})
        audit.full_clean()
        audit.save()


def verify_preserved(before, after):
    for key, fields in (
        ('teams', ('id', 'code', 'competition_id', 'recruiter_id')),
        ('memberships', ('id', 'team_id', 'competition_id', 'user_id')),
        ('recruitments', ('id', 'team_id')), ('applications', ('id', 'recruitment_id')),
    ):
        project = lambda rows: [{f: row[f] for f in fields} for row in rows]
        require(project(before[key]) == project(after[key]), f'{key} 身份或归属被改变，事务回滚。')
    require(before['reports'] == after['reports'], '举报记录身份或目标发生变化，事务回滚。')
    for label in EXPECTED:
        field = 'review_status' if label == 'curation.knowledgedocument' else 'publication_status'
        require(all(row[field] == 'withdrawn' for row in after[label]), '旧公开资料未全部归档。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--actor-id', required=True, type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    snapshot, digest = read_snapshot(args.snapshot)
    sys.path.insert(0, str(ROOT / 'backend'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.private_beta_settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.serializers.json import DjangoJSONEncoder
    from django.db import connection, transaction
    from django.utils import timezone
    state = check_database()
    actor = get_user_model().objects.get(pk=args.actor_id)
    require(actor.is_active and actor.is_staff and actor.has_perms([
        'competitions.change_competition', 'resources.change_resource', 'governance.add_adminaction',
        'curation.change_knowledgedocument', 'curation.add_documentreview',
    ]), '维护者缺少归档及审计权限。')
    report = {'database': DATABASE, 'snapshot_sha256': digest, 'snapshot': str(args.snapshot.resolve()),
              'actor_id': actor.pk, 'reason': REASON, 'mode': 'apply' if args.apply else 'preview', 'committed': False}
    path = state / ('retire-snapshot-' + timezone.now().strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    def write_report():
        temporary = path.with_suffix('.writing')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder) + '\n', encoding='utf-8')
        temporary.replace(path)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [2026131255])
        report['release'] = check_release()
        objects = checked_objects(snapshot)
        before = state_snapshot(objects)
        report['before'] = before
        report['planned'] = {label: sum((o.review_status if label == 'curation.knowledgedocument' else o.publication_status) != 'withdrawn'
                                      for o in rows) for label, rows in objects.items()}
        write_report()
        if args.apply:
            archive(objects, actor)
            report['after'] = state_snapshot(objects)
            verify_preserved(before, report['after'])
            report['release_after'] = check_release()
            write_report()  # Audit must be writable before the transaction can commit.
    report['committed'] = args.apply
    try:
        write_report()
    except OSError:
        # A final filesystem failure cannot roll back an already committed DB transaction.
        print(json.dumps({'committed': args.apply, 'audit_finalization': 'failed', 'report': str(path)}))
        return 1
    print(json.dumps({'mode': report['mode'], 'committed': report['committed'], 'planned': report['planned'],
                      'release': report['release'], 'report': str(path)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # DB driver errors can contain connection details; never print their text.
        if isinstance(error, (RuntimeError, ValueError, FileNotFoundError)):
            print(f'未执行或已回滚：{error}', file=sys.stderr)
        else:
            print(f'未执行或已回滚（{type(error).__name__}）。请在受控本地环境检查。', file=sys.stderr)
        sys.exit(1)
