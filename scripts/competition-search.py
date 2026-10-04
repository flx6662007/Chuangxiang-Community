"""Build a local semantic index or run competition retrieval without a chat API."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?', default='')
    parser.add_argument('--corpus', type=Path, default=ROOT / 'docs/competition-knowledge/corpus.json')
    parser.add_argument('--database', action='store_true', help='Use currently approved and visible database documents')
    parser.add_argument('--index', type=Path, default=ROOT / '.local/competition-search/index.npz')
    parser.add_argument('--model', type=Path, default=ROOT / '.local/models/bge-small-zh-v1.5')
    parser.add_argument('--build-index', action='store_true')
    parser.add_argument('--mode', choices=['keyword', 'semantic', 'hybrid'], default='hybrid')
    parser.add_argument('--filters', default='{}', help='JSON object of explicit constraints')
    parser.add_argument('--preferences', default='{}', help='JSON object of ranking preferences')
    parser.add_argument('--as-of', default=None)
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    from information_library.competition_search import search_competitions
    from information_library.semantic import LocalBGEEncoder, build_index, save_index
    if args.database:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from information_library.competition_search import database_corpus
        corpus = database_corpus()
    else:
        corpus = json.loads(args.corpus.read_text(encoding='utf-8'))
    index = None
    if args.build_index:
        encoder = LocalBGEEncoder(model_path=str(args.model))
        index = build_index(corpus, encoder=encoder)
        save_index(index, args.index)
        print(json.dumps({'index': str(args.index), 'corpus_version': corpus['version'],
                          'records': len(corpus['records']), 'chunks': len(index.metadata['chunks']),
                          'model_revision': encoder.revision}, ensure_ascii=False))
        return
    if args.mode != 'keyword':
        os.environ['COMPETITION_EMBEDDING_MODEL_PATH'] = str(args.model)
        # Let the service handle unavailable models and invalid indices with the
        # same explicit diagnostic returned to backend callers.
        index = args.index
    result = search_competitions(args.query, filters=json.loads(args.filters),
        preferences=json.loads(args.preferences), as_of=args.as_of, mode=args.mode,
        limit=args.limit, corpus=corpus, index=index)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
