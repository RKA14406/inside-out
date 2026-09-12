"""Offline index build only. Normal desktop startup never renders or embeds assets."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image

from desktop.encoder import VisualEncoder, shape_feature
from desktop.library import read_manifest
from desktop.paths import ENCODER, INDEX, local


def main():
    models = read_manifest()
    encoder = VisualEncoder()
    vectors, shapes, ids, paths, angles = [], [], [], [], []
    for model in models:
        views = model.get('previewImages', [])
        if not views:
            raise ValueError('Run render_views.py before indexing '+model['name'])
        print(f"Indexing {model['name']}: {len(views)} rendered images on {encoder.device}",flush=True)
        images = [Image.open(local(v['path'])).convert('RGB') for v in views]
        vectors.extend(encoder.encode(images))
        shapes.extend(shape_feature(cv2.imread(str(local(v['path'])))) for v in views)
        ids.extend([model['id']]*len(views)); paths.extend(v['path'] for v in views); angles.extend(v['angle'] for v in views)
        for image in images:
            image.close()
    INDEX.parent.mkdir(parents=True,exist_ok=True)
    temp = INDEX.with_suffix('.partial.npz')
    np.savez_compressed(temp, vectors=np.asarray(vectors,dtype=np.float32), shapes=np.asarray(shapes,dtype=np.float32),
                        model_ids=np.asarray(ids), paths=np.asarray(paths), angles=np.asarray(angles),encoder=np.asarray(ENCODER))
    temp.replace(INDEX)
    print(f'Saved {len(ids)} image vectors to {INDEX}',flush=True)


if __name__ == '__main__':
    main()
