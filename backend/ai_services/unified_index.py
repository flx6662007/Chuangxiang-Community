"""Optional, versioned local BGE index for resources and research records.

Competition passages keep using the existing competition index.  The index is
rebuilt offline and never grants publication permission by itself.
"""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from information_library.semantic import LocalBGEEncoder, SemanticError, _matrix, _numpy


def fingerprint(records):
    payload = [(row['object_type'], row['object_id'], row['version'], row['status'],
                row['title'], row['summary'], row['content'], row['tags'], row['category'],
                row['direction'], row['source_url'], row.get('evidence_blocks'),
                row.get('field_links'), row.get('recruitment_active')) for row in records]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build_index(records, *, encoder=None):
    encoder = encoder or LocalBGEEncoder()
    chunks, texts, provenance = [], [], []
    for row in records:
        if row['status'] != 'published' or not row['source_url']:
            continue
        body = ('\n'.join([row['title'], row['summary'], row['content'], row['category'],
                           *row['tags'], *row['direction']])).strip()
        blocks = row.get('evidence_blocks') or [{'text': body, 'section': 'content', 'url': row['source_url'], 'fields': []}]
        for block in blocks:
            body = row['title'] + '\n' + block['text']
            for offset in range(0, len(body), 350):
                chunks.append((row['object_type'], row['object_id']))
                texts.append(body[offset:offset + 400])
                provenance.append({'section': block['section'], 'fields': block['fields'],
                                   'url': block['url'], 'version': row['version']})
                if offset + 400 >= len(body):
                    break
    if not texts:
        raise SemanticError('unified_index_empty')
    vectors = _matrix(encoder.encode(texts, is_query=False), expected_rows=len(texts))
    return {'metadata': {'schema_version': 2, 'fingerprint': fingerprint(records),
                         'model_id': encoder.model_id, 'model_revision': encoder.revision,
                         'chunks': chunks, 'provenance': provenance}, 'vectors': vectors}


def save_index(index, path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as stream:
        _numpy().savez_compressed(stream, vectors=index['vectors'],
                                 metadata=json.dumps(index['metadata'], ensure_ascii=False))


@lru_cache(maxsize=2)
def load_index(path, modified_ns, size):
    try:
        with _numpy().load(path, allow_pickle=False) as data:
            return {'metadata': json.loads(str(data['metadata'].item())), 'vectors': data['vectors'].copy()}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SemanticError('unified_index_unreadable') from error


@lru_cache(maxsize=2)
def query_encoder(model_id, revision, model_path):
    return LocalBGEEncoder(model_id=model_id, revision=revision, model_path=model_path or None)


def search(records, query, *, index=None, encoder=None, threshold=0.60):
    if index is None:
        path = os.getenv('UNIFIED_SEMANTIC_INDEX', '')
        if not path:
            raise SemanticError('unified_index_unconfigured')
        stat = os.stat(path)
        index = load_index(os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    metadata = index['metadata']
    if (metadata.get('schema_version') != 2 or metadata.get('fingerprint') != fingerprint(records)
            or not metadata.get('model_id') or not metadata.get('model_revision')
            or not isinstance(metadata.get('chunks'), list)):
        raise SemanticError('unified_index_stale')
    encoder = encoder or query_encoder(metadata['model_id'], metadata['model_revision'],
                                       os.getenv('COMPETITION_EMBEDDING_MODEL_PATH', ''))
    if encoder.model_id != metadata['model_id'] or encoder.revision != metadata['model_revision']:
        raise SemanticError('unified_model_mismatch')
    matrix = _matrix(index['vectors'], expected_rows=len(metadata['chunks']))
    vector = _matrix(encoder.encode([query], is_query=True), expected_rows=1)
    if matrix.shape[1] != vector.shape[1]:
        raise SemanticError('unified_dimension_mismatch')
    scores = matrix @ vector[0]
    best = {}
    for key, score in zip(metadata['chunks'], scores):
        key = tuple(key)
        if float(score) >= threshold:
            best[key] = max(best.get(key, -1.0), float(score))
    return best
