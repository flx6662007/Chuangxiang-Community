"""Extract archived official notices and publish only validated competition records."""
from collections import Counter
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from competition_catalog.extraction import extract_notice
from competition_catalog.models import CatalogExtraction, OfficialNotice
from competition_catalog.publication import notice_snapshot, persist_extraction, publish_extraction
from competition_catalog.registry import ADAPTER_CATALOG
from competitions.services import require_editor
from ingestion.locks import source_mutex


class Command(BaseCommand):
    help = '提取学校目录官网原文；校验通过的赛事可发布，其余记录缺项和原因供后台处理。'

    def add_arguments(self, parser):
        parser.add_argument('--code', action='append', help='只处理指定目录编号，可重复')
        parser.add_argument('--notice-id', type=int, action='append', help='指定原文编号，可重复')
        parser.add_argument('--limit', type=int, default=2500)
        parser.add_argument('--actor-id', type=int, help='有赛事维护权限的现有账号')
        parser.add_argument('--publish', action='store_true', help='发布校验通过的结果')
        parser.add_argument('--scheduled', action='store_true', help='按服务端自动发布配置执行')
        parser.add_argument('--dry-run', action='store_true', help='仅提取预览，不写入数据库')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 10000:
            raise CommandError('limit 必须为1—10000。')
        publishing = options['publish'] or (options['scheduled'] and settings.CATALOG_AUTO_PUBLISH)
        actor_id = options['actor_id'] or (settings.CATALOG_PUBLISH_ACTOR_ID if options['scheduled'] else None)
        actor = None
        if publishing and not options['dry_run']:
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                for permission in ('add_competition', 'change_competition', 'add_competitionsource'):
                    require_editor(actor, permission)
            except (get_user_model().DoesNotExist, ValueError, TypeError, PermissionDenied) as exc:
                raise CommandError('发布须指定现有的赛事维护账号；本命令不会创建账号或授予权限。') from exc
        with source_mutex('catalog-publication') as acquired:
            if not acquired:
                self.stdout.write(json.dumps({'skipped': 'already_running'}))
                return
            notices = OfficialNotice.objects.filter(
                is_current_version=True, site__enabled=True, site__entry__is_active=True,
            ).exclude(site__entry__code__in=ADAPTER_CATALOG.values()).select_related('site__entry')
            if options['code']:
                notices = notices.filter(site__entry__code__in=options['code'])
            if options['notice_id']:
                notices = notices.filter(pk__in=options['notice_id'])
            # New source versions must not be starved by already-processed older entries.
            from django.db.models import Exists, OuterRef
            from competition_catalog.extraction import RULE_VERSION
            notices = notices.annotate(_already_extracted=Exists(CatalogExtraction.objects.filter(
                notice_id=OuterRef('pk'), rule_version=RULE_VERSION,
            ))).order_by('_already_extracted', 'site__entry__code', '-source_published_on', '-last_seen_at', 'pk')[:options['limit']]
            counts, publishable = Counter(), []
            for notice in notices:
                extracted = extract_notice(notice_snapshot(notice), today=timezone.localdate())
                counts['processed'] += 1
                counts[extracted['disposition']] += 1
                try:
                    record = None if options['dry_run'] else persist_extraction(notice, extracted)
                except ValidationError as exc:
                    counts['record_blocked'] += 1
                    self.stdout.write(json.dumps({'notice': notice.pk, 'publication': 'blocked', 'reason': str(exc)}, ensure_ascii=False))
                    continue
                if extracted['disposition'] in ('ready', 'historical') and not extracted.get('errors'):
                    publishable.append((notice, extracted, record))
                self.stdout.write(json.dumps({
                    'notice': notice.pk, 'catalog': notice.site.entry.code,
                    'disposition': extracted['disposition'],
                    'missing_fields': extracted.get('missing_fields', []), 'errors': extracted.get('errors', []),
                    'candidate_title': extracted.get('candidate', {}).get('title', ''),
                }, ensure_ascii=False))
            # Prefer the most complete candidate if multiple notices describe the same event.
            publishable.sort(key=lambda row: (
                len(row[1].get('missing_fields', [])),
                -(row[0].source_published_on.toordinal() if row[0].source_published_on else 0),
            ))
            seen = set()
            if publishing and not options['dry_run']:
                for notice, extracted, record in publishable:
                    code = extracted['candidate']['code']
                    if code in seen:
                        counts['same_event_pending'] += 1
                        CatalogExtraction.objects.filter(pk=record.pk, status='pending').update(
                            review_note='同一赛事已有本轮通过核验的通知；此原文保留作补充资料，未重复生成卡片。',
                        )
                        continue
                    was_published = record.competition_id is not None
                    try:
                        competition = publish_extraction(record.pk, actor=actor, mode='rules')
                    except (ValidationError, PermissionDenied) as exc:
                        counts['publication_blocked'] += 1
                        CatalogExtraction.objects.filter(pk=record.pk, status='pending').update(review_note=str(exc)[:1000])
                        self.stdout.write(json.dumps({'notice': notice.pk, 'publication': 'blocked', 'reason': str(exc)}, ensure_ascii=False))
                        continue
                    seen.add(code)
                    counts['unchanged' if was_published else 'published'] += 1
                    self.stdout.write(json.dumps({'notice': notice.pk, 'publication': 'published', 'competition_id': competition.pk}, ensure_ascii=False))
            self.stdout.write(json.dumps({'summary': dict(counts), 'dry_run': options['dry_run'], 'publish_enabled': publishing}, ensure_ascii=False))
