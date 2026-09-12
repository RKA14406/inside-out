"""Fetch explicitly licensed assets from their publishers; retain provenance."""
from __future__ import annotations

import concurrent.futures
import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.paths import ASSETS, WEIGHTS, relative

KHR = 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main'
HRA = 'https://raw.githubusercontent.com/hubmapconsortium/ccf-releases/main/v1.2'

SOURCES = [
    dict(id='human_heart', name='Human heart', category='Anatomy', author='Kristen Browne; Heidi Schlehlein / HuBMAP HRA',
         license='CC-BY-4.0', licenseUrl='https://creativecommons.org/licenses/by/4.0/',
         source='https://doi.org/10.48539/HBM373.VSTV.568', url=HRA+'/models/VH_M_Heart.glb',
         licenseText=HRA+'/markdown/ref-organs/heart-male.md', semanticParts=True),
    dict(id='human_lungs', name='Human lungs', category='Anatomy', author='Kristen Browne; Heidi Schlehlein / HuBMAP HRA',
         license='CC-BY-4.0', licenseUrl='https://creativecommons.org/licenses/by/4.0/',
         source='https://doi.org/10.48539/HBM787.FWXN.723', url=HRA+'/models/VH_M_Lung.glb',
         licenseText=HRA+'/markdown/ref-organs/lung-male.md', semanticParts=True),
    *[dict(id=ident, name=name, category=category, author=author, license='CC0-1.0',
           licenseUrl='https://creativecommons.org/publicdomain/zero/1.0/',
           source=f'https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/{folder}',
           url=f'{KHR}/Models/{folder}/glTF-Binary/{folder}.glb',
           licenseText=f'{KHR}/Models/{folder}/README.md', semanticParts=False)
      for ident, name, category, author, folder in [
          ('antique_camera','Antique camera','Optics','Maximillan Kamps / UX3D','AntiqueCamera'),
          ('lantern','Lantern','Lighting','Microsoft; sbtron','Lantern'),
          ('water_bottle','Water bottle','Everyday objects','Microsoft','WaterBottle')]],
    dict(id='toy_car',name='Car',category='Mechanics',author='Eric Chadwick / Darmstadt Graphics Group GmbH; Khronos Group',
         license='CC-BY-4.0',licenseUrl='https://creativecommons.org/licenses/by/4.0/',
         source='https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarConcept',
         url=KHR+'/Models/CarConcept/glTF-Binary/CarConcept.glb',
         licenseText=KHR+'/Models/CarConcept/LICENSE.md',semanticParts=True),
]


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    request = urllib.request.Request(url, headers={'User-Agent': 'InsideOut-local-prototype/1.0'})
    temporary = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    temporary.replace(path)


def fetch_asset(spec: dict) -> dict:
    folder = ASSETS / 'sources' / spec['id']
    model = folder / ('CarConcept-original.glb' if spec['id']=='toy_car' else spec['id']+'.glb')
    download(spec['url'], model)
    download(spec['licenseText'], folder / 'SOURCE_LICENSE.md')
    if spec['id'] == 'antique_camera':
        download(KHR+'/LICENSES/LicenseRef-LegalMark-UX3D.txt', folder / 'UX3D_MARK_NOTICE.txt')
    previous_file=folder/'metadata.json'
    previous=json.loads(previous_file.read_text(encoding='utf-8')) if previous_file.exists() else {}
    metadata = {**spec, 'file': relative(model), 'downloadDate': previous.get('downloadDate',datetime.date.today().isoformat()),
                'sha256': hashlib.sha256(model.read_bytes()).hexdigest(), 'bytes': model.stat().st_size,
                'modifications': 'Original GLB retained. Runtime cache normalizes scale and preserves mesh transforms.'}
    (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f"Downloaded {spec['name']}: {metadata['bytes'] / 1e6:.1f} MB", flush=True)
    return metadata


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        sources = list(pool.map(fetch_asset, SOURCES))
    (ASSETS / 'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    print('Downloading OpenCLIP weights (~605 MB, one time)...', flush=True)
    download('https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/resolve/main/open_clip_model.safetensors', WEIGHTS)
    download('https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/raw/main/README.md', WEIGHTS.parent / 'OPENCLIP_MODEL_CARD.md')
    print(f'Local visual encoder saved: {WEIGHTS.stat().st_size / 1e6:.1f} MB', flush=True)
    # Produces the logo-neutral grouped CarConcept runtime copy and the legal
    # four-layer Earth fallback before the normal ingestion step runs.
    from scripts.prepare_competition_assets import main as prepare_assets
    prepare_assets()


if __name__ == '__main__':
    main()
