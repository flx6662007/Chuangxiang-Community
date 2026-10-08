from rest_framework import serializers
from common.public_content import public_text, safe_source_url
from information_library.presentation import reading_text


class CatalogSerializer(serializers.BaseSerializer):
    def to_representation(self, entry):
        return {
            'code': entry.code, 'name': public_text(entry.name), 'version': entry.version,
            'grade': entry.grade, 'levels': public_text(entry.levels),
            'departments': [],
            'source_url': '',
            **self.context['counts'][entry.pk],
        }


def edition_summary(competition):
    published = competition.publication_status == 'published'
    return {
        'id': competition.pk, 'code': competition.code, 'title': public_text(competition.title),
        'edition': public_text(competition.edition), 'summary': reading_text(competition.summary),
        'publication_status': competition.publication_status,
        'url': f'/information/competitions/{competition.pk}' if published else '',
    }
