"""Public issue snapshots. This reader deliberately does not grant AI retrieval access."""
from collections import OrderedDict
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.db.models import F, Prefetch
from django.utils import timezone

from common.public_content import public_text, safe_source_url
from competitions.models import CompetitionSource
from .models import Newsletter, NewsletterItem


def public_link(value):
    """Keep SPA routes, after validating both the URL and fragment query."""
    if not safe_source_url(value):
        return ''
    fragment = urlsplit(value).fragment
    if any(key.lower() in ('password', 'token', 'secret', 'authorization', 'email', 'access_token')
           for key, _ in parse_qsl(fragment.partition('?')[2] or fragment)):
        return ''
    return value


def public_issues(code=None):
    items = NewsletterItem.objects.select_related('competition', 'research', 'resource').prefetch_related(
        Prefetch('competition__sources', queryset=CompetitionSource.objects.all()),
    ).order_by('position')
    queryset = Newsletter.objects.filter(
        publication_status='published', current_revision__status='confirmed',
        current_revision__newsletter_id=F('pk'),
    ).exclude(code__startswith='demo-').exclude(
        current_revision__title__contains='【虚构样例】',
    ).select_related('current_revision').order_by('-published_at', '-pk')
    if code is not None:
        queryset = queryset.filter(code=code)
    issues = list(queryset)
    revisions = {issue.current_revision_id: issue.current_revision for issue in issues}
    for revision in revisions.values():
        revision.public_items = []
    for item in items.filter(revision_id__in=revisions):
        revisions[item.revision_id].public_items.append(item)
    return issues


def issue_detail(issue):
    revision = issue.current_revision
    sections = OrderedDict()
    hidden = 0
    labels = {'competition': '赛事速递', 'resource': '资源速递', 'research': '科研速递', 'activity': '活动速递'}
    for item in revision.public_items:
        source = public_link(item.source_url)
        changed = False
        if item.kind != 'activity':
            target = getattr(item, item.kind)
            allowed = (target and target.publication_status == 'published'
                       and not target.code.startswith('demo-') and '【虚构样例】' not in target.title)
            if item.kind == 'resource':
                allowed = allowed and target.availability == 'available'
                urls = [target.access_url]
                changed = item.source_version != target.content_version
            elif item.kind == 'research':
                allowed = allowed and settings.PUBLIC_RESEARCH_ENABLED
                urls = [target.official_url]
                changed = item.source_version != target.content_version
            else:
                urls = [entry.source_url for entry in target.sources.all()]
                changed = item.source_updated_at != target.updated_at
            # A changed URL must not leave a stale clickable destination in a historical snapshot.
            if source not in [public_link(url) for url in urls]:
                source = ''
                changed = True
            if not allowed:
                hidden += 1
                continue
        if '【虚构样例】' in item.title_snapshot:
            hidden += 1
            continue
        section = sections.setdefault(item.kind, {'kind': item.kind, 'title': labels[item.kind], 'groups': OrderedDict()})
        group_key = ('group', item.group_title) if item.group_title else ('item', item.position)
        group = section['groups'].setdefault(group_key, {
            'title': public_text(item.group_title or item.title_snapshot), 'items': [],
        })
        group['items'].append({
            'id': item.pk, 'title': public_text(item.title_snapshot),
            'body': public_text(item.summary_snapshot), 'sourceUrl': source,
            'sourceChanged': changed,
        })
    for section in sections.values():
        section['groups'] = list(section['groups'].values())
    return {
        'id': f'db-{issue.pk}', 'code': issue.code, 'title': public_text(revision.title),
        'introduction': public_text(revision.introduction) if not hidden else '',
        'sourcePublishedOn': revision.source_published_on.isoformat() if revision.source_published_on else '',
        'publishedAt': issue.published_at.isoformat() if issue.published_at else '',
        'credits': public_text(revision.credits), 'sections': list(sections.values()),
        'hasHiddenItems': bool(hidden),
    }


def issue_card(issue, detail):
    summary = detail['introduction'] or '阅读本期仍公开的赛事、资源与活动信息。'
    return {
        'id': detail['id'], 'code': issue.code, 'title': detail['title'],
        'date': detail['sourcePublishedOn'], 'sourcePublishedOn': detail['sourcePublishedOn'],
        'publishedAt': detail['publishedAt'],
        'publishedOn': timezone.localtime(issue.published_at).date().isoformat() if issue.published_at else '',
        'summary': summary[:180],
        'detailUrl': f'/newsletters/{issue.code}', 'sourceUrl': '',
        '_searchText': '\n'.join(entry['title'] + '\n' + entry['body']
                                for section in detail['sections'] for group in section['groups']
                                for entry in group['items']),
        'unit': '', 'verifiedOn': '', 'participation': '', 'evidenceNote': '', 'direction': '',
    }
