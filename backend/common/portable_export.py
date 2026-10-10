"""Read-only, allowlisted public fixtures for an isolated review installation.

No user or operational history is exported. The launcher must create a synthetic
user with ``demo_actor_id`` before loaddata (DocumentRevision requires an actor).
The source connection is protected by a database-enforced read-only transaction.
"""
from collections import Counter
from contextlib import contextmanager
import hashlib
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from django.conf import settings
from django.core import serializers
from django.core.management.base import CommandError
from django.db import connections, models, transaction
from django.db.models import Q

from common.public_content import public_text, safe_source_url
from competition_catalog.models import CatalogBinding, CatalogEntry, OfficialSite
from competitions.models import CompetitionSource, CompetitionTaxonomy
from competitions.scope import apply_competition_scope
from competitions.selectors import public_competition_queryset
from curation.retrieval import student_visible_documents
from information_library.competition_search import FIELD_NAMES
from research.models import ResearchDirection, ResearchOpportunity, ResearchSource, ResearchTag, ResearchTaxonomy
from research.presentation import public_card_details
from resources.models import ResourceCompetition, ResourceDirection, ResourceResearchOpportunity, ResourceTag, ResourceTaxonomy
from resources.selectors import visible_resources
from teams.models import RecruitmentOption


# Explicit field lists prevent future private model fields entering a release.
PUBLIC_FIELDS = {
    'competitions.competitiontaxonomy': 'code kind name is_active sort_order',
    'competitions.competition': (
        'code title edition summary description category tags level organizer tracks eligibility participation_type '
        'team_size_min team_size_max registration_method registration_url campus_arrangements registration_deadline '
        'registration_deadline_at registration_deadline_timezone submission_deadline submission_deadline_at '
        'submission_deadline_timezone campus_deadline campus_deadline_at campus_deadline_timezone deadline_notes '
        'publication_status publication_method published_at last_verified_at created_at updated_at '
        'recruitment_enabled recruitment_deadline'),
    'competitions.competitionsource': (
        'competition source_type source_name source_url is_primary source_published_on source_updated_on last_verified_at'),
    'competition_catalog.catalogentry': 'code version name grade levels departments aliases is_active source_url',
    'competition_catalog.catalogbinding': 'entry competition',
    'competition_catalog.officialsite': 'entry url evidence_url kind dedicated allowed_hosts enabled',
    'resources.resourcetaxonomy': 'code kind name is_active sort_order',
    'resources.resource': (
        'code title description category provider access_url source_note availability last_verified_at '
        'publication_status published_at last_edited_at content_version created_at updated_at'),
    'resources.resourcetag': 'resource taxonomy',
    'resources.resourcedirection': 'resource taxonomy',
    'resources.resourcecompetition': 'resource competition',
    'resources.resourceresearchopportunity': 'resource opportunity',
    'research.researchtaxonomy': 'code kind name is_active sort_order',
    'research.researchopportunity': (
        'code title description summary recruiting_entity official_url official_source_name source_published_on '
        'card_details supervisor research_group institution category work_content eligibility requirements '
        'vacancies_text vacancies_min vacancies_max weekly_hours_text weekly_hours_min weekly_hours_max '
        'duration_text starts_on ends_on collaboration_mode location_text application_instructions application_url '
        'deadline_mode deadline_on deadline_at deadline_timezone deadline_notes closed_at closure_note '
        'last_verified_at publication_status published_at last_edited_at content_version created_at updated_at'),
    'research.researchsource': 'opportunity source_url source_name source_type published_on updated_on verified_at created_at',
    'research.researchtag': 'opportunity taxonomy',
    'research.researchdirection': 'opportunity taxonomy',
    'curation.knowledgedocument': 'code title review_status current_revision updated_at',
    'curation.documentrevision': 'document version title body edition sources content_hash metadata created_at',
    'curation.documentlink': 'revision catalog competition resource',
    'teams.recruitmentoption': 'code kind name is_active sort_order',
}
SOURCE_FIELDS = {'id', 'url', 'quote', 'title', 'locator', 'verified_at', 'published_on', 'name'}
RECORD_FIELDS = {
    'id', 'code', 'kind', 'level', 'title', 'aliases', 'edition', 'summary', 'category', 'catalog_code',
    'catalog_codes', 'review_status', 'publication_status', 'content_hash', 'competition_id',
}
METADATA_FIELDS = {'why_useful', 'gaps', 'edition_note', 'source_status', 'contains_source_fulltext', 'content_standard'}


@contextmanager
def readonly_snapshot(database='default'):
    connection = connections[database]
    if connection.in_atomic_block:
        raise CommandError('Export must start outside an existing transaction.')
    if connection.vendor not in ('postgresql', 'sqlite'):
        raise CommandError('Only PostgreSQL and SQLite read-only snapshots are supported.')
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA query_only')
            was_readonly = cursor.fetchone()[0]
            cursor.execute('PRAGMA query_only = ON')
    try:
        with transaction.atomic(using=database):
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            yield
    finally:
        if connection.vendor == 'sqlite':
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA query_only = ' + ('ON' if was_readonly else 'OFF'))


def clean_text(value):
    """Apply the existing public contact filter without truncating full documents."""
    value = '\n'.join(public_text(line) for line in value.splitlines())
    value = re.sub(r'(?i)\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,})', '[凭据已省略]', value)
    value = re.sub(r'(?i)(?:api[_ -]?key|password|secret|access[_ -]?token)\s*[:=]\s*\S+', '[凭据已省略]', value)
    value = re.sub(r'(?i)\b[A-Z]:[\\/][^\s<>"|]+|file://[^\s<>]+|\\\\[^\s<>]+', '[本地路径已省略]', value)
    value = re.sub(r'(?<!\w)/(?:home|Users|root|tmp|var|mnt)/[^\s<>]+', '[本地路径已省略]', value)
    value = re.sub(r'https?://[^\s<>\]\)"，。；]+',
                   lambda match: public_url(match.group()) or '[非公开链接已省略]', value)
    return value


def public_url(value):
    url = safe_source_url(value)
    if not url:
        return ''
    parsed = urlsplit(url)
    if any(re.search(r'(?i)password|secret|token|api.?key|authorization|signature|credential', key)
           for key, _ in parse_qsl(parsed.query)):
        return ''
    if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', unquote(url)):
        return ''
    return url


def clean_value(value, *, key=''):
    if isinstance(value, str):
        if key in {'url', 'source_url', 'access_url', 'official_url', 'application_url', 'registration_url', 'evidence_url'}:
            return public_url(value)
        return clean_text(value)
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {clean_text(str(name)): clean_value(item, key=name) for name, item in value.items()}
    return value


def public_sources(sources):
    return [clean_value({key: value for key, value in source.items() if key in SOURCE_FIELDS})
            for source in sources if isinstance(source, dict) and public_url(source.get('url'))]


def public_search_record(raw, revision):
    record = clean_value({key: value for key, value in raw.items() if key in RECORD_FIELDS})
    record['fields'] = clean_value({key: value for key, value in raw.get('fields', {}).items() if key in FIELD_NAMES})
    if isinstance(record.get('category'), dict):
        record['category'] = {key: value for key, value in record['category'].items() if key in {'id', 'code', 'name'}}
    record['sources'] = public_sources(revision.sources)
    source_ids = {source.get('id') for source in record['sources']}
    record['sections'] = [
        {**clean_value({key: section[key] for key in ('id', 'heading', 'text') if key in section}),
         'evidence_ids': [key for key in section.get('evidence_ids', []) if key in source_ids]}
        for section in raw.get('sections', []) if isinstance(section, dict)
    ]
    record['field_evidence'] = {key: [item for item in values if item in source_ids]
                                for key, values in raw.get('field_evidence', {}).items() if key in FIELD_NAMES}
    record['alias_evidence'] = {clean_text(key): [item for item in values if item in source_ids]
                                for key, values in raw.get('alias_evidence', {}).items()}
    record['category_evidence'] = [key for key in raw.get('category_evidence', []) if key in source_ids]
    record['learning_resources'] = [
        clean_value({key: value for key, value in item.items() if key in {'id', 'url', 'title', 'summary'}})
        for item in raw.get('learning_resources', []) if isinstance(item, dict) and public_url(item.get('url'))
    ]
    return record


def fixture_row(obj, *, demo_actor_id):
    label = obj._meta.label_lower
    fields = PUBLIC_FIELDS[label].split()
    row = serializers.serialize('python', [obj], fields=fields)[0]
    row['fields'] = clean_value(row['fields'])
    values = row['fields']
    # Nullable user relations are explicit nulls so re-loading cannot preserve an actor.
    for field in obj._meta.concrete_fields:
        if field.is_relation and field.related_model._meta.label_lower == settings.AUTH_USER_MODEL.lower():
            values[field.name] = None if field.null else demo_actor_id
        elif isinstance(field, (models.CharField, models.TextField)) and field.name in values and field.max_length:
            values[field.name] = values[field.name][:field.max_length]
    if label == 'competitions.competition':
        values['withdrawal_reason'] = ''
        values['recruitment_note'] = '演示包保留已公开赛事的招募设置。' if obj.recruitment_enabled else ''
    elif label == 'competition_catalog.catalogbinding':
        values['basis'] = '演示包保留已公开赛事的目录关联。'
    elif label == 'research.researchopportunity':
        values.update(application_email='', verification_note='', withdrawal_reason='', card_details=clean_value(public_card_details(obj.card_details)))
    elif label == 'resources.resource':
        values['withdrawal_reason'] = ''
    elif label == 'curation.documentrevision':
        metadata = {key: clean_value(value) for key, value in obj.metadata.items() if key in METADATA_FIELDS}
        values['sources'] = public_sources(obj.sources)
        values['attachments'] = []  # Local file paths and source snapshots never leave the machine.
        raw = obj.metadata.get('search_record')
        if isinstance(raw, dict):
            record = public_search_record(raw, obj)
            # Keep the exact body/source equality required by database_corpus().
            values['body'] = '\n\n'.join(f"## {part['heading']}\n\n{part['text']}" for part in record['sections'])
            record.update(title=values['title'], edition=values['edition'], sources=values['sources'])
            record['content_hash'] = hashlib.sha256(values['body'].encode('utf-8')).hexdigest()
            metadata['search_record'] = record
        values['content_hash'] = hashlib.sha256(values['body'].encode('utf-8')).hexdigest()
        values['metadata'] = metadata
    return row


def build_public_fixture(*, database='default', demo_actor_id=1):
    """Select current public objects only; caller owns the read-only transaction."""
    if demo_actor_id < 1:
        raise CommandError('demo_actor_id must be a positive synthetic account ID.')
    groups = []
    competitions = list(apply_competition_scope(public_competition_queryset()).using(database).order_by('pk'))
    competition_ids = {obj.pk for obj in competitions}
    resources = [obj for obj in visible_resources().using(database).order_by('pk') if public_url(obj.access_url)]
    resource_ids = {obj.pk for obj in resources}
    catalogs = list(CatalogEntry.objects.using(database).filter(is_active=True).order_by('pk'))
    catalog_ids = {obj.pk for obj in catalogs}
    research = []
    if settings.PUBLIC_RESEARCH_ENABLED:
        research = [obj for obj in ResearchOpportunity.objects.using(database).filter(publication_status='published')
                    .exclude(Q(code__startswith='demo-') | Q(title__contains='【虚构样例】')).order_by('pk')
                    if public_url(obj.official_url)]
    research_ids = {obj.pk for obj in research}

    def rows(model, **filters):
        return list(model.objects.using(database).filter(**filters).order_by('pk'))

    sources = [obj for obj in CompetitionSource.objects.using(database).filter(competition_id__in=competition_ids)
               .filter(Q(last_verified_at__isnull=False) | Q(competition__publication_method='direct')).order_by('pk')
               if public_url(obj.source_url)]
    competition_terms = {obj.category_id for obj in competitions}
    competition_terms.update(tag.pk for obj in competitions for tag in obj.tags.all())
    resource_tags = rows(ResourceTag, resource_id__in=resource_ids)
    resource_directions = rows(ResourceDirection, resource_id__in=resource_ids)
    resource_terms = {obj.category_id for obj in resources} | {obj.taxonomy_id for obj in resource_tags + resource_directions}
    research_tags = rows(ResearchTag, opportunity_id__in=research_ids)
    research_directions = rows(ResearchDirection, opportunity_id__in=research_ids)
    research_terms = {obj.category_id for obj in research} | {obj.taxonomy_id for obj in research_tags + research_directions}
    groups.extend([
        rows(CompetitionTaxonomy, pk__in=competition_terms), catalogs, competitions, sources,
        rows(CatalogBinding, entry_id__in=catalog_ids, competition_id__in=competition_ids),
        [obj for obj in rows(OfficialSite, enabled=True, entry_id__in=catalog_ids)
         if public_url(obj.url) and public_url(obj.evidence_url)],
        rows(ResourceTaxonomy, pk__in=resource_terms), resources, resource_tags, resource_directions,
        rows(ResourceCompetition, resource_id__in=resource_ids, competition_id__in=competition_ids),
        rows(ResearchTaxonomy, pk__in=research_terms), research, research_tags, research_directions,
        [obj for obj in rows(ResearchSource, opportunity_id__in=research_ids) if public_url(obj.source_url)],
        rows(ResourceResearchOpportunity, resource_id__in=resource_ids, opportunity_id__in=research_ids),
    ])
    documents, revisions, links = [], [], []
    for document in student_visible_documents().using(database).select_related('current_revision').prefetch_related('current_revision__links').order_by('pk'):
        revision = document.current_revision
        linked = list(revision.links.all())
        if any((link.competition_id and link.competition_id not in competition_ids)
               or (link.resource_id and link.resource_id not in resource_ids)
               or (link.catalog_id and link.catalog_id not in catalog_ids) for link in linked):
            continue
        if revision.document_id != document.pk:
            raise CommandError('A current knowledge revision belongs to a different document.')
        documents.append(document)
        revisions.append(revision)
        links.extend(linked)
    groups.extend([documents, revisions, links])
    # These controlled terms are public inputs, not team/member activity. Match
    # RecruitmentOptionsView: only active terms, excluding its retired demo set.
    demo_options = (Q(code__startswith='demo-r1-') | Q(code__startswith='demo-r2-')) & Q(name__contains='【虚构样例】')
    groups.append(list(RecruitmentOption.objects.using(database).filter(is_active=True)
                       .exclude(demo_options).order_by('pk')))
    fixture = [fixture_row(obj, demo_actor_id=demo_actor_id) for group in groups for obj in group]
    validate_fixture_relations(fixture, demo_actor_id=demo_actor_id)
    return fixture


def validate_fixture_relations(fixture, *, demo_actor_id):
    """Fail before writing if an exported FK/M2M points outside the public fixture."""
    from django.apps import apps
    identities = {(row['model'], row['pk']) for row in fixture}
    identities.add((settings.AUTH_USER_MODEL.lower(), demo_actor_id))
    for row in fixture:
        if row['model'] not in PUBLIC_FIELDS:
            raise CommandError('Non-public model in portable fixture.')
        model = apps.get_model(row['model'])
        for name, value in row['fields'].items():
            field = model._meta.get_field(name)
            if not field.is_relation or value is None:
                continue
            values = value if field.many_to_many else [value]
            if any((field.related_model._meta.label_lower, pk) not in identities for pk in values):
                raise CommandError(f'Unresolved fixture relation: {row["model"]}.{name}')


def fixture_report(fixture, payload, *, demo_actor_id, database):
    return {
        'format_version': 1, 'source_database_vendor': connections[database].vendor,
        'public_research_enabled': settings.PUBLIC_RESEARCH_ENABLED,
        'competition_catalog_only': settings.COMPETITION_CATALOG_ONLY,
        'demo_actor_id': demo_actor_id, 'counts': dict(sorted(Counter(row['model'] for row in fixture).items())),
        'total_objects': len(fixture), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
        'contains_users': False, 'contains_private_activity': False,
        'requires': ['migrate isolated SQLite', f'create synthetic account pk={demo_actor_id}',
                     'loaddata public-fixture.json', 'rebuild AI indexes from sanitized fixture'],
    }
