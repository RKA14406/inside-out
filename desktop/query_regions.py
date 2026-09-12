"""Cheap, paper-optional visual-query proposals shared by camera and file input."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from desktop.config import MAX_QUERY_REGIONS


@dataclass
class QueryRegion:
    image: np.ndarray
    kind: str
    score: float
    rect: tuple[int, int, int, int]
    quad: np.ndarray | None = None

    def payload(self) -> dict:
        return dict(image=self.image, kind=self.kind, score=float(self.score),
                    rect=tuple(int(v) for v in self.rect),
                    quad=None if self.quad is None else self.quad.astype(float).tolist())


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    x0, y0, x1, y1 = max(ax, bx), max(ay, by), min(ax+aw, bx+bw), min(ay+ah, by+bh)
    intersection = max(0, x1-x0) * max(0, y1-y0)
    return intersection / max(aw*ah + bw*bh - intersection, 1)


def _drawing_boxes(frame: np.ndarray) -> list[tuple[float, tuple[int, int, int, int]]]:
    """Find grouped high-contrast or chromatic strokes without assuming black ink."""
    h, w = frame.shape[:2]
    scale = min(1.0, 720.0/max(w, 1))
    small = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    # Local colour contrast catches blue pen on white or coloured paper; local
    # luminance and edges retain pencil and printed-image boundaries.
    smooth = cv2.GaussianBlur(lab, (0, 0), 11).astype(np.int16)
    delta = np.linalg.norm(lab.astype(np.int16)-smooth, axis=2)
    local_gray = cv2.absdiff(gray, cv2.GaussianBlur(gray, (0, 0), 11))
    edges = cv2.Canny(gray, 35, 105)
    ink = ((delta > 13) | (local_gray > 11) | (edges > 0)).astype(np.uint8)*255
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    # Join nearby strokes into one symbol while keeping unrelated scene regions apart.
    join = max(5, round(min(sh, sw)*.018))
    grouped = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (join, join)), iterations=2)
    contours = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    boxes = []
    diagonal = max(float(np.hypot(sw, sh)), 1.)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
        x, y, bw, bh = cv2.boundingRect(contour)
        area_ratio = bw*bh/max(sw*sh, 1)
        # Near-full-frame groups are normally hair, clothing, furniture, or a
        # page merged with the scene. They were the source of the giant debug
        # border and made background clutter compete with the drawing.
        if area_ratio < .008 or area_ratio > .62 or min(bw, bh) < 28:
            continue
        margin = max(12, round(max(bw, bh)*.18))
        x0, y0 = max(0, x-margin), max(0, y-margin)
        x1, y1 = min(sw, x+bw+margin), min(sh, y+bh+margin)
        roi_ink = ink[y:y+bh, x:x+bw]
        density = float(np.mean(roi_ink > 0))
        if density < .006 or density > .55:
            continue
        center_distance = float(np.linalg.norm(np.array([x+bw/2, y+bh/2])-
                                               np.array([sw/2, sh/2])))/diagonal
        score = .72 + min(.28, density*1.5) + min(.22, area_ratio) - center_distance*.24
        boxes.append((score, (round(x0/scale), round(y0/scale),
                              round((x1-x0)/scale), round((y1-y0)/scale))))
    return boxes


def detect_query_regions(frame: np.ndarray, paper=None, max_regions: int = MAX_QUERY_REGIONS) -> list[QueryRegion]:
    """Return 3–4 strong candidates: optional page, strokes, center, full frame."""
    if frame is None or frame.size == 0:
        return []
    h, w = frame.shape[:2]
    candidates: list[QueryRegion] = []
    if paper is not None and paper.quad is not None and paper.crop.size:
        x, y, bw, bh = cv2.boundingRect(paper.quad.astype(np.float32))
        candidates.append(QueryRegion(paper.crop.copy(), 'page/rectangle', 1.30,
                                      (x, y, bw, bh), paper.quad.copy()))
    page_rect=None if paper is None or paper.quad is None else cv2.boundingRect(paper.quad.astype(np.float32))
    for score, rect in _drawing_boxes(frame):
        x, y, bw, bh = rect
        if page_rect is not None:
            px,py,pw,ph=page_rect; cx,cy=x+bw/2,y+bh/2
            # Once a page is known, ignore scene texture outside it and retain
            # only a compact stroke group that could genuinely be its drawing.
            if not (px<=cx<=px+pw and py<=cy<=py+ph) or bw*bh>pw*ph*.55:
                continue
            score=min(score,1.08)
        candidates.append(QueryRegion(frame[y:y+bh, x:x+bw].copy(), 'drawing-region', score, rect))
    # Poster/page-like rectangles that are not bright enough for the paper path.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.morphologyEx(cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 45, 130),
                             cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    for contour in sorted(cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
                          key=cv2.contourArea, reverse=True)[:12]:
        perimeter = cv2.arcLength(contour, True)
        poly = cv2.approxPolyDP(contour, .025*perimeter, True)
        area = cv2.contourArea(poly)/max(gray.size, 1)
        if len(poly) != 4 or not cv2.isContourConvex(poly) or not .06 < area < .88:
            continue
        x, y, bw, bh = cv2.boundingRect(poly)
        if min(bw, bh) < 80:
            continue
        margin = round(max(bw, bh)*.025)
        x0, y0, x1, y1 = max(0, x-margin), max(0, y-margin), min(w, x+bw+margin), min(h, y+bh+margin)
        rect = (x0, y0, x1-x0, y1-y0)
        candidates.append(QueryRegion(frame[y0:y1, x0:x1].copy(), 'image/poster', .70+area*.2, rect))
        break
    # Lower-priority fallbacks guarantee recognition never depends on a boundary.
    side_w, side_h = round(w*.78), round(h*.78)
    cx, cy = (w-side_w)//2, (h-side_h)//2
    candidates.append(QueryRegion(frame[cy:cy+side_h, cx:cx+side_w].copy(), 'center-fallback', .42,
                                  (cx, cy, side_w, side_h)))
    candidates.append(QueryRegion(frame.copy(), 'full-frame', .30, (0, 0, w, h)))
    selected: list[QueryRegion] = []
    ranked=[item for item in sorted(candidates,key=lambda item:item.score,reverse=True)
            if item.kind not in {'center-fallback','full-frame'}]
    for candidate in ranked:
        if candidate.image.size and all(_iou(candidate.rect, old.rect) < .88 for old in selected):
            selected.append(candidate)
        if len(selected) >= max(1,max_regions-1):
            break
    fallback=next(item for item in candidates if item.kind=='center-fallback')
    if all(_iou(fallback.rect,old.rect)<.95 for old in selected):
        selected.append(fallback)
    if not selected:
        selected.append(next(item for item in candidates if item.kind=='full-frame'))
    return selected


def draw_regions(frame: np.ndarray, regions: list[QueryRegion], selected: int = 0) -> np.ndarray:
    overlay = frame.copy()
    palette = [(0, 210, 255), (90, 220, 120), (255, 170, 70), (180, 120, 255)]
    for index, region in enumerate(regions):
        # Fallbacks remain available to retrieval but do not need to cover most
        # of the judge-facing camera preview unless they actually win.
        if index != selected and region.kind in {'center-fallback','full-frame'}:
            continue
        x, y, w, h = region.rect
        color = (0, 245, 255) if index == selected else palette[index % len(palette)]
        thickness=3 if index == selected else 1
        if region.quad is not None:
            cv2.polylines(overlay,[region.quad.astype(np.int32)],True,color,thickness,cv2.LINE_AA)
        else:
            cv2.rectangle(overlay, (x, y), (x+w, y+h), color, thickness)
        label='query' if index==selected else region.kind
        cv2.putText(overlay, label, (x+4, max(20, y-7)),
                    cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1, cv2.LINE_AA)
    return overlay
