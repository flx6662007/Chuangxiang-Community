"""Optional SearXNG discovery + bounded public-page reading, without paid credentials."""
import hashlib
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ingestion.http import FetchError, OfficialClient, checked_url
from .research_retrieval import topic_terms


def search_question(question):
    # Conversation commands pollute engine ranking; retain subject and explicit constraints.
    question = re.sub(r'联网搜索|联网查询|网上搜索|网络搜索|联网|搜索一下|帮我查一下|请帮我|帮我|给我|解释一下|解释', ' ', question)
    question = re.sub(r'[，。；、？！?;]+', ' ', question)
    return re.sub(r'\s+', ' ', question).strip()[:500]


def page_evidence(page, query):
    soup = BeautifulSoup(page.text, 'html.parser')
    published = None
    for node in soup.select('meta[property="article:published_time"], meta[name="pubdate"], time[datetime]'):
        value = node.get('content') or node.get('datetime')
        try:
            published = datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
            break
        except (ValueError, TypeError, AttributeError):
            continue
    root = soup.select_one('article, main, .v_news_content, .article-content, .wp_articlecontent') or soup.body or soup
    title = soup.find('h1') or soup.title
    title = title.get_text(' ', strip=True)[:200] if title else ''
    for node in root.select('script,style,iframe,form,nav,header,footer,noscript'):
        node.decompose()
    paragraphs = [node.get_text(' ', strip=True) for node in root.select('p,li,h2,h3')]
    body = '\n'.join(dict.fromkeys(paragraphs)) or root.get_text(' ', strip=True)
    if len(body) < 80 or not title:
        return None, []
    terms = topic_terms(query)
    def score(text):
        lower = text.casefold()
        return sum(term in lower or len(term) > 3 and any(term[i:i+2] in lower for i in range(len(term)-1)) for term in terms)
    paragraphs = paragraphs or [body]
    chosen = sorted(enumerate(paragraphs), key=lambda row: -score(row[1]))[:8]
    if terms and not score(title + ' ' + body):
        return None, []
    text = '\n'.join(text for _, text in sorted(chosen))[:1800]
    links = []
    labels = r'招募|招生|加入|申请|join|openings' if re.search(r'招募|申请|本科|硕士|博士', query) else r'成果|论文|publication|research'
    for anchor in root.select('a[href]'):
        url = urljoin(page.url, anchor['href'])
        if re.search(labels, anchor.get_text(' ', strip=True), re.I) and urlsplit(url).hostname == urlsplit(page.url).hostname:
            links.append(url)
    return {'title': title, 'url': page.url, 'text': text, 'published_on': published,
            'read_at': timezone.now().isoformat(), 'version': hashlib.sha256(body.encode()).hexdigest(),
            'entity_id': hashlib.sha256(page.url.encode()).hexdigest()[:20], 'retrieval_score': 0.6}, links[:1]


class SearXNGAdapter:
    def __init__(self, config=None, *, transport=None, client_factory=OfficialClient):
        self.config = config if config is not None else getattr(settings, 'AI_EXTERNAL_SEARCH', {})
        self.transport, self.client_factory = transport, client_factory

    def search(self, query):
        query = search_question(query)
        endpoint = self.config.get('SEARXNG_URL', '').strip()
        parts = urlsplit(endpoint)
        # This endpoint is operator-owned configuration; never taken from chat or search results.
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            return [], 'external_search_unconfigured'
        cache_key = 'ai-web-v2:' + hashlib.sha256((endpoint + query).encode()).hexdigest()
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, 'ready'
        deadline = time.monotonic() + min(25, max(1, float(self.config.get('TIMEOUT_SECONDS', 15))))
        limit = min(3, max(1, int(self.config.get('MAX_PAGES', 3))))
        try:
            with httpx.Client(timeout=min(5, deadline - time.monotonic()), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                with client.stream('GET', endpoint.rstrip('/') + '/search',
                                   params={'q': query[:500], 'format': 'json', 'categories': 'general'}) as response:
                    if response.status_code != 200:
                        return [], 'external_search_unavailable'
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 512000 or time.monotonic() >= deadline:
                            return [], 'external_search_unavailable'
                        chunks.append(chunk)
                    payload = json.loads(b''.join(chunks))
            candidates = payload.get('results', []) if isinstance(payload, dict) else []
            if not isinstance(candidates, list):
                return [], 'external_search_unavailable'
            preferred = self.config.get('OFFICIAL_HOSTS', {})
            urls = [row.get('url') for row in candidates[:10] if isinstance(row, dict) and isinstance(row.get('url'), str)]
            urls.sort(key=lambda url: urlsplit(url).hostname not in preferred)
            rows, seen, attempts = [], set(), 0
            while urls and attempts < limit and time.monotonic() < deadline:
                url = urls.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                attempts += 1
                reader = None
                try:
                    host = urlsplit(url).hostname
                    checked_url(url, [host], resolve=False)
                    reader = self.client_factory([host], timeout=min(5, max(.01, deadline-time.monotonic())),
                                                 attempts=1, interval=0, deadline=deadline)
                    page = reader.get(url)
                    checked_url(page.url, [host], resolve=False)
                    row, links = page_evidence(page, query)
                    if row and row['url'] not in {item['url'] for item in rows}:
                        rows.append(row)
                        urls = links + urls
                except (FetchError, ValueError, OSError):
                    continue
                finally:
                    if reader is not None:
                        reader.close()
            if rows:
                cache.set(cache_key, rows, timeout=300)
            return rows, 'ready' if rows else 'external_page_unavailable'
        except (httpx.HTTPError, ValueError, TypeError, OSError):
            return [], 'external_search_unavailable'
