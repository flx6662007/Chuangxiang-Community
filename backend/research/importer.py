"""Import reviewed nine-field cards through validated, versioned database writes."""
from datetime import date, datetime, time
import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from common.snapshots import PUBLIC_SNAPSHOT_KEYS
from common.public_content import safe_source_url
from .models import ResearchOpportunity, ResearchRevision, ResearchSource
from .knowledge import source_key


def card_fields(row):
    return {
        'title': row['title'], 'institution': row['unit'],
        'recruiting_entity': row['unit'] or row['title'],
        'research_group': row['title'], 'description': row['summary'],
        'summary': row['summary'], 'eligibility': row['participation'],
        'requirements': row['evidenceNote'], 'official_url': row['sourceUrl'],
        'source_published_on': date.fromisoformat(row['date']) if row['date'] else None,
        'last_verified_at': timezone.make_aware(datetime.combine(date.fromisoformat(row['verifiedOn']), time.min)) if row['verifiedOn'] else None,
    }


def snapshot(obj):
    result = {}
    for field in obj._meta.concrete_fields:
        if field.name in PUBLIC_SNAPSHOT_KEYS:
            value = getattr(obj, field.attname)
            result[field.name] = value.isoformat() if hasattr(value, 'isoformat') else value
    result['tags'] = list(obj.tags.values_list('code', flat=True))
    result['directions'] = list(obj.directions.values_list('code', flat=True))
    result['sources'] = list(ResearchSource.objects.filter(opportunity=obj).order_by('source_url').values('source_url', 'source_name', 'source_type', 'published_on', 'updated_on', 'verified_at'))
    return json.loads(json.dumps(result, cls=DjangoJSONEncoder))


@transaction.atomic
def import_cards(rows, *, apply=False, publish=False, profiles=None, sources=None):
    """Preview runs the same validations and rolls back; withdrawn rows stay withdrawn."""
    counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'published': 0, 'withdrawn_preserved': 0}
    if sources is not None:
        if not isinstance(sources, dict) or set(sources) != {r['id'] for r in rows}:
            raise ValidationError('sources 必须与导入编号一一对应。')
        for entries in sources.values():
            if not isinstance(entries, list):
                raise ValidationError('补充来源须为列表。')
            seen = set()
            for entry in entries:
                if (not isinstance(entry, dict) or set(entry) != {'url', 'title', 'verifiedOn'}
                        or not safe_source_url(entry['url']) or not isinstance(entry['title'], str)
                        or not 1 <= len(entry['title']) <= 200 or source_key(entry['url']) in seen):
                    raise ValidationError('补充来源格式无效或重复。')
                date.fromisoformat(entry['verifiedOn'])
                seen.add(source_key(entry['url']))
    for row in rows:
        obj = ResearchOpportunity.objects.select_for_update().filter(code=row['id']).first()
        source = row['sourceUrl'].rstrip('/')
        if ResearchOpportunity.objects.filter(official_url__in=[source, source + '/']).exclude(code=row['id']).exists():
            raise ValidationError(f"{row['id']} 的来源已由其他编号占用，请先核对实体。")
        if obj and obj.publication_status == 'withdrawn':
            counts['withdrawn_preserved'] += 1
            continue
        fields = card_fields(row)
        if profiles is not None:
            fields['card_details'] = profiles[row['id']]
        new = obj is None
        if new:
            obj = ResearchOpportunity(code=row['id'])
        changed = new or any(getattr(obj, key) != value for key, value in fields.items())
        source_updates = []
        existing_sources = {source_key(s.source_url): s for s in ResearchSource.objects.filter(opportunity=obj)} if not new and sources is not None else {}
        for entry in sources.get(row['id'], []) if sources is not None else []:
            url = source_key(entry['url'])
            if url == source_key(row['sourceUrl']):
                continue
            child = existing_sources.get(url) or ResearchSource(opportunity=obj, source_url=url)
            values = {'source_name': entry['title'], 'source_type': 'official',
                      'verified_at': timezone.make_aware(datetime.combine(date.fromisoformat(entry['verifiedOn']), time.min))}
            if not child.pk or any(getattr(child, key) != value for key, value in values.items()):
                source_updates.append((child, values))
        changed = changed or bool(source_updates)
        publication_changed = publish and obj.publication_status == 'draft'
        if not changed and not publication_changed:
            counts['unchanged'] += 1
            continue
        for key, value in fields.items():
            setattr(obj, key, value)
        if publication_changed:
            obj.publication_status = 'published'
            obj.published_at = obj.published_at or timezone.now()
            counts['published'] += 1
        if changed and not new:
            obj.content_version += 1
        obj.last_edited_at = timezone.now()
        obj.full_clean()
        obj.save()
        for child, values in source_updates:
            child.opportunity = obj
            for key, value in values.items():
                setattr(child, key, value)
            child.full_clean()
            child.save()
        if changed:
            revision = ResearchRevision(opportunity=obj, version=obj.content_version, snapshot=snapshot(obj))
            revision.full_clean()
            revision.save()
        counts['created' if new else 'updated'] += 1
    counts['retained'] = ResearchOpportunity.objects.exclude(code__in=[r['id'] for r in rows]).count()
    if not apply:
        transaction.set_rollback(True)
    return {**counts, 'applied': apply}
