"""面向访客的科研与快讯资料；维护记录和联系人不进入响应。"""
import json
import re
from django.conf import settings

from django.db.models import Q
from django.utils import timezone

from newsletters.models import Newsletter, NewsletterItem
from research.models import ResearchOpportunity
from research.presentation import public_card_details
from common.public_content import public_text, safe_source_url

from . import selectors
from .selectors import collect_records, editorial_date, is_demo


def _day(value):
    return timezone.localtime(value).date().isoformat() if value else ''


def _card(identifier, title, *, unit='', date='', verified='', summary='',
          participation='', evidence='', source='', direction=''):
    # 白名单显式构造；不序列化模型、来源原始对象或内部信息库记录。
    return {
        'id': identifier, 'title': public_text(title), 'unit': public_text(unit),
        'date': editorial_date(date) or '', 'verifiedOn': editorial_date(verified) or '',
        'summary': public_text(summary), 'participation': public_text(participation),
        'evidenceNote': public_text(evidence), 'sourceUrl': safe_source_url(source),
        'direction': public_text(direction),
    }


def _editorial_cards(kind, reserved_urls):
    data = json.loads(selectors.EDITORIAL_PATH.read_text(encoding='utf-8'))
    for item in data.get('laboratories' if kind == 'research' else 'newsletters', []):
        identifier, title = str(item.get('id', '')), item.get('title', '')
        source = safe_source_url(item.get('sourceUrl', ''))
        if (not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', identifier) or is_demo(identifier, title)
                or item.get('publication_status', 'published') != 'published'
                or not source or source in reserved_urls):
            continue
        reserved_urls.add(source)
        card = _card('editorial-' + identifier, title, unit=item.get('unit', ''),
                    date=item.get('date'), verified=item.get('verifiedOn'),
                    summary=item.get('summary', ''), participation=item.get('participation', ''),
                    evidence=item.get('evidenceNote', ''), source=source,
                    direction=item.get('direction', ''))
        if kind == 'research':
            card['details'] = public_card_details(data.get('profiles', {}).get(identifier, {}))
        yield card


def research_cards():
    if not settings.PUBLIC_RESEARCH_ENABLED:
        return []
    # 数据库承担当前状态；下架/草稿同源记录也阻止旧人工文件重新展示。
    reserved_urls = {safe_source_url(url) for url in ResearchOpportunity.objects.values_list('official_url', flat=True)}
    queryset = ResearchOpportunity.objects.filter(publication_status='published').exclude(
        Q(code__startswith='demo-') | Q(title__contains='【虚构样例】'),
    ).prefetch_related('directions').order_by('-published_at', '-pk')
    cards, seen = [], set()
    for item in queryset:
        source = safe_source_url(item.official_url)
        if source and source in seen:
            continue
        if source:
            seen.add(source)
        participation = [item.eligibility, item.duration_text]
        if item.is_closed:
            participation.append('该次招募已结束')
        elif item.deadline_on:
            participation.append(f'申请截止：{item.deadline_on.isoformat()}')
        elif item.deadline_mode == 'ongoing':
            participation.append('长期招募')
        card = _card(
            f'db-{item.pk}', item.title, unit=item.institution or item.recruiting_entity,
            date=item.source_published_on.isoformat() if item.source_published_on else '',
            verified=_day(item.last_verified_at), summary=item.summary or item.description,
            participation=' · '.join(filter(None, participation)), evidence=item.requirements,
            source=source, direction=' / '.join(entry.name for entry in item.directions.all()),
        )
        card['details'] = public_card_details(item.card_details)
        cards.append(card)
    cards.extend(_editorial_cards('research', reserved_urls))
    return cards


def newsletter_cards():
    # 仅明确指向本期已确认版本的公开记录；后续草稿和旧版本不参与读取。
    current = {
        f'db-{item.pk}': item for item in Newsletter.objects.filter(
            publication_status='published', current_revision__status='confirmed',
        ).exclude(code__startswith='demo-').select_related('current_revision')
        if item.current_revision.newsletter_id == item.pk
    }
    reserved_urls = {safe_source_url(url) for url in NewsletterItem.objects.values_list('source_url', flat=True)}
    cards = []
    for row in collect_records(['newsletter']) if current else []:
        item = current.get(row['id'])
        # 聚合器会去掉撤下、版本已变更的引用，以及含失效引用的旧导读。
        if not item or not row['text'] or not row['source_urls']:
            continue
        cards.append(_card(
            row['id'], row['title'], date=_day(item.published_at),
            verified=_day(item.current_revision.confirmed_at), summary=row['text'],
            source=row['source_urls'][0],
        ))
    cards.extend(_editorial_cards('newsletter', reserved_urls))
    return cards


def search_cards(cards, query):
    words = query.casefold().split()
    fields = ('title', 'unit', 'summary', 'participation', 'evidenceNote', 'direction')
    return [item for item in cards if all(word in ('\n'.join(item[key] for key in fields) + json.dumps(item.get('details', {}), ensure_ascii=False)).casefold() for word in words)]
