"""增量准备隔离内测账号，可将负责人总表和个人邀请导出到私有目录。"""
import json
import os
import re
import secrets
import tempfile
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit

from allauth.account.internal.flows.email_verification_by_code import EmailVerificationProcess
from allauth.core.context import request_context
from allauth.headless.account.inputs import VerifyEmailInput
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.http import HttpRequest
from django.utils import timezone

from accounts.adapters import ensure_email_record
from accounts.permissions import school_email_verified


PURPOSE = 'private-beta-test-accounts'
FILE_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
MAX_STUDENTS = 50
SUMMARY_MARKER = '<!-- chuangxiang-private-beta-credentials v1 -->'
INVITATION_MARKER = '<!-- chuangxiang-private-beta-invitation v1 -->'


def account_specs(students=5):
    if type(students) is not int or not 1 <= students <= MAX_STUDENTS:
        raise CommandError('学生测试账号数量必须为 1 至 50 的整数。')
    return [(role, number, f'private-beta-test-{role}-{number:02}@tongji.edu.cn')
            for role, count in (('student', students), ('admin', 2)) for number in range(1, count + 1)]


ACCOUNT_SPECS = account_specs()
ALL_ACCOUNT_SPECS = account_specs(MAX_STUDENTS)
ALLOWED_EMAILS = {email for _, _, email in ALL_ACCOUNT_SPECS}
ADMIN_APPS = ('competitions', 'competition_catalog', 'resources', 'curation', 'research',
              'newsletters', 'teams', 'governance', 'notifications')


def database_identity():
    if connection.vendor != 'postgresql':
        return connection.vendor, str(connection.settings_dict.get('NAME', ''))
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        return connection.vendor, cursor.fetchone()[0]


def validate_environment(output=None):
    if getattr(settings, 'PRIVATE_BETA', False) is not True:
        raise CommandError('仅可在 PRIVATE_BETA=True 的隔离内测环境运行。')
    vendor, database = database_identity()
    if vendor != 'postgresql' or not re.fullmatch(r'chuangxiang_beta_[a-z0-9_]{1,40}', database):
        raise CommandError('仅可操作名称以 chuangxiang_beta_ 开头的独立 PostgreSQL 数据库。')
    if settings.EMAIL_BACKEND != FILE_BACKEND:
        raise CommandError('内测初始化仅支持 filebased 本地模拟邮件。')
    expected = (Path(settings.BASE_DIR).parent / '.local' / 'private-beta' / database).resolve()
    state = Path(getattr(settings, 'PRIVATE_BETA_STATE_DIR', expected)).resolve()
    if state != expected:
        raise CommandError('PRIVATE_BETA_STATE_DIR 必须位于项目 .local/private-beta/<数据库名>/。')
    if not getattr(settings, 'EMAIL_FILE_PATH', '') or Path(settings.EMAIL_FILE_PATH).resolve() != state / 'mail':
        raise CommandError('EMAIL_FILE_PATH 必须为内测状态目录下的 mail/。')
    destination = Path(output).resolve() if output else state / 'accounts.json'
    if not is_private_destination(destination, state) or destination.suffix != '.json':
        raise CommandError('凭据文件必须保存在本次内测 .local 状态目录中的 JSON 文件。')
    return database, state, destination


def read_credentials(path, database):
    if not path.exists():
        return {'schema_version': 1, 'purpose': PURPOSE, 'database': database,
                'created_at': timezone.now().isoformat(), 'accounts': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('schema_version') != 1
                or data.get('purpose') != PURPOSE or data.get('database') != database
                or not isinstance(data.get('accounts'), list)
                or any(not isinstance(row, dict) or row.get('email') not in ALLOWED_EMAILS
                       for row in data['accounts'])
                or len({row['email'] for row in data['accounts']}) != len(data['accounts'])):
            raise ValueError
        return data
    except (OSError, ValueError, TypeError):
        raise CommandError('凭据文件格式或所属数据库不符，未覆盖原文件。') from None


def write_credentials(path, data):
    write_private_text(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def write_private_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.beta-accounts-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            Path(temporary).unlink()


def is_private_destination(path, state):
    public = Path(getattr(settings, 'PRIVATE_BETA_FRONTEND_DIST',
                          Path(settings.BASE_DIR).parent / 'frontend' / 'dist')).resolve()
    blocked = [state / 'mail', state / 'cache', state / 'frontend-dist', public]
    return path.is_relative_to(state) and not any(path.is_relative_to(folder) for folder in blocked)


def markdown_destination(path, state, marker):
    path = Path(path)
    path = (path if path.is_absolute() else state / path).resolve()
    if not is_private_destination(path, state) or path.suffix.lower() != '.md':
        raise CommandError('Markdown 只能导出到本次内测的私有状态目录，不能放入公开页面或邮件目录。')
    if path.exists() and (not path.is_file() or not path.read_text(encoding='utf-8').startswith(marker + '\n')):
        raise CommandError('目标 Markdown 已存在且不是本命令生成的文件，未覆盖。')
    return path


def export_configuration(option, state):
    if option is None or option is False:
        return None
    summary = markdown_destination('内测账号清单-仅负责人.md' if option is True else option,
                                   state, SUMMARY_MARKER)
    if summary.is_relative_to((state / 'invitations').resolve()):
        raise CommandError('负责人总表不能放在个人邀请目录中。')
    invitations = {number: markdown_destination(state / 'invitations' / f'内测邀请-{number:02}.md',
                                                state, INVITATION_MARKER)
                   for number in range(1, MAX_STUDENTS + 1)}
    gate_user = getattr(settings, 'PRIVATE_BETA_USERNAME', '')
    gate_password = getattr(settings, 'PRIVATE_BETA_PASSWORD', '')
    origin = getattr(settings, 'PUBLIC_ORIGIN', '').rstrip('/')
    parsed = urlsplit(origin)
    if (not gate_user or not gate_password or parsed.scheme not in ('https', 'http')
            or not parsed.hostname or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment):
        raise CommandError('导出邀请前须配置当前访问网址及内测入口凭据。')
    return summary, invitations, origin, gate_user, gate_password


def markdown_value(value):
    value = str(value).replace('\r', '').replace('\n', ' ')
    fence = '`'
    while fence in value:
        fence += '`'
    return f'{fence} {value} {fence}'


def export_markdown(config, data, newly_created):
    summary, invitations, origin, gate_user, gate_password = config
    opening = [f'内测网址：[打开网站]({origin}/)', '',
               f'网页入口账号：{markdown_value(gate_user)}', '',
               f'网页入口口令：{markdown_value(gate_password)}', '',
               '先输入网页入口账号和口令，再到网站「内测账号」页面登录自己的测试账号。', '']
    rows = [SUMMARY_MARKER, '# 内测账号清单（仅负责人）', '',
            '本文件包含全部账号口令，只由负责人保存，不上传 GitHub；给同学分别发送对应的个人邀请。', '',
            *opening, '## 学生测试账号', '']
    specs = {email: (role, number) for role, number, email in ALL_ACCOUNT_SPECS}
    for record in data['accounts']:
        role, number = specs[record['email']]
        if role != 'student':
            continue
        note = '负责人使用（04，已分配）' if number == 4 else ('本次新增，待分配' if record['email'] in newly_created else '已有测试账号')
        password = record.get('password', '未保存现有密码，请联系负责人；本次未重置')
        rows.extend([f'### 学生 {number:02} · {note}', '',
                     f'登录账号：{markdown_value(record["email"])}', '',
                     f'登录密码：{markdown_value(password)}', ''])
        invitation = [INVITATION_MARKER, f'# 创享内测邀请 · {number:02}', '', *opening,
                      f'你的测试账号：{markdown_value(record["email"])}', '',
                      f'你的登录密码：{markdown_value(password)}', '',
                      '每人使用自己的账号，体验 AI 助手、查阅资料、发布招募、申请入队与举报。', '',
                      '账号中的邮箱和初始联系方式是测试标识，本轮不向该邮箱发送邮件。', '',
                      '临时网址会随服务重启变化；无法访问时联系负责人取得新网址。', '']
        if number == 4:
            invitation += ['此账号已分配给负责人，请勿再次分配。', '']
        write_private_text(invitations[number], '\n'.join(invitation))
    rows.extend(['## 本机管理员（仅负责人）', '',
                 '管理后台：[打开本机后台](http://127.0.0.1:8011/admin/)', '',
                 '这个地址只能在运行网站的负责人电脑上打开，不通过公网内测网址提供管理后台。', ''])
    for record in data['accounts']:
        role, number = specs[record['email']]
        if role == 'admin':
            rows.extend([f'### 管理员 {number:02}', '',
                         f'账号：{markdown_value(record["email"])}', '',
                         f'密码：{markdown_value(record.get("password", "未保存现有密码；本次未重置"))}', ''])
    rows.extend(['两名管理员分别用于举报处理和申诉复核；同一人不能复核自己作出的处理。', ''])
    write_private_text(summary, '\n'.join(rows))


def _mail_code(mail_dir, previous_sizes, email):
    codes = []
    for path in mail_dir.glob('*.log'):
        payload = path.read_bytes()[previous_sizes.get(path, 0):]
        for raw in payload.split(b'\n' + b'-' * 79 + b'\n'):
            if not raw.strip():
                continue
            message = BytesParser(policy=policy.default).parsebytes(raw)
            if email not in {address for _, address in getaddresses(message.get_all('To', []))}:
                continue
            body = message.get_body(preferencelist=('plain',))
            if body is not None:
                codes.extend(re.findall(r'验证码[：:]\s*(\d{6})', body.get_content()))
    if len(codes) != 1:
        raise CommandError('本地模拟邮件未生成唯一验证码，测试账号初始化已回滚。')
    return codes[0]


def confirm_test_email(user, mail_dir):
    if user.email not in ALLOWED_EMAILS:
        raise CommandError('只允许确认预设的 private-beta-test 测试邮箱。')
    ensure_email_record(user)
    origin = urlsplit(settings.PUBLIC_ORIGIN)
    request = HttpRequest()
    request.method = 'POST'
    request.path = '/private-beta/account-setup/'
    request.META.update(HTTP_HOST=origin.netloc or 'localhost', SERVER_NAME=origin.hostname or 'localhost',
                        SERVER_PORT=str(origin.port or (443 if origin.scheme == 'https' else 80)),
                        REMOTE_ADDR='127.0.0.1')
    request.user = user
    request.session = import_module(settings.SESSION_ENGINE).SessionStore()
    request._messages = FallbackStorage(request)
    mail_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous_sizes = {path: path.stat().st_size for path in mail_dir.glob('*.log')}
    with request_context(request):
        process = EmailVerificationProcess.initiate(request=request, user=user, email=user.email)
        if not process.did_send:
            raise CommandError('本地模拟邮件受限，请稍后重新运行初始化。')
        key = _mail_code(mail_dir, previous_sizes, user.email)
        process = EmailVerificationProcess.resume(request)
        if process is None:
            raise CommandError('本地模拟邮箱确认流程已失效。')
        form = VerifyEmailInput(data={'key': key}, process=process)
        if not form.is_valid() or process.finish() is None or not school_email_verified(user):
            raise CommandError('本地模拟验证码校验未完成，测试账号初始化已回滚。')


class Command(BaseCommand):
    help = '增量准备 1–50 个学生（默认 5）及 2 个管理员测试账号；已有账号保留，凭据仅写入私有 .local。'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=Path, help='本次内测 .local 状态目录中的凭据 JSON 路径')
        parser.add_argument('--students', type=int, default=5, choices=range(1, MAX_STUDENTS + 1),
                            help='需要的学生账号数量，1–50，默认 5；数量减少不会删除或重置已有账号。')
        parser.add_argument('--markdown', nargs='?', const=True, type=Path,
                            help='同时导出负责人总表及 invitations/个人邀请；可指定私有目录内的总表路径。')

    def handle(self, *args, **options):
        requested = {email for _, _, email in account_specs(options.get('students', 5))}
        database, state, output = validate_environment(options.get('output'))
        markdown = export_configuration(options.get('markdown'), state)
        created = preserved = 0
        newly_created = set()
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [2026100601])
            data = read_credentials(output, database)
            saved = {row['email']: row for row in data['accounts']}
            existing = set(get_user_model().objects.filter(email__in=ALLOWED_EMAILS).values_list('email', flat=True))
            retained = requested | saved.keys() | existing
            permissions = list(Permission.objects.filter(content_type__app_label__in=ADMIN_APPS).exclude(
                codename__startswith='delete_').select_related('content_type'))
            if not any(p.content_type.app_label == 'curation' and p.codename == 'add_importrun' for p in permissions):
                raise CommandError('请先完成内测数据库迁移，再初始化账号。')
            rows = []
            for role, number, email in ALL_ACCOUNT_SPECS:
                if email not in retained:
                    continue
                user = get_user_model().objects.select_for_update().filter(email=email).first()
                if user is not None:
                    preserved += 1
                    record = dict(saved.get(email, {}))
                    password = record.get('password')
                    if not isinstance(password, str) or not user.check_password(password):
                        record.pop('password', None)
                        record['credential_status'] = 'existing-password-unchanged'
                else:
                    password = secrets.token_urlsafe(24)
                    user = get_user_model().objects.create_user(
                        email=email, password=password, is_staff=role == 'admin', is_superuser=False,
                        wechat_id=f'private_beta_test_{role}_{number:02}',
                    )
                    if role == 'admin':
                        user.user_permissions.add(*permissions)
                    confirm_test_email(user, state / 'mail')
                    record = {'password': password}
                    newly_created.add(email)
                    created += 1
                record.update(email=email, role='admin' if user.is_staff else 'student',
                              user_id=user.pk, public_code=user.public_code,
                              verification='allauth-local-mail' if school_email_verified(user) else 'unverified')
                rows.append(record)
            data['accounts'] = rows
            write_credentials(output, data)
        if markdown:
            export_markdown(markdown, data, newly_created)
        self.stdout.write(self.style.SUCCESS(f'创建 {created} 个测试账号，保留 {preserved} 个已有账号。'))
        self.stdout.write(f'凭据已保存：{output}')
        if markdown:
            self.stdout.write(f'负责人总表已保存：{markdown[0]}')
            self.stdout.write(f'个人邀请已保存：{state / "invitations"}')
