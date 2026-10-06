"""Compatibility entry point for the single pinned competition embedding model."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('prepare-competition-model.py')), run_name='__main__')
