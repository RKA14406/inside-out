from __future__ import annotations

import base64
import io
import math
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image


MODEL_SHAPES: dict[str, str] = {
    "heart_001": "heart",
    "engine_001": "engine",
    "camera_001": "camera",
    "telescope_001": "telescope",
    "cell_001": "cell",
    "satellite_001": "satellite",
}


@dataclass
class Candidate:
    model_id: str
    score: float
    view: str


def _canvas() -> np.ndarray:
    return np.zeros((256, 256), dtype=np.uint8)


def _line(img: np.ndarray, a: tuple[int, int], b: tuple[int, int], width: int = 7) -> None:
    cv2.line(img, a, b, 255, width, cv2.LINE_AA)


def _ellipse(img: np.ndarray, center: tuple[int, int], axes: tuple[int, int], angle: float = 0, width: int = -1) -> None:
    cv2.ellipse(img, center, axes, angle, 0, 360, 255, width, cv2.LINE_AA)


def draw_reference(shape: str, view: int = 0) -> np.ndarray:
    """Create a neutral line-art reference for the curated local index.

    These are deliberately image primitives rather than labels: retrieval compares
    the query image against a multi-view visual signature made from these drawings.
    """
    img = _canvas()
    if shape == "heart":
        pts = np.array([[128, 218], [68, 154], [48, 104], [58, 64], [92, 54], [128, 78], [164, 54], [198, 64], [208, 104], [188, 154]], np.int32)
        cv2.polylines(img, [pts], False, 255, 9, cv2.LINE_AA)
        _line(img, (127, 79), (127, 195), 5)
        _line(img, (127, 117), (91, 94), 5)
        _line(img, (128, 136), (168, 98), 5)
        _line(img, (84, 24), (84, 57), 12)
        _line(img, (172, 24), (172, 57), 12)
    elif shape == "engine":
        cv2.rectangle(img, (44, 46), (210, 210), 255, 9, cv2.LINE_AA)
        _ellipse(img, (128, 128), (49, 49), width=8)
        _ellipse(img, (128, 128), (16, 16), width=-1)
        for angle in range(0, 360, 45):
            rad = math.radians(angle + view * 8)
            _line(img, (128 + int(math.cos(rad) * 18), 128 + int(math.sin(rad) * 18)), (128 + int(math.cos(rad) * 42), 128 + int(math.sin(rad) * 42)), 6)
        for x in (66, 190):
            _line(img, (x, 30), (x, 46), 8)
    elif shape == "camera":
        cv2.rectangle(img, (34, 76), (222, 192), 255, 10, cv2.LINE_AA)
        pts = np.array([[70, 76], [86, 48], [166, 48], [182, 76]], np.int32)
        cv2.polylines(img, [pts], True, 255, 10, cv2.LINE_AA)
        _ellipse(img, (128, 134), (42, 42), width=10)
        _ellipse(img, (128, 134), (14, 14), width=-1)
        _ellipse(img, (190, 101), (8, 8), width=-1)
    elif shape == "telescope":
        angle = math.radians(-18 + view * 3)
        start = np.array([128, 100])
        direction = np.array([math.cos(angle), math.sin(angle)])
        normal = np.array([-direction[1], direction[0]])
        p1 = start + direction * -75 + normal * 24
        p2 = start + direction * 75 + normal * 24
        p3 = start + direction * 75 - normal * 24
        p4 = start + direction * -75 - normal * 24
        poly = np.array([p1, p2, p3, p4], dtype=np.int32)
        cv2.polylines(img, [poly], True, 255, 9, cv2.LINE_AA)
        _ellipse(img, tuple(start.astype(int)), (31, 31), width=8)
        _line(img, (128, 130), (111, 220), 8)
        _line(img, (128, 130), (164, 220), 8)
        _line(img, (128, 130), (128, 220), 8)
    elif shape == "cell":
        _ellipse(img, (128, 128), (86, 76), width=9)
        _ellipse(img, (118, 132), (25, 25), width=7)
        for x, y, rx, ry in [(78, 96, 11, 7), (167, 93, 10, 15), (82, 163, 13, 8), (171, 153, 9, 11), (126, 69, 8, 12)]:
            _ellipse(img, (x, y), (rx, ry), width=-1)
        for a in range(0, 360, 45):
            rad = math.radians(a)
            _line(img, (128 + int(math.cos(rad) * 32), 128 + int(math.sin(rad) * 32)), (128 + int(math.cos(rad) * 61), 128 + int(math.sin(rad) * 61)), 4)
    elif shape == "satellite":
        cv2.rectangle(img, (103, 76), (153, 180), 255, 8, cv2.LINE_AA)
        _ellipse(img, (128, 58), (22, 22), width=8)
        _line(img, (128, 180), (128, 222), 7)
        _line(img, (128, 200), (92, 222), 7)
        _line(img, (128, 200), (164, 222), 7)
        cv2.rectangle(img, (28, 98), (91, 159), 255, 7, cv2.LINE_AA)
        cv2.rectangle(img, (165, 98), (228, 159), 255, 7, cv2.LINE_AA)
        _line(img, (91, 128), (103, 128), 6)
        _line(img, (153, 128), (165, 128), 6)
    return img


def _feature(image: np.ndarray) -> np.ndarray:
    if float(image.mean()) > 127:
        image = 255 - image
    image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    image = cv2.GaussianBlur(image, (3, 3), 0)
    edges = cv2.Canny(image, 35, 120)
    combined = np.concatenate([image.astype(np.float32).ravel(), edges.astype(np.float32).ravel()])
    combined -= combined.mean()
    norm = np.linalg.norm(combined) + 1e-8
    return combined / norm


def _decode(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("The uploaded image could not be decoded")
    return image


def find_paper(image: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Rectify the largest stable quadrilateral, falling back to the full frame."""
    height, width = image.shape[:2]
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 140)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    best: np.ndarray | None = None
    best_area = 0.0
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
        area = cv2.contourArea(approx)
        if len(approx) == 4 and area > width * height * 0.12 and area > best_area:
            best = approx.reshape(4, 2).astype(np.float32)
            best_area = area
    if best is None:
        return image, {"detected": False, "confidence": 0.35, "quad": None}
    sums = best.sum(axis=1)
    diffs = np.diff(best, axis=1).ravel()
    ordered = np.array([best[np.argmin(sums)], best[np.argmin(diffs)], best[np.argmax(sums)], best[np.argmax(diffs)]], dtype=np.float32)
    target = np.array([[0, 0], [255, 0], [255, 255], [0, 255]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(ordered, target)
    return cv2.warpPerspective(image, matrix, (256, 256)), {"detected": True, "confidence": min(0.99, best_area / (width * height)), "quad": ordered.astype(int).tolist()}


class SketchRetriever:
    def __init__(self) -> None:
        self.index: list[tuple[str, int, np.ndarray]] = []
        for model_id, shape in MODEL_SHAPES.items():
            for view in range(6):
                self.index.append((model_id, view, _feature(draw_reference(shape, view))))

    def search(self, image: np.ndarray, limit: int = 3) -> list[Candidate]:
        query = _feature(image)
        scores: dict[str, tuple[float, int]] = {}
        for model_id, view, vector in self.index:
            score = float(np.dot(query, vector))
            if model_id not in scores or score > scores[model_id][0]:
                scores[model_id] = (score, view)
        ranked = sorted(scores.items(), key=lambda item: item[1][0], reverse=True)[:limit]
        return [Candidate(model_id, max(0.0, min(0.99, (score + 1) / 2)), f"view-{view + 1}") for model_id, (score, view) in ranked]

    def retrieve(self, data: bytes) -> dict[str, Any]:
        started = time.perf_counter()
        image = _decode(data)
        rectified, paper = find_paper(image)
        candidates = self.search(rectified)
        if not candidates:
            raise ValueError("No visual matches found")
        ok, buffer = cv2.imencode(".png", rectified)
        thumbnail = "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode("ascii") if ok else None
        return {
            "match": candidates[0].model_id,
            "confidence": round(candidates[0].score, 3),
            "bestView": candidates[0].view,
            "candidates": [candidate.__dict__ for candidate in candidates],
            "paper": paper,
            "queryPreview": thumbnail,
            "embeddingMs": round((time.perf_counter() - started) * 1000, 1),
        }
