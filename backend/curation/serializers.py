"""前端知识正文白名单；不输出导入路径、附件本地路径和操作者。"""
from rest_framework import serializers
from common.public_content import public_text, safe_source_url
from information_library.presentation import document_summary, reading_text


def document_sources(revision):
    result = []
    seen = set()
    for source in revision.sources if isinstance(revision.sources, list) else []:
        if not isinstance(source, dict):
            continue
        url = safe_source_url(source.get('url'))
        if url and url not in seen:
            seen.add(url)
            result.append({'url': url, 'title': reading_text(source.get('title')
                           or source.get('locator') or source.get('name') or '原始来源')})
    return result


class KnowledgeDocumentSerializer(serializers.BaseSerializer):
    def to_representation(self, document):
        revision = document.current_revision
        metadata = revision.metadata if isinstance(revision.metadata, dict) else {}
        gaps = metadata.get('gaps', [])
        body = reading_text(revision.body, gaps=gaps if isinstance(gaps, list) else [])
        result = {
            'code': document.code, 'title': public_text(revision.title),
            'edition': public_text(revision.edition), 'review_status': document.review_status,
            'summary': document_summary(body, metadata), 'sources': document_sources(revision),
            'updated_at': document.updated_at.isoformat(), 'version': revision.version,
        }
        if self.context.get('detail'):
            result.update(body=body, body_truncated=len(public_text(revision.body)) >= 16000, notes={
                'edition_note': reading_text(metadata.get('edition_note')),
                'source_status': public_text(metadata.get('source_status')),
                'gaps': [public_text(x) for x in gaps] if isinstance(gaps, list) else [],
                'contains_source_fulltext': metadata.get('contains_source_fulltext') is True,
            })
        return result
