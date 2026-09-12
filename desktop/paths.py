from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets' / 'desktop'
MANIFEST = ASSETS / 'manifest.json'
INDEX = ROOT / 'data' / 'model_index' / 'desktop.npz'
COMPETITION_INDEX = ROOT / 'data' / 'model_index' / 'competition.npz'
WEIGHTS = ROOT / 'data' / 'weights' / 'open_clip_model.safetensors'
ENCODER = 'ViT-B-32/laion2b_s34b_b79k'


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def local(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Asset path must stay inside this project')
    return path
