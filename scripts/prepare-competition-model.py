"""Download the pinned public embedding model into the local workspace cache."""
import argparse
import json
from pathlib import Path

MODEL = 'BAAI/bge-small-zh-v1.5'
REVISION = '7999e1d3359715c523056ef9478215996d62a620'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / '.local/models/bge-small-zh-v1.5')
    args = parser.parse_args()
    from huggingface_hub import snapshot_download
    path = snapshot_download(MODEL, revision=REVISION, local_dir=str(args.output),
                             allow_patterns=['*.json', '*.txt', '*.safetensors', '1_Pooling/*', 'README.md', 'LICENSE*'])
    (Path(path) / 'revision.json').write_text(json.dumps({'model_id': MODEL, 'revision': REVISION}) + '\n', encoding='utf-8')
    print(json.dumps({'model_id': MODEL, 'revision': REVISION, 'path': path}))


if __name__ == '__main__':
    main()
