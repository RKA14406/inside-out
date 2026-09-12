"""Check that obvious non-competition drawings are rejected by the real retriever."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.encoder import Retriever, query_diagnostics


def samples() -> dict[str, np.ndarray]:
    blank = np.full((480, 640, 3), 255, np.uint8)
    circle = blank.copy()
    cv2.circle(circle, (320, 240), 120, (30, 30, 30), 8)
    scribble = blank.copy()
    points = np.array([[120, 100], [500, 340], [180, 380], [460, 110], [300, 420]], np.int32)
    cv2.polylines(scribble, [points], False, (20, 20, 20), 9)
    text = blank.copy()
    cv2.putText(text, "THIS IS TEXT", (95, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (20, 20, 20), 4)
    return {"blank": blank, "plain_circle": circle, "scribble": scribble, "text": text}


def main() -> int:
    retriever = Retriever("cpu")
    failed = False
    for name, image in samples().items():
        diagnostic = query_diagnostics(image)
        try:
            result = retriever.retrieve(image)
            top = result["candidates"][0]
            accepted = bool(result["accepted"])
            print(f"{name}: diagnostic={diagnostic} top={top['id']} score={top['score']:.4f} "
                  f"margin={result['margin']:.4f} accepted={accepted} "
                  f"latency_ms={result['timings']['totalMs']:.1f}")
        except ValueError as error:
            accepted = False
            print(f"{name}: diagnostic={diagnostic} rejected before ranking ({error})")
        failed |= accepted
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
