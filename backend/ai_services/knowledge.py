"""Local E5 embedding and exact small-corpus search over current public revisions."""

from functools import lru_cache
import hashlib
import json
import math
import os
import re

from django.db import OperationalError, ProgrammingError, transaction

from curation.models import DocumentReview, KnowledgeChunk
from curation.retrieval import student_visible_documents
from information_library.selectors import public_text, safe_source_url
from .embedding_spec import MODEL_ID, MODEL_REVISION, DIMENSION



class EmbeddingUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def local_encoder():
    path = os.getenv('AI_EMBEDDING_MODEL_PATH', '')
    if not path or not os.path.isdir(path):
        raise EmbeddingUnavailable('local_model_missing')
    try:
        with open(os.path.join(path, '.ai-model.json'), encoding='utf-8') as stream:
            manifest = json.load(stream)
        if manifest != {'model_id': MODEL_ID, 'revision': MODEL_REVISION, 'dimension': DIMENSION}:
            raise EmbeddingUnavailable('local_model_revision_mismatch')
    except (OSError, ValueError, TypeError) as error:
        raise EmbeddingUnavailable('local_model_manifest_missing') from error
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(path, device='cpu', local_files_only=True, trust_remote_code=False)
        if model.get_sentence_embedding_dimension() != DIMENSION:
            raise EmbeddingUnavailable('model_dimension_mismatch')
        return model
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        raise EmbeddingUnavailable('local_model_unavailable') from error


def _vectors(encoder, texts, *, query=False):
    prefix = 'query: ' if query else 'passage: '
    vectors = encoder.encode([prefix + text for text in texts], normalize_embeddings=True,
                             convert_to_numpy=True, show_progress_bar=False)
    result = []
    for vector in vectors:
        row = [float(value) for value in vector]
        if len(row) != DIMENSION or not all(math.isfinite(value) for value in row):
            raise EmbeddingUnavailable('invalid_embedding')
        result.append(row)
    return result


def _source(revision):
    rows = revision.sources if isinstance(revision.sources, list) else []
    sources = [(url, public_text(source.get('locator', ''))[:300])
               for source in rows if isinstance(source, dict)
               if (url := safe_source_url(source.get('url')))]
    # There is no passage-to-source map in DocumentRevision. A multi-URL body cannot be
    # attributed to one URL safely, so leave it out until reviewed source mapping exists.
    return sources[0] if len({url for url, _ in sources}) == 1 else None


def _parts(text, size=700, overlap=80):
    # Character boundaries are stable for rebuilds; no invented PDF page number.
    for position, start in enumerate(range(0, len(text), size - overlap)):
        part = text[start:start + size].strip()
        if part:
            yield position, part
        if start + size >= len(text):
            break


def rebuild_index(*, encoder=None):
    """Explicit maintenance action. Failed encoding leaves old rows untouched."""
    documents = list(student_visible_documents().select_related('current_revision'))
    prepared = []
    for doc in documents:
        revision = doc.current_revision
        source = _source(revision)
        body = public_text(revision.body)
        if not source or not body.strip():
            continue
        for position, part in _parts(body):
            prepared.append((doc, revision, position, part, *source,
                             hashlib.sha256(body.encode()).hexdigest()))
    if len(prepared) > 2000:
        raise EmbeddingUnavailable('exact_index_capacity_exceeded')
    if prepared:
        encoder = encoder or local_encoder()
        vectors = _vectors(encoder, [row[3] for row in prepared])
    else:
        vectors = []
    with transaction.atomic():
        KnowledgeChunk.objects.all().delete()
        KnowledgeChunk.objects.bulk_create([
            KnowledgeChunk(document=doc, revision=revision, position=position, text=part,
                           source_url=url, locator=locator, content_hash=revision.content_hash,
                           text_hash=digest, model_id=MODEL_ID, model_revision=MODEL_REVISION,
                           dimension=DIMENSION, vector=vector)
            for (doc, revision, position, part, url, locator, digest), vector in zip(prepared, vectors)
        ])
    return len(vectors)


def retrieve_knowledge(question, *, limit=4, encoder=None):
    visible = {doc.pk: doc for doc in student_visible_documents().select_related('current_revision')}
    if not visible:
        return [], 'no_published_knowledge'
    try:
        # An optional index may not be installed yet; preserve outer transactions on PostgreSQL.
        with transaction.atomic():
            chunks = list(KnowledgeChunk.objects.filter(document_id__in=visible, model_id=MODEL_ID,
                                                       model_revision=MODEL_REVISION, dimension=DIMENSION)
                          .order_by('pk')[:2000])
    except (OperationalError, ProgrammingError):
        return [], 'index_unavailable'
    candidates = []
    current = {}
    for chunk in chunks:
        doc = visible[chunk.document_id]
        revision = doc.current_revision
        if doc.pk not in current:
            body = public_text(revision.body)
            current[doc.pk] = (hashlib.sha256(body.encode()).hexdigest(), _source(revision))
        digest, source = current[doc.pk]
        if (chunk.revision_id != revision.pk or chunk.content_hash != revision.content_hash
                or chunk.text_hash != digest or source is None or chunk.source_url != source[0]):
            continue
        candidates.append((chunk, doc, revision))
    if not candidates:
        return [], 'index_unavailable'
    try:
        encoder = encoder or local_encoder()
        query_vector = _vectors(encoder, [question[:500]], query=True)[0]
    except EmbeddingUnavailable:
        return [], 'embedding_unavailable'
    scored = []
    for chunk, doc, revision in candidates:
        vector = chunk.vector
        if not isinstance(vector, list) or len(vector) != DIMENSION:
            continue
        cosine = sum(a * b for a, b in zip(query_vector, vector))
        # Conservative lexical gate avoids claiming a semantic hit on unrelated topics.
        terms = re.findall(r'[\u4e00-\u9fff]{2,}|[a-z]{2,}', question.casefold())
        lexical = sum(term in (revision.title + chunk.text).casefold() for term in terms)
        if lexical or cosine >= 0.72:
            scored.append((cosine + min(lexical, 2) * .1, chunk, doc, revision))
    scored.sort(key=lambda row: row[0], reverse=True)
    result = []
    for _, chunk, doc, revision in scored[:limit]:
        review = (DocumentReview.objects.filter(document=doc, revision=revision, status='approved')
                  .order_by('-created_at').first() if doc.review_status == 'approved' else None)
        result.append({'kind': 'knowledge', 'entity_id': str(doc.pk), 'version': str(revision.version),
                       'title': public_text(revision.title), 'url': chunk.source_url, 'internal_url': None,
                       'text': chunk.text, 'verified_at': review.created_at.isoformat() if review else None,
                       'published_on': None,
                       'status': doc.review_status, 'status_note': '公开知识资料',
                       'locator': chunk.locator or None, 'edition': revision.edition or None,
                       'content_hash': chunk.content_hash})
    return result, 'ready' if result else 'no_match'
