"""Explicitly download the pinned free model outside request handling."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from ai_services.embedding_spec import DIMENSION, MODEL_ID, MODEL_REVISION  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.local' / 'models' / 'multilingual-e5-small')
    args = parser.parse_args()
    from huggingface_hub import snapshot_download

    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=target,
                      ignore_patterns=['*.bin', 'onnx/*', 'openvino/*', '*.h5', '*.ot'])
    if not (target / 'model.safetensors').is_file():
        raise RuntimeError('Model weights were not downloaded')
    (target / '.ai-model.json').write_text(json.dumps({
        'model_id': MODEL_ID, 'revision': MODEL_REVISION, 'dimension': DIMENSION,
    }, sort_keys=True), encoding='utf-8')
    print(f'Prepared pinned local model at {target}')


if __name__ == '__main__':
    main()
