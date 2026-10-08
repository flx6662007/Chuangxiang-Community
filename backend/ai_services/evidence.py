"""Server-owned evidence trust and external-search trigger policy."""

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

from information_library.selectors import safe_source_url
from information_library.selectors import public_text


@dataclass(frozen=True)
class SourceTrust:
    source_type: str
    score: float
    reviewed: bool
    label: str


@dataclass(frozen=True)
class EvidenceScore:
    relevance: float
    trust: float
    freshness: float
    total: float


TRUST_BY_DOMAIN = {
    'competition': {
        'official_event': 1.00, 'organizer_official': 0.94, 'campus_official': 0.86,
        'authoritative_media': 0.62, 'ordinary_web': 0.25,
    },
    'research': {
        'campus_official': 1.00, 'research_institute': 1.00, 'official_project': 0.91,
        'official_repository': 0.76, 'technical_community': 0.48, 'ordinary_web': 0.25,
    },
}


def source_trust(source_type, *, domain='competition', reviewed=False):
    if source_type in ('approved_knowledge', 'platform_competition', 'platform_resource', 'platform_research', 'platform_team'):
        return SourceTrust(source_type, 1.0 if reviewed else 0.72, reviewed,
                           '站内已核验资料' if reviewed else '站内公开资料')
    score = TRUST_BY_DOMAIN.get(domain, TRUST_BY_DOMAIN['competition']).get(source_type, 0.20)
    return SourceTrust(source_type, score, False,
                       '官方来源' if score >= 0.80 else 'Web 补充')


def evidence_score(row, *, domain='competition'):
    """Comparable server-side evidence score; read_at never proves source freshness."""
    trust = source_trust(row.get('source_type'), domain=domain, reviewed=bool(row.get('reviewed')))
    relevance = row.get('retrieval_score')
    if type(relevance) not in (int, float):
        relevance = 0.65 if trust.score >= 0.8 else 0.4
    date_value = row.get('verified_at') or row.get('published_on') or row.get('published_at')
    freshness = 0.0
    if isinstance(date_value, str):
        try:
            value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt_timezone.utc)
            freshness = max(0.0, 1 - max(0, (timezone.now() - value).days) / 365)
        except ValueError:
            pass
    total = min(1.0, 0.55 * max(0.0, min(1.0, relevance)) + 0.35 * trust.score + 0.10 * freshness)
    return EvidenceScore(round(relevance, 4), trust.score, round(freshness, 4), round(total, 4))


def external_decision(question, route, internal_records, *, answer_kind='fact'):
    """Explicit freshness requests take precedence; otherwise use count/confidence."""
    config = getattr(settings, 'AI_EXTERNAL_SEARCH', {})
    minimum = int(config.get('MIN_RESULTS', 2)) if isinstance(config, dict) else 2
    threshold = float(config.get('MIN_CONFIDENCE', 0.55)) if isinstance(config, dict) else 0.55
    if route.web_requested:
        return True, 'explicit_external_request'
    if answer_kind == 'advice' and not route.current:
        return False, 'general_advice'
    if route.current and route.intent != 'general':
        return True, 'time_sensitive'
    if route.intent == 'general':
        return False, 'general_question'
    if any(row.get('object_type') == 'research_opportunity' and row.get('title') in question
           and row.get('evidence_blocks') and row.get('retrieval_score', 0) >= threshold
           for row in internal_records):
        return False, 'internal_evidence_sufficient'
    if len(internal_records) < minimum:
        return True, 'insufficient_internal_results'
    if max((row.get('retrieval_score', 0) for row in internal_records), default=0) < threshold:
        return True, 'low_internal_confidence'
    topical = [row for row in internal_records if row.get('retrieval_score', 0) >= threshold]
    if len(topical) < minimum:
        return True, 'insufficient_internal_results'
    return False, 'internal_evidence_sufficient'


def validated_external(row, *, domain='competition', source_type='ordinary_web'):
    """A search adapter may suggest a page, but never grant it reviewed status."""
    if not isinstance(row, dict) or not safe_source_url(row.get('url')) or not row.get('title') or not row.get('text'):
        return None
    trust = source_trust(source_type, domain=domain)
    published_on = row.get('published_on')
    if not isinstance(published_on, str):
        published_on = None
    elif published_on:
        try:
            datetime.fromisoformat(published_on.replace('Z', '+00:00'))
        except ValueError:
            published_on = None
    result = {**row, 'url': safe_source_url(row['url']), 'source_type': source_type,
              'trust_score': trust.score, 'reviewed': False, 'trust_label': trust.label,
              'kind': 'web', 'internal_url': None, 'verified_at': None,
              'title': public_text(row['title'])[:200], 'text': public_text(row['text'])[:1800],
              'published_on': published_on, 'read_at': row.get('read_at') or timezone.now().isoformat(),
              'status_note': '外部网页刚刚读取，未经平台人工审核；以原文和后续更正为准。',
              'status': 'unreviewed_official_page' if trust.score >= 0.8 else 'unreviewed_web_page'}
    result['evidence_score'] = evidence_score(result, domain=domain).total
    return result
