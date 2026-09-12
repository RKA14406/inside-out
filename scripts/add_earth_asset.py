"""Compatibility entry point for the current four-layer competition Earth."""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop.library import ingest, read_manifest, save_manifest
from desktop.paths import ASSETS, relative
from scripts.render_views import render_model


MODEL_URL = 'https://assets.science.nasa.gov/content/dam/science/psd/solar/2023/09/e/Earth_1_12756.glb'
SOURCE_URL = 'https://science.nasa.gov/resource/earth-3d-model/'
USAGE_URL = 'https://www.nasa.gov/nasa-brand-center/images-and-media/'


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'InsideOut-local-prototype/1.0'})
    temporary = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    temporary.replace(path)


def main() -> None:
    from scripts.prepare_competition_assets import main as prepare_assets
    prepare_assets()
    from scripts.render_views import main as render_views
    render_views()
    print('Installed the current four-layer competition Earth fallback.')


if __name__ == '__main__':
    main()
