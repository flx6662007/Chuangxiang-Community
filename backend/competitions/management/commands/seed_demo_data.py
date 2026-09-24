"""按稳定编码补充虚构开发数据；整批事务、重复执行保留已有记录。"""

from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy


MARKER = '【虚构样例】'
PREFIX = 'demo-r1-'


class Command(BaseCommand):
    help = '导入虚构开发数据（默认 25 条公开赛事、2 条草稿、1 条下架）；仅 DEBUG=1 可用。'
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--published-count', type=int, default=25, help='公开样例数量，1 到 500；默认 25。')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('虚构样例仅限本地开发环境，请使用 DJANGO_DEBUG=1 的开发配置。')
        count = options['published_count']
        if not 1 <= count <= 500:
            raise CommandError('--published-count 必须在 1 到 500 之间。')

        self.now = timezone.now()
        self.today = timezone.localdate(self.now)
        created = {'users': 0, 'taxonomies': 0, 'competitions': 0, 'sources': 0}
        users = []
        User = get_user_model()
        for index in range(1, 4):
            email = f'cxdemo-r1-{index:03d}@tongji.edu.cn'
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email, password=None, is_active=False,
                    wechat_id='fictional_demo_02' if index == 2 else '',
                    phone_number='+1 202-555-0100' if index == 3 else '',
                )
                created['users'] += 1
            elif user.is_active or user.is_staff or user.is_superuser or user.has_usable_password():
                raise CommandError(f'样例邮箱已被非样例账号占用：{email}；本次导入已回滚。')
            users.append(user)

        categories, tags = [], []
        for kind, names, output in (
            ('category', ('工程设计', '数字创意', '基础研究'), categories),
            ('tag', ('新手体验', '跨学科', '作品展示'), tags),
        ):
            for index, name in enumerate(names, 1):
                code = f'{PREFIX}{kind}-{index}'
                item = CompetitionTaxonomy.objects.filter(code=code).first()
                if item is None:
                    item = CompetitionTaxonomy(code=code, kind=kind, name=MARKER + name, sort_order=index)
                    item.full_clean()
                    item.save()
                    created['taxonomies'] += 1
                elif item.kind != kind or not item.name.startswith(MARKER) or not item.is_active:
                    raise CommandError(f'样例词条编码冲突或已停用：{code}；本次导入已回滚。')
                output.append(item)

        for index in range(1, count + 1):
            self.add_competition(f'{PREFIX}public-{index:03d}', index, 'published', users[0], categories, tags, created)
        for index in range(1, 3):
            self.add_competition(f'{PREFIX}draft-{index:03d}', index, 'draft', users[0], categories, tags, created)
        self.add_competition(f'{PREFIX}withdrawn-001', 1, 'withdrawn', users[0], categories, tags, created)

        self.stdout.write(self.style.SUCCESS(
            '虚构样例导入完成；新增 ' + ', '.join(f'{key}={value}' for key, value in created.items())
            + '。已有稳定编码记录保持原样；未发送邮件，样例账号不可登录。'
        ))

    def add_competition(self, code, index, status, creator, categories, tags, created):
        existing = Competition.objects.filter(code=code).first()
        if existing:
            if not existing.title.startswith(MARKER):
                raise CommandError(f'赛事编码已被非样例记录占用：{code}；本次导入已回滚。')
            return

        competition = Competition(
            code=code, title=f'{MARKER}{dict(Competition.PublicationStatus.choices)[status]}科创挑战 {index:03d}',
            edition='虚构演示届次', created_by=creator, updated_by=creator,
        )
        if status == 'draft':
            # 一个最小草稿、一个已有部分简介的草稿，均保留未知日期。
            competition.summary = MARKER + '资料待补齐。' if index == 2 else ''
            competition.full_clean()
            competition.save()
            created['competitions'] += 1
            return

        competition.category = categories[(index - 1) % len(categories)]
        competition.summary = MARKER + '仅用于列表、筛选和分页联调，不接受真实报名。'
        competition.description = MARKER + '全部名称、资格、来源与时间均为虚构；核验时间仅模拟状态，不代表核实真实通知。'
        competition.organizer = MARKER + '演示主办方'
        competition.eligibility = MARKER + '模拟学生参赛资格'
        competition.level = ('university', 'national', 'unknown')[(index - 1) % 3]
        competition.participation_type = ('team', 'individual', 'both', 'unknown')[(index - 1) % 4]
        if competition.participation_type in ('team', 'both'):
            competition.team_size_min, competition.team_size_max = 2, 5
        competition.registration_url = f'https://example.org/{code}/registration'
        competition.registration_method = MARKER + '占位入口，不提交真实信息。'

        scenario = (index - 1) % 6
        future_day = self.today + timedelta(days=30 + index)
        if scenario == 0:
            competition.deadline_notes = MARKER + '来源未说明截止日期，保持空值。'
        elif scenario == 1:
            competition.registration_deadline = future_day
            competition.deadline_notes = MARKER + '仅给出日期，不补造截止时刻。'
        elif scenario == 2:
            competition.registration_deadline = future_day
            competition.registration_deadline_at = datetime.combine(
                future_day - timedelta(days=1), time(18), tzinfo=dt_timezone.utc,
            )
            competition.registration_deadline_timezone = 'Asia/Shanghai'
        elif scenario == 3:
            competition.registration_deadline = self.today - timedelta(days=7)
            competition.deadline_notes = MARKER + '报名已截止，仍保留公开历史资讯。'
        elif scenario == 4:
            zone = dt_timezone(timedelta(hours=-5))
            competition.submission_deadline = future_day
            competition.submission_deadline_at = datetime.combine(future_day, time(23, 30), tzinfo=zone)
            competition.submission_deadline_timezone = '-05:00'
        else:
            competition.campus_arrangements = MARKER + '模拟校内选拔，由虚构校内来源支持。'
            competition.campus_deadline = future_day - timedelta(days=5)
            competition.registration_deadline = future_day

        # 先保存草稿与关联，再执行发布校验；整个命令处于同一事务。
        competition.full_clean()
        competition.save()
        created['competitions'] += 1
        competition.tags.set([tags[(index - 1) % len(tags)]])
        for source_type in (('official', 'campus') if scenario == 5 else ('official',)):
            source = CompetitionSource(
                competition=competition, source_type=source_type,
                source_name=MARKER + ('赛事官方来源' if source_type == 'official' else '校内来源'),
                source_url=f'https://example.org/{code}/{source_type}',
                is_primary=source_type == 'official', source_published_on=self.today,
                last_verified_at=self.now,
            )
            source.full_clean()
            source.save()
            created['sources'] += 1

        competition.publication_status = 'published'
        competition.published_at = self.now - timedelta(minutes=index)
        competition.last_verified_at = self.now
        if status == 'published' and scenario == 2 and competition.participation_type in ('team', 'both'):
            competition.recruitment_enabled = True
            competition.recruitment_deadline = self.now + timedelta(days=14)
            competition.recruitment_note = MARKER + '模拟已确认的统一招募期限。'
        competition.full_clean()
        competition.save()
        if status == 'withdrawn':
            competition.publication_status = 'withdrawn'
            competition.withdrawal_reason = MARKER + '用于验证下架筛选，不应出现在公开列表。'
            competition.full_clean()
            competition.save()
