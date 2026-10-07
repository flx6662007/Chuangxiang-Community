"""External evidence adapters. The default adapter reads registered official notices."""

from urllib.parse import urlsplit
import hashlib
from typing import Protocol

from django.utils import timezone

from competition_catalog.models import OfficialSite
from competition_catalog.monitor import normalize_name, parse_page
from ingestion.http import FetchError, OfficialClient, checked_url
from information_library.selectors import public_text, safe_source_url
from .evidence import validated_external


class ChatOfficialClient(OfficialClient):
    def __init__(self, hosts):
        # Chat latency is bounded separately from the offline catalog crawler.
        super().__init__(hosts, timeout=5, attempts=1, interval=0)

    def _check_robots(self, url):
        super()._check_robots(url)
        if self.interval > 5:
            raise FetchError('robots_delay_unsupported', '官网要求的访问间隔超出聊天请求预算。')


def _matching_site(question):
    normalized = normalize_name(question)
    for site in OfficialSite.objects.filter(enabled=True, entry__is_active=True).select_related('entry').order_by('pk'):
        names = [site.entry.name, *(site.entry.aliases if isinstance(site.entry.aliases, list) else [])]
        if not any(len(name := normalize_name(value)) >= 4 and name in normalized for value in names):
            continue
        host = urlsplit(site.url).hostname
        if not host or host not in site.allowed_hosts or not safe_source_url(site.url):
            continue
        return site
    return None


def retrieve_official_web(question, *, client_factory=ChatOfficialClient):
    """The caller never passes a URL. An official registry entry controls the target."""
    site = _matching_site(question)
    if site is None:
        return [], 'registered_site_not_matched'
    try:
        url = checked_url(site.url, site.allowed_hosts, resolve=False)
        client = client_factory(site.allowed_hosts)
        try:
            page = client.get(url)
        finally:
            client.close()
        # Final redirect must still belong to the registered hosts.
        checked_url(page.url, site.allowed_hosts, resolve=False)
        # A registry entrance can be an index. Require an identifiable notice body
        # instead of treating every long home page bearing the event name as news.
        parsed = parse_page(site, page, index=True)
        if parsed['page_kind'] != 'notice':
            return [], 'official_page_not_a_notice'
        body = public_text(parsed['body'])
        if not body or not safe_source_url(page.url):
            return [], 'official_page_without_usable_text'
        return [{
            'kind': 'web', 'entity_id': str(site.pk), 'version': hashlib.sha256(body.encode()).hexdigest()[:16],
            'title': public_text(parsed['title']), 'url': page.url, 'internal_url': None,
            'text': body[:1800], 'verified_at': None,
            'published_on': parsed['source_published_on'].isoformat() if parsed['source_published_on'] else None,
            'read_at': timezone.now().isoformat(), 'status': 'unreviewed_official_page',
            'status_note': '官网页面刚刚读取，未经平台人工审核；请以原文和后续更正为准。',
            'source_type': 'official_event', 'reviewed': False,
        }], 'ready'
    except (FetchError, ValueError, TypeError):
        return [], 'official_site_unavailable'


class RegisteredOfficialAdapter:
    """Current search adapter. Future SearXNG/API adapters implement search(query)."""

    def search(self, query):
        return retrieve_official_web(query)


class ExternalSearchAdapter(Protocol):
    """Future providers return candidate rows and a status; trust is assigned here."""

    def search(self, query): ...


def search_external(query, *, domain='competition', adapters=None):
    """Search only configured adapters; dedupe and validate every candidate."""
    adapters = [RegisteredOfficialAdapter()] if adapters is None else adapters
    results, seen, statuses = [], set(), []
    for adapter in adapters:
        try:
            rows, status = adapter.search(query)
        except (FetchError, OSError, ValueError):
            statuses.append('external_search_unavailable')
            continue
        statuses.append(status)
        for row in rows:
            # A result cannot award itself official status. Only our registry adapter
            # has already checked the target host against an enabled OfficialSite.
            source_type = 'official_event' if type(adapter) is RegisteredOfficialAdapter else 'ordinary_web'
            candidate = validated_external(row, domain=domain, source_type=source_type)
            if candidate and candidate['url'] not in seen:
                seen.add(candidate['url'])
                results.append(candidate)
    results.sort(key=lambda row: -row['evidence_score'])
    return results[:3], 'ready' if results else (statuses[0] if statuses else 'no_adapter')
