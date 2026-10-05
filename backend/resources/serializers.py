"""Explicit public fields: no local attachment paths, operator identities or metadata."""

from rest_framework import serializers

from information_library.selectors import public_text, safe_source_url
from information_library.presentation import resource_presentation


def taxonomy(item, expected_kind):
    if not item or item.kind != expected_kind:
        return None
    return {'code': item.code, 'name': public_text(item.name)}


class ResourceSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        content = resource_presentation(instance.description, title=instance.title)
        detail = self.context.get('detail', False)
        catalogs = self.context.get('catalog_map', {}).get(instance.pk, [])
        return {
            'id': instance.code,
            'title': public_text(instance.title),
            'description': content['summary'],
            'content': content['content'] if detail else '',
            'facts': content['facts'],
            'category': taxonomy(instance.category, 'category'),
            'directions': [term for item in instance.directions.all()
                           if (term := taxonomy(item, 'direction'))],
            'tags': [term for item in instance.tags.all()
                     if (term := taxonomy(item, 'tag'))],
            'provider': public_text(instance.provider),
            'source_url': safe_source_url(instance.access_url),
            'updated_at': instance.updated_at.isoformat(),
            'publication_status': instance.publication_status,
            'availability': instance.availability,
            'catalogs': [{'code': item['code'], 'name': public_text(item['name'])}
                         for item in catalogs],
        }
