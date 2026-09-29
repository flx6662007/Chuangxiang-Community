"""Read bounded public rule attachments into separately versioned source records."""
from collections import Counter
from datetime import timedelta
import json
import math
import re
import time
from urllib.parse import unquote

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from competition_catalog.attachments import fetch_attachment
from competition_catalog.models import OfficialNotice
from competition_catalog.monitor import NOTICE_WORDS, related_title, save_page
from ingestion.http import FetchError, OfficialClient, Page
from ingestion.services import source_mutex


SUBMISSION_WORDS = re.compile(
    r'(?<![a-z])(?:claimants?|respondents?|memoranda|memorandum|best[\s_-]*memorials?|memorials?)(?![a-z])'
    r'|选手提交|参赛论文|参赛文书|获奖文书', re.I)
RULE_DOCUMENT_WORDS = re.compile(
    r'(?<![a-z])(?:rules?|regulations?|registration|invitations?)(?![a-z])'
    r'|报名|章程|竞赛规则|邀请函', re.I)


def is_submission_attachment(attachment):
    title = str(attachment.get('title', ''))
    url = unquote(attachment['url'])
    filename = url.rsplit('/', 1)[-1].split('?', 1)[0]
    # Rules for claimants 等仍是规则；目录名含 memoranda 不能挡住规则文件。
    return bool(SUBMISSION_WORDS.search(title + ' ' + url)
                and not RULE_DOCUMENT_WORDS.search(title + ' ' + filename))


def attempt_time(value):
    """历史缺失或无效记录视为未尝试；只向 JSON 写有限时间戳。"""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return value if math.isfinite(value) and value > 0 else 0


def eligible_attachments(notice):
    if re.search(r'获奖|公示|名单|颁奖|观赛|住宿|研学|圆满|成功举办', notice.title):
        return []
    return [attachment for attachment in notice.attachments
            if isinstance(attachment, dict) and isinstance(attachment.get('url'), str)
            and re.search(r'\.(?:pdf|docx)(?:$|[?#])', attachment['url'], re.I)
            and not re.search(r'获奖|名单|公示|回执|发票|报销|同意表|通讯录', str(attachment.get('title', '')))
            and not is_submission_attachment(attachment)
            and (notice.page_kind == 'notice'
                 or related_title(notice.site, str(attachment.get('title', '')))
                 or (notice.site.dedicated and NOTICE_WORDS.search(str(attachment.get('title', '')))))]


class Command(BaseCommand):
    help = '读取已核验官网通知中的公开 PDF/DOCX 规则，分别保存原文版本；扫描件保留待处理。'

    def add_arguments(self, parser):
        parser.add_argument('--code', action='append')
        parser.add_argument('--limit', type=int, default=40, help='本轮附件数量上限，1—200')
        parser.add_argument('--max-per-notice', type=int, default=2)
        parser.add_argument('--max-seconds', type=int, default=300,
                            help='本轮软时间预算，10—1800 秒；当前附件完成保存后停止')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 200 or not 1 <= options['max_per_notice'] <= 5:
            raise CommandError('limit必须为1—200，max-per-notice必须为1—5。')
        if not 10 <= options['max_seconds'] <= 1800:
            raise CommandError('max-seconds必须为10—1800。')
        started = time.monotonic()
        counts, clients, seen, selected = Counter(), {}, set(), Counter()

        def time_exhausted():
            if time.monotonic() - started >= options['max_seconds']:
                counts['time_budget_reached'] = 1
                return True
            return False

        with source_mutex('catalog-attachments') as acquired:
            if not acquired:
                self.stdout.write(json.dumps({'skipped': 'already_running'}))
                return
            notices = OfficialNotice.objects.filter(
                is_current_version=True, site__enabled=True, site__entry__is_active=True,
                page_kind__in=['notice', 'index'],
            ).exclude(attachments=[]).select_related('site__entry')
            if options['code']:
                notices = notices.filter(site__entry__code__in=options['code'])
            notices = notices.order_by('-source_published_on', '-last_seen_at', 'pk')
            try:
                # 先对所有候选排序，再施加每通知额度，失败的前两个不会永久抢占。
                candidates = []
                for notice in notices:
                    if time_exhausted():
                        break
                    for attachment in eligible_attachments(notice):
                        url = attachment['url']
                        key = (notice.site_id, url)
                        if key in seen:
                            continue
                        seen.add(key)
                        previous = attempt_time(notice.site.page_attempts.get('attachment:' + url))
                        candidates.append((previous, notice, url))
                candidates.sort(key=lambda row: row[0])
                for _, notice, url in candidates:
                    if counts['attempted'] >= options['limit'] or time_exhausted():
                        break
                    if selected[notice.pk] >= options['max_per_notice']:
                        continue
                    # 与普通 HTML 监测共享站点锁，refresh 后仅增改本次轮换键。
                    with source_mutex(f'catalog-{notice.site_id}') as acquired:
                        if not acquired:
                            counts['locked'] += 1
                            continue
                        site = notice.site
                        site.refresh_from_db()
                        if not site.enabled or not site.entry.is_active:
                            counts['disabled'] += 1
                            continue
                        current = OfficialNotice.objects.filter(
                            pk=notice.pk, site_id=site.pk, is_current_version=True,
                            page_kind__in=['notice', 'index'],
                        ).select_related('site__entry').first()
                        attachment = next((item for item in eligible_attachments(current)
                                           if item['url'] == url), None) if current else None
                        if attachment is None:
                            counts['obsolete'] += 1
                            continue
                        notice = current
                        cutoff = timezone.now() - timedelta(hours=6)
                        recent_success = attempt_time(site.page_attempts.get('attachment-success:' + url)) >= cutoff.timestamp()
                        if not options['force'] and (recent_success or OfficialNotice.objects.filter(
                            site_id=site.pk, url=url, is_current_version=True, last_seen_at__gte=cutoff,
                        ).exists()):
                            counts['not_due'] += 1
                            continue
                        if time_exhausted():
                            break
                        # 下载前落库，异常退出或失败也会让下一轮处理更久未尝试的附件。
                        attempts = dict(site.page_attempts)
                        attempts['attachment:' + url] = timezone.now().timestamp()
                        site.page_attempts = attempts
                        site.save(update_fields=['page_attempts'])
                        selected[notice.pk] += 1
                        counts['attempted'] += 1
                        try:
                            host_key = tuple(sorted(site.allowed_hosts))
                            if host_key not in clients:
                                clients[host_key] = OfficialClient(host_key)
                            parsed = fetch_attachment(site, attachment, client=clients[host_key])
                            parsed['title'] = (notice.title + ' / ' + parsed['title'])[:500]
                            parsed['body'] = (
                                '关联通知：' + notice.title + '\n关联通知地址：' + notice.url
                                + '\n以下为附件正文：\n' + parsed['body']
                            )
                            parsed['attachments'] = [{'title': '关联通知（网页）', 'url': notice.url}]
                            fields = {key: parsed[key] for key in (
                                'title', 'body', 'attachments', 'source_published_on', 'page_kind', 'status',
                            )}
                            created = save_page(site, Page(parsed['url'], ''), fields)
                            site.page_attempts['attachment-success:' + url] = timezone.now().timestamp()
                            site.save(update_fields=['page_attempts'])
                            counts['created' if created else 'unchanged'] += 1
                            result = {'parent_notice': notice.pk, 'catalog': site.entry.code, 'status': 'saved', 'url': parsed['url']}
                        except (FetchError, ValueError) as exc:
                            counts['failed'] += 1
                            result = {'parent_notice': notice.pk, 'catalog': site.entry.code, 'status': 'pending', 'reason': str(exc)}
                        self.stdout.write(json.dumps(result, ensure_ascii=False))
                        self.stdout.flush()
            finally:
                for client in clients.values():
                    client.close()
            self.stdout.write(json.dumps({'summary': dict(counts)}, ensure_ascii=False))
