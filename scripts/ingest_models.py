"""Normalize assets, retain graph/meshes, render previews, and update retrieval index."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop.library import ingest, identifier, read_manifest, save_manifest
from desktop.paths import ASSETS, ROOT, relative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', nargs='?', default=str(ASSETS/'sources'))
    parser.add_argument('--cache-only', action='store_true', help='Defer preview and embedding generation')
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    models = {m['id']:m for m in read_manifest()}
    failures = []
    for file in sorted(directory.rglob('*')):
        if file.suffix.lower() not in {'.glb','.gltf','.obj'}:
            continue
        sidecar = file.with_suffix('.metadata.json')
        if not sidecar.exists():
            sidecar = file.parent/'metadata.json'
        source = json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
        source['id']=identifier(source.get('id',file.stem)); source.setdefault('name',file.stem.replace('_',' ').title())
        source.setdefault('license','Unspecified - local use only; verify rights before sharing')
        source.setdefault('source','User supplied local asset'); source.setdefault('author','Unspecified')
        source.setdefault('category','Imported')
        if not file.is_relative_to(ROOT):
            target = ASSETS/'sources'/source['id']
            shutil.copytree(file.parent,target,dirs_exist_ok=True)
            file = target/file.name
        source['file'] = relative(file)
        try:
            print('Ingesting '+source['name'],flush=True)
            model = ingest(file, source); models[model['id']]=model
            print(f"  {model['partCount']} parts; hierarchy depth {model['hierarchyDepth']}",flush=True)
        except Exception as exc:
            failures.append(f'{file.name}: {exc}')
            print(f'  Unable to ingest: {exc}',flush=True)
    save_manifest(list(models.values()))
    if not args.cache_only and models:
        from scripts.render_views import main as render
        from scripts.build_index import main as index
        render(); index()
    if failures:
        raise SystemExit('\n'.join(failures))


if __name__ == "__main__":
    main()
