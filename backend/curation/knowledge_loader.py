"""Load and activate the three competition knowledge packages as one batch."""
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from .importer import entity_state, import_package, require_actor
from .models import ImportedObject, KnowledgeDocument
from .package import digest, load_package, require
from .services import review_document


DEFAULT_DIRECTORY = Path(__file__).resolve().parents[2] / 'docs/competition-knowledge-maintenance/imports'
PACKAGE_RANGES = ('001-089', '090-130', '131-255')


def load_knowledge_packages(directory=None):
    """Validate the complete, independent corpus before starting database work."""
    from information_library.competition_search import _validate_corpus

    directory = Path(directory) if directory is not None else DEFAULT_DIRECTORY
    packages, records, versions, document_codes = [], [], set(), set()
    for scope in PACKAGE_RANGES:
        data = load_package(directory / f'import-{scope}.json')
        require(data['package_id'] == f'competition-knowledge-standalone-v1-{scope}',
                f'{scope} 资料包编号与独立知识版本一致。')
        require(not data['competitions'] and not data['resources']
                and not any(data['references'].values()), f'{scope} 资料包只能包含独立知识文档。')
        require(bool(data['documents']), f'{scope} 资料包缺少知识文档。')
        version = data.get('corpus_version')
        require(isinstance(version, str) and bool(version), f'{scope} 资料包缺少 corpus_version。')
        versions.add(version)
        for row in data['documents']:
            code = row['code']
            require(code not in document_codes, f'知识文档编号重复：{code}')
            document_codes.add(code)
            require(not row.get('competition_codes') and not row.get('resource_codes')
                    and not row.get('attachments'), f'{code} 需要完整独立正文。')
            metadata = row.get('metadata', {})
            record = metadata.get('search_record')
            require(isinstance(record, dict) and metadata.get('corpus_version') == version,
                    f'{code} 检索记录或资料版本不一致。')
            require(code == 'final-' + str(record.get('id', '')), f'{code} 检索标识不一致。')
            require(record.get('competition_id') is None, f'{code} 应使用独立知识标识。')
            require(record.get('review_status') == 'approved' and record.get('publication_status') == 'published',
                    f'{code} 应为成品知识记录。')
            _validate_corpus({'schema_version': 1, 'version': version, 'records': [record]})
            body = '\n\n'.join(f"## {section['heading']}\n\n{section['text']}"
                               for section in record['sections'])
            require(row['title'] == record['title'] and row.get('edition', '') == record.get('edition', '')
                    and row['body'].replace('\r\n', '\n').strip() == body.replace('\r\n', '\n').strip()
                    and row['sources'] == record['sources'], f'{code} 正文与检索记录不一致。')
            require(set(row['catalog_codes']) <= set(record.get('catalog_codes', [])),
                    f'{code} 目录与检索记录不一致。')
            require(record['content_hash'] == digest({key: value for key, value in record.items()
                                                       if key != 'content_hash'}), f'{code} 内容版本不一致。')
            source_ids = {source['id'] for source in record['sources']}
            for source in record['sources']:
                require(bool(source.get('locator')) and bool(source.get('verified_at')),
                        f'{code} 来源需要原文位置和核验日期。')
                date.fromisoformat(source['verified_at'])
            for field in record['fields']:
                evidence = set(record['field_evidence'].get(field, []))
                require(bool(evidence) and evidence <= source_ids, f'{code}/{field} 缺少字段来源。')
            for section in record['sections']:
                evidence = set(section.get('evidence_ids', []))
                require(bool(section['text'].strip()) and bool(evidence) and evidence <= source_ids,
                        f'{code}/{section["id"]} 缺少正文或来源。')
            records.append(record)
        packages.append(data)
    require(len(versions) == 1, '三个资料包需要使用同一 corpus_version。')
    version = versions.pop()
    _validate_corpus({'schema_version': 1, 'version': version, 'records': records})
    require(digest(records)[:16] == version, '资料包内容与 corpus_version 不一致。')
    return packages, version


def _check_owned_document(document, stamp, package_id):
    """Compare the saved import revision, content and links before an update."""
    code = document.code
    require(stamp is not None and stamp.package_id == package_id, f'{code} 的资料包归属不一致。')
    previous = stamp.revisions.order_by('-version').first()
    require(previous is not None and stamp.payload_hash == digest(previous.payload)
            and stamp.state_hash == digest(previous.state), f'{code} 导入版本记录不一致。')
    state = entity_state('document', document)
    require({k: v for k, v in state.items() if k != 'review_status'}
            == {k: v for k, v in previous.state.items() if k != 'review_status'},
            f'{code} 当前标题或版本已修改。')
    revision, payload = document.current_revision, previous.payload
    require(revision is not None and revision.content_hash == stamp.payload_hash
            and revision.title == payload['title'] and revision.body == payload['body']
            and revision.edition == payload.get('edition', '') and revision.sources == payload['sources']
            and revision.attachments == payload.get('attachments', [])
            and {key: value for key, value in revision.metadata.items() if key not in {'package_id', 'package_root'}}
            == payload.get('metadata', {}) and revision.metadata.get('package_id') == package_id,
            f'{code} 当前正文与导入版本不一致。')
    links = list(revision.links.select_related('catalog'))
    require(all(link.catalog_id and not link.competition_id and not link.resource_id for link in links)
            and {link.catalog.code for link in links} == set(payload['catalog_codes']),
            f'{code} 当前关联与导入版本不一致。')


@transaction.atomic
def load_competition_knowledge(*, actor, reason, apply=False, directory=None):
    """Preview or commit import and approval for the complete knowledge release."""
    require_actor(actor)
    if not actor.has_perms(['curation.change_knowledgedocument', 'curation.add_documentreview']):
        raise PermissionDenied('需要知识文档审核权限。')
    require(isinstance(reason, str) and 1 <= len(reason.strip()) <= 500, '审核依据需要 1 至 500 个字符。')
    packages, version = load_knowledge_packages(directory)
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [2026131255])
    counts = Counter({key: 0 for key in ('documents_created', 'documents_updated', 'documents_unchanged',
                                       'documents_withdrawn', 'documents_retired', 'documents_reviewed', 'catalogs_created')})
    package_ids = [data['package_id'] for data in packages]
    release_codes = {row['code'] for data in packages for row in data['documents']}
    retired_stamps = ImportedObject.objects.select_for_update().filter(
        kind='document', package_id__in=package_ids).exclude(code__in=release_codes)
    for stamp in retired_stamps:
        document = KnowledgeDocument.objects.select_for_update(of=('self',)).select_related(
            'current_revision').filter(code=stamp.code).first()
        require(document is not None, f'{stamp.code} 缺少已导入的知识文档。')
        _check_owned_document(document, stamp, stamp.package_id)
        if document.review_status != 'withdrawn':
            review_document(document.code, revision=document.current_revision.version,
                            status='withdrawn', reason=reason, actor=actor)
            counts['documents_retired'] += 1
    codes, record_ids, to_approve = [], set(), []
    for source in packages:
        data = deepcopy(source)
        data['review'] = {'status': 'approved', 'reviewed_by': str(actor.get_username()),
                          'reviewed_on': timezone.localdate().isoformat()}
        pending = []
        for row in data['documents']:
            codes.append(row['code'])
            record_ids.add(row['metadata']['search_record']['id'])
            document = KnowledgeDocument.objects.select_for_update(of=('self',)).select_related('current_revision').filter(code=row['code']).first()
            if document:
                stamp = ImportedObject.objects.select_for_update().filter(kind='document', code=row['code']).first()
                _check_owned_document(document, stamp, data['package_id'])
                if document.review_status == 'withdrawn':
                    counts['documents_withdrawn'] += 1
                    continue
                if stamp.payload_hash == digest(row):
                    counts['documents_unchanged'] += 1
                    if document.review_status == 'draft':
                        to_approve.append(row['code'])
                    continue
                if document.review_status in ('approved', 'published'):
                    review_document(document.code, revision=document.current_revision.version,
                                    status='draft', reason=reason, actor=actor)
            pending.append(row)
            to_approve.append(row['code'])
        data['documents'] = pending
        if pending:
            imported = import_package(data, actor=actor, apply=True)
            counts['documents_created'] += imported.get('document_created', 0)
            counts['documents_updated'] += imported.get('document_updated', 0)
            counts['catalogs_created'] += imported.get('catalog_created', 0)
    for code in to_approve:
        document = KnowledgeDocument.objects.select_related('current_revision').get(code=code)
        review_document(code, revision=document.current_revision.version, status='approved', reason=reason, actor=actor)
        counts['documents_reviewed'] += 1
    from information_library.competition_search import database_corpus
    corpus = database_corpus()
    owned_codes = ImportedObject.objects.filter(kind='document', package_id__in=package_ids).values_list('code', flat=True)
    active_documents = KnowledgeDocument.objects.filter(code__in=owned_codes, review_status__in=('approved', 'published')).select_related('current_revision')
    active_record_ids = {document.current_revision.metadata['search_record']['id'] for document in active_documents}
    require(active_record_ids <= record_ids, '当前启用的知识文档需要属于本次资料版本。')
    visible = {record['id'] for record in corpus['records']} & active_record_ids
    require(visible == active_record_ids, '已启用的知识文档需要全部进入检索语料。')
    require(len(visible) == len(codes) - counts['documents_withdrawn'], '导入结果与可检索文档数量不一致。')
    result = {'ok': True, 'mode': 'apply' if apply else 'preview-rolled-back',
              'corpus_version': version, 'database_corpus_version': corpus['version'],
              'packages': package_ids, 'documents': len(codes),
              'searchable_documents': len(visible), 'counts': dict(counts)}
    from .activation import activate_release
    result['activation'] = activate_release([r for r in corpus['records'] if r['id'] in visible], actor=actor)
    if not apply:
        transaction.set_rollback(True)
    return result
