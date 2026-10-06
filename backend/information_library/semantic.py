"""Versioned local semantic indices; model downloads are a separate setup step."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile


MODEL_ID = 'BAAI/bge-small-zh-v1.5'
MODEL_REVISION = '7999e1d3359715c523056ef9478215996d62a620'
QUERY_INSTRUCTION = '为这个句子生成表示以用于检索相关文章：'
DEFAULT_THRESHOLD = 0.60


class SemanticError(ValueError):
    """An unavailable, incompatible or damaged semantic index."""


class LocalBGEEncoder:
    def __init__(self, *, model_id=MODEL_ID, revision=None, cache_folder=None, model_path=None):
        self.model_id = model_id
        self.revision = revision or os.getenv('COMPETITION_EMBEDDING_REVISION', MODEL_REVISION)
        if not re.fullmatch(r'[0-9a-f]{40}', self.revision):
            raise SemanticError('embedding_revision_unconfigured')
        if self.model_id != MODEL_ID or self.revision != MODEL_REVISION:
            raise SemanticError('embedding_model_not_pinned')
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(
                model_path or os.getenv('COMPETITION_EMBEDDING_MODEL_PATH') or model_id,
                revision=self.revision, device='cpu',
                cache_folder=cache_folder, local_files_only=True,
                trust_remote_code=False,
            )
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            raise SemanticError('embedding_model_unavailable') from error

    def encode(self, texts, *, is_query=False):
        if is_query:
            texts = [QUERY_INSTRUCTION + text for text in texts]
        try:
            tokenized = self.model.tokenizer(texts, truncation=False, padding=False, add_special_tokens=True)
            if any(len(tokens) > self.model.max_seq_length for tokens in tokenized['input_ids']):
                raise SemanticError('semantic_query_too_long' if is_query else 'semantic_passage_too_long')
            return self.model.encode(
                texts, normalize_embeddings=True, convert_to_numpy=True,
                show_progress_bar=False, batch_size=32,
            )
        except SemanticError:
            raise
        except (ValueError, RuntimeError, OSError) as error:
            raise SemanticError('embedding_failed') from error


def _numpy():
    try:
        import numpy as np
        return np
    except ImportError as error:
        raise SemanticError('numpy_unavailable') from error


def _visible(record):
    return (record.get('review_status') in ('approved', 'published')
            and record.get('publication_status') == 'published')


def _hashes(corpus):
    if not isinstance(corpus, dict) or not isinstance(corpus.get('records'), list):
        raise SemanticError('semantic_corpus_invalid')
    hashes, seen = {}, set()
    for row in corpus['records']:
        if (not isinstance(row, dict) or not isinstance(row.get('id'), str)
                or not isinstance(row.get('content_hash'), str) or row['id'] in seen):
            raise SemanticError('semantic_corpus_invalid')
        seen.add(row['id'])
        if _visible(row):
            hashes[row['id']] = row['content_hash']
    return hashes


def _fingerprints(corpus):
    """Check actual retrieval content even if a caller forgets its version label."""
    names = ('id', 'title', 'edition', 'aliases', 'summary', 'fields', 'field_evidence',
             'sources', 'sections', 'category', 'level', 'review_status', 'publication_status')
    try:
        return {row['id']: hashlib.sha256(json.dumps(
            {name: row.get(name) for name in names}, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False,
        ).encode('utf-8')).hexdigest() for row in corpus['records'] if _visible(row)}
    except (TypeError, ValueError, KeyError) as error:
        raise SemanticError('semantic_corpus_invalid') from error


def _matrix(values, *, expected_rows=None):
    np = _numpy()
    try:
        matrix = np.asarray(values, dtype=np.float32)
        if (matrix.ndim != 2 or not matrix.shape[1]
                or (expected_rows is not None and matrix.shape[0] != expected_rows)
                or not np.isfinite(matrix).all()):
            raise SemanticError('embedding_shape_invalid')
        norms = np.linalg.norm(matrix.astype(np.float64), axis=1, keepdims=True)
        if not np.isfinite(norms).all() or (norms == 0).any():
            raise SemanticError('embedding_zero_vector')
        return (matrix / norms).astype(np.float32)
    except (TypeError, ValueError, OverflowError) as error:
        if isinstance(error, SemanticError):
            raise
        raise SemanticError('embedding_shape_invalid') from error


@dataclass
class SemanticIndex:
    metadata: dict
    vectors: object
    encoder: object = None

    def validate(self, corpus):
        metadata = self.metadata
        if not isinstance(metadata, dict):
            raise SemanticError('semantic_index_metadata_invalid')
        if (metadata.get('schema_version') != 1
                or metadata.get('corpus_version') != corpus.get('version')
                or metadata.get('record_hashes') != _hashes(corpus)
                or metadata.get('record_fingerprints') != _fingerprints(corpus)):
            raise SemanticError('semantic_index_stale')
        if not metadata.get('model_id') or not metadata.get('model_revision'):
            raise SemanticError('semantic_model_metadata_missing')
        chunks = metadata.get('chunks')
        if not isinstance(chunks, list) or not chunks:
            raise SemanticError('semantic_index_empty')
        self.vectors = _matrix(self.vectors, expected_rows=len(chunks))
        current = {str(row['id']): row for row in corpus['records'] if _visible(row)}
        for chunk in chunks:
            if (not isinstance(chunk, dict) or not isinstance(chunk.get('record_id'), str)
                    or not isinstance(chunk.get('section_id'), str)
                    or not isinstance(chunk.get('evidence_ids'), list) or not chunk['evidence_ids']
                    or type(chunk.get('offset')) is not int or chunk['offset'] < 0
                    or any(not isinstance(key, str) for key in chunk['evidence_ids'])):
                raise SemanticError('semantic_chunk_invalid')
            row = current.get(chunk.get('record_id'))
            if row is None or row['content_hash'] != chunk.get('content_hash'):
                raise SemanticError('semantic_index_stale')
            source_ids = {source['id'] for source in row.get('sources', [])}
            if not set(chunk.get('evidence_ids', [])).issubset(source_ids):
                raise SemanticError('semantic_evidence_invalid')
            sections = row.get('sections') or [{'id': 'summary'}]
            if chunk['section_id'] not in {section['id'] for section in sections}:
                raise SemanticError('semantic_section_invalid')
        if self.encoder is not None and (
            getattr(self.encoder, 'model_id', None) != metadata['model_id']
            or getattr(self.encoder, 'revision', None) != metadata['model_revision']
        ):
            raise SemanticError('semantic_model_mismatch')

    def search(self, query, corpus, *, threshold=DEFAULT_THRESHOLD):
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not -1 <= threshold <= 1:
            raise SemanticError('semantic_threshold_invalid')
        self.validate(corpus)
        if self.encoder is None:
            self.encoder = LocalBGEEncoder(
                model_id=self.metadata['model_id'], revision=self.metadata['model_revision'],
            )
        query_vector = _matrix(self.encoder.encode([query], is_query=True), expected_rows=1)
        if query_vector.shape[1] != self.vectors.shape[1]:
            raise SemanticError('semantic_dimension_mismatch')
        scores = self.vectors @ query_vector[0]
        best = {}
        for chunk, score in zip(self.metadata['chunks'], scores):
            if float(score) < threshold:
                continue
            key = chunk['record_id']
            if key not in best or float(score) > best[key]['score']:
                best[key] = {**chunk, 'score': float(score)}
        return sorted(best.values(), key=lambda item: (-item['score'], item['record_id']))


def build_index(corpus, *, encoder=None):
    """Build from an approved corpus. The injected encoder uses encode(texts, is_query=...)."""
    hashes = _hashes(corpus)
    encoder = encoder or LocalBGEEncoder()
    if not getattr(encoder, 'model_id', None) or not getattr(encoder, 'revision', None):
        raise SemanticError('semantic_model_metadata_missing')
    chunks, texts = [], []
    for row in corpus['records']:
        if not _visible(row):
            continue
        source_ids = {source['id'] for source in row.get('sources', [])}
        sections = row.get('sections') or [{
            'id': 'summary', 'heading': row['title'], 'text': row.get('summary', ''),
            'evidence_ids': list(source_ids),
        }]
        for section in sections:
            text = section.get('text', '').strip()
            evidence_ids = [key for key in section.get('evidence_ids', []) if key in source_ids]
            if not text or not evidence_ids:
                continue
            # Paragraph-sized overlapping windows retain section-level provenance.
            for offset in range(0, len(text), 350):
                part = text[offset:offset + 400]
                heading = f"{row['title']} {section.get('heading', '')}"[:80]
                texts.append(f"{heading}\n{part}")
                chunks.append({
                    'record_id': str(row['id']), 'section_id': str(section['id']),
                    'offset': offset, 'content_hash': row['content_hash'],
                    'evidence_ids': evidence_ids,
                })
                if offset + 400 >= len(text):
                    break
    if not texts:
        raise SemanticError('semantic_index_empty')
    vectors = _matrix(encoder.encode(texts, is_query=False), expected_rows=len(texts))
    index = SemanticIndex({
        'schema_version': 1, 'corpus_version': corpus['version'],
        'model_id': encoder.model_id, 'model_revision': encoder.revision,
        'record_hashes': hashes, 'record_fingerprints': _fingerprints(corpus), 'chunks': chunks,
    }, vectors, encoder)
    index.validate(corpus)
    return index


def save_index(index, path):
    """One NPZ file contains vectors and JSON metadata; loading never enables pickle."""
    np = _numpy()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('wb') as stream:
        np.savez_compressed(stream, vectors=index.vectors,
                            metadata=json.dumps(index.metadata, ensure_ascii=False, sort_keys=True))


def load_index(path, *, encoder=None):
    np = _numpy()
    try:
        with np.load(Path(path), allow_pickle=False) as data:
            metadata = json.loads(str(data['metadata'].item()))
            vectors = data['vectors'].copy()
    except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as error:
        raise SemanticError('semantic_index_unreadable') from error
    if not isinstance(metadata, dict):
        raise SemanticError('semantic_index_unreadable')
    return SemanticIndex(metadata, vectors, encoder)
