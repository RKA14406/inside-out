"""Document quadrilateral detection and normalized sketch acquisition."""
from __future__ import annotations

from dataclasses import dataclass
import time

import cv2
import numpy as np

from desktop.config import (
    PAPER_CONTENT_HARD,
    PAPER_CONTENT_SOFT,
    PAPER_MOVEMENT_HARD,
    PAPER_MOVEMENT_SOFT,
    PAPER_QUAD_SMOOTHING_MAX,
    PAPER_QUAD_SMOOTHING_MIN,
    PAPER_STABLE_SECONDS,
    PAPER_UNSTABLE_DECAY,
)


def _order_quad(points: np.ndarray) -> np.ndarray:
    points=np.asarray(points,dtype=np.float32)
    center=points.mean(0)
    points=points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))]
    return np.roll(points,-np.argmin(points.sum(1)),axis=0)


def _color_paper_candidate(image: np.ndarray) -> np.ndarray | None:
    """Recover a page whose torn/occluded border cannot form four edge corners.

    The fallback is intentionally bounded: it needs a bright central color
    cluster that fills a plausible rotated rectangle. It never returns the full
    frame as a crop.
    """
    height,width=image.shape[:2]
    # This runs only after the inexpensive contour path fails. Keep the sample
    # deliberately small so an empty scene cannot stall paper updates.
    sample_width=min(128,width)
    sample_height=max(60,round(height*sample_width/width))
    sample=cv2.resize(image,(sample_width,sample_height),interpolation=cv2.INTER_AREA)
    lab_sample=cv2.cvtColor(sample,cv2.COLOR_BGR2LAB).astype(np.float32)
    pixels=lab_sample.reshape(-1,3)
    cv2.setRNGSeed(17)
    _,labels,centers=cv2.kmeans(
        pixels,6,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,25,.35),
        2,cv2.KMEANS_PP_CENTERS)
    y0,y1=round(sample_height*.32),round(sample_height*.62)
    x0,x1=round(sample_width*.32),round(sample_width*.68)
    seed=np.median(lab_sample[y0:y1,x0:x1].reshape(-1,3),axis=0)
    if seed[0] < 145:
        return None
    eligible=np.flatnonzero(centers[:,0]>=145)
    if not len(eligible):
        return None
    # Prefer the cluster nearest the central page sample, with a small bias to
    # its illuminated paper surface rather than adjacent shirt/shadow colors.
    color_distances=np.linalg.norm(centers[eligible]-seed,axis=1)
    distances=color_distances-centers[eligible,0]*.035
    order=eligible[np.argsort(distances)]
    cluster_groups=[(int(order[0]),)]
    if len(order)>1:
        second=int(order[1])
        second_distance=float(np.linalg.norm(centers[second]-seed))
        if second_distance<22:
            # Illumination can split one sheet into two nearby color clusters.
            # Evaluate both pieces and their union; geometry chooses the page.
            cluster_groups.extend([(second,),(int(order[0]),second)])
    label_image=labels.reshape(sample_height,sample_width)
    # A white/blue page can be almost identical to a light shirt. Preserve the
    # visible page boundary as a barrier so those touching color regions do not
    # become one oversized rectangle.
    sample_gray=cv2.cvtColor(sample,cv2.COLOR_BGR2GRAY)
    boundary=cv2.dilate(cv2.Canny(sample_gray,30,90),np.ones((3,3),np.uint8))
    candidates=[]
    diagonal=max(float(np.hypot(sample_width,sample_height)),1.)
    for group in cluster_groups:
        mask=np.isin(label_image,group).astype(np.uint8)*255
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        mask[boundary>0]=0
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
        contours=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:6]:
            contour_area=cv2.contourArea(contour)
            rect=cv2.minAreaRect(contour)
            rw,rh=rect[1]
            box_area=rw*rh
            if min(rw,rh)<28 or box_area<=0:
                continue
            area_ratio=box_area/(sample_width*sample_height)
            fill=contour_area/box_area
            aspect=max(rw,rh)/max(min(rw,rh),1e-6)
            center_distance=np.linalg.norm(np.asarray(rect[0])-[sample_width/2,sample_height/2])/diagonal
            if not .10<area_ratio<.48 or fill<.45 or aspect>2.05 or center_distance>.34:
                continue
            score=fill+area_ratio*.35-center_distance-.45*abs(float(np.log(aspect)))
            candidates.append((score,cv2.boxPoints(rect)))
    if not candidates:
        return None
    box=max(candidates,key=lambda row:row[0])[1]
    box*=np.array([width/sample_width,height/sample_height],dtype=np.float32)
    return _order_quad(box)


def sketch_stages(image: np.ndarray, size: int = 224) -> dict[str, np.ndarray]:
    """Return the exact intermediate images used to build a retrieval query."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    h, w = gray.shape
    gray = gray[int(h*.025):max(int(h*.975), 1), int(w*.025):max(int(w*.975), 1)]
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # Remove slowly varying illumination, preserve dark pencil strokes.
    background = cv2.GaussianBlur(gray, (0, 0), 18)
    corrected = cv2.divide(gray, np.maximum(background, 1), scale=245)
    _, ink = cv2.threshold(corrected, 205, 255, cv2.THRESH_BINARY_INV)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink)
    clean = np.zeros_like(ink)
    valid = []
    for i in range(1, count):
        x, y, bw, bh, area = stats[i]
        # Suppress specks and contours spanning the entire image edge.
        touches = x == 0 or y == 0 or x+bw >= ink.shape[1] or y+bh >= ink.shape[0]
        if area >= max(4, ink.size*.000015) and not (touches and (bw > ink.shape[1]*.9 or bh > ink.shape[0]*.9)):
            clean[labels == i] = 255
            valid.append((i,x,y,bw,bh,area,touches))
    # Shadows, fingers, torn edges, and paper defects can be darker/larger than
    # the sketch. Prefer a central stroke-like component, then retain enclosed
    # components (for car wheels and Earth continents) inside its region.
    candidates=[]
    image_center=np.array([clean.shape[1]/2,clean.shape[0]/2])
    diagonal=max(float(np.linalg.norm(image_center)),1.)
    for i,x,y,bw,bh,area,touches in valid:
        occupancy=area/max(bw*bh,1)
        center=np.array([x+bw/2,y+bh/2])
        distance=float(np.linalg.norm(center-image_center))/diagonal
        if not touches and max(bw,bh)>=8 and occupancy<.48:
            score=area*(1-occupancy)*(.35+np.exp(-3*distance))
            candidates.append((score,i,x,y,bw,bh))
    if candidates:
        _,_,x,y,bw,bh=max(candidates,key=lambda row:row[0])
        margin=max(10,round(max(bw,bh)*.18))
        x0,y0=max(0,x-margin),max(0,y-margin)
        x1,y1=min(clean.shape[1],x+bw+margin),min(clean.shape[0],y+bh+margin)
        focused=np.zeros_like(clean)
        for i,cx,cy,cw,ch,area,touches in valid:
            center_x,center_y=cx+cw/2,cy+ch/2
            if x0<=center_x<=x1 and y0<=center_y<=y1:
                focused[labels==i]=255
        clean=focused
    points = cv2.findNonZero(clean)
    canvas = np.full((size, size), 255, np.uint8)
    if points is None:
        return dict(gray=gray, corrected=corrected, threshold=ink,
                    cleaned=clean, cropped=clean, query=canvas)
    x, y, w, h = cv2.boundingRect(points)
    crop = clean[y:y+h, x:x+w]
    scale = (size * .82) / max(w, h)
    nw, nh = max(1, round(w*scale)), max(1, round(h*scale))
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    x, y = (size-nw)//2, (size-nh)//2
    canvas[y:y+nh, x:x+nw] = 255-resized
    return dict(gray=gray, corrected=corrected, threshold=ink,
                cleaned=clean, cropped=255-crop, query=canvas)


def normalize_sketch(image: np.ndarray, size: int = 224) -> np.ndarray:
    return sketch_stages(image, size)['query']


@dataclass
class Paper:
    quad: np.ndarray | None
    crop: np.ndarray
    ink: float
    stable: float = 0.0
    ready: bool = False


def detect_paper(frame: np.ndarray) -> Paper:
    height, width = frame.shape[:2]
    scale = min(1., 640 / width)
    small = cv2.resize(frame, None, fx=scale, fy=scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 35, 110)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
    _, white = cv2.threshold(blur, max(110, float(np.percentile(blur, 68))), 255, cv2.THRESH_BINARY)
    contours = []
    for mask in (edges, white):
        contours.extend(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
    candidates = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
        poly = cv2.approxPolyDP(contour, .022 * cv2.arcLength(contour, True), True)
        area = cv2.contourArea(poly) / gray.size
        if len(poly) != 4 or not .12 < area < .96 or not cv2.isContourConvex(poly):
            continue
        pts = poly[:, 0].astype(np.float32)
        pts = _order_quad(pts)
        lengths = np.linalg.norm(np.roll(pts, -1, axis=0)-pts, axis=1)
        if lengths.min() < 35 or lengths.max()/lengths.min() > 3:
            continue
        mask = np.zeros_like(gray)
        cv2.fillConvexPoly(mask, pts.astype(np.int32), 255)
        if cv2.mean(gray, mask=mask)[0] < 95:
            continue
        candidates.append((area, pts / scale))
    quad = max(candidates, key=lambda row: row[0])[1] if candidates else None
    if quad is None:
        quad=_color_paper_candidate(small)
        if quad is not None:
            quad=quad/scale
    if quad is not None:
        lengths = np.linalg.norm(np.roll(quad, -1, axis=0)-quad, axis=1)
        w, h = max(80, int(max(lengths[0], lengths[2]))), max(80, int(max(lengths[1], lengths[3])))
        factor = min(1, 800/max(w,h)); w,h = int(w*factor), int(h*factor)
        transform = cv2.getPerspectiveTransform(quad.astype(np.float32), np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]))
        crop = cv2.warpPerspective(frame, transform, (w,h), borderValue=(255,255,255))
    else:
        crop = frame.copy()
    sketch = normalize_sketch(crop)
    return Paper(quad, crop, float(np.mean(sketch < 160)))


class StablePaper:
    def __init__(self):
        self.previous = None
        self.signature = None
        self.progress = 0.0
        self.updated_at = None

    def update(self, paper: Paper, shape: tuple) -> Paper:
        now = time.monotonic()
        elapsed = .10 if self.updated_at is None else min(.35, max(.01, now-self.updated_at))
        self.updated_at = now
        signature = cv2.resize(normalize_sketch(paper.crop), (40,40))
        movement = 0.
        if paper.quad is not None and self.previous is not None:
            movement = float(np.mean(np.linalg.norm(paper.quad-self.previous, axis=1))) / max(shape[:2])
        difference = 1. if self.signature is None else float(np.mean(cv2.absdiff(signature,self.signature)))/255
        # Paper is an optional proposal, not a prerequisite.  For a boundaryless
        # view, signature change is the only motion estimate used by auto-capture.
        if paper.quad is None:
            movement = difference
        has_drawing = .003 < paper.ink < .48
        steady = has_drawing and movement < PAPER_MOVEMENT_SOFT and difference < PAPER_CONTENT_SOFT
        recoverable = has_drawing and movement < PAPER_MOVEMENT_HARD and difference < PAPER_CONTENT_HARD
        if steady:
            self.progress = min(PAPER_STABLE_SECONDS, self.progress+elapsed)
        elif recoverable:
            # Hand tremor or one noisy segmentation result should pause/decay
            # confidence, not restart the complete hold timer.
            self.progress = max(0., self.progress-elapsed*PAPER_UNSTABLE_DECAY)
        else:
            self.progress = max(0., self.progress-elapsed*1.5)
        paper.stable = min(1., self.progress/PAPER_STABLE_SECONDS)
        paper.ready = bool(has_drawing and paper.stable >= 1.)
        if paper.quad is not None:
            if self.previous is not None and movement < PAPER_MOVEMENT_HARD:
                motion_ratio=min(1.,movement/max(PAPER_MOVEMENT_SOFT,1e-6))
                alpha=PAPER_QUAD_SMOOTHING_MIN+(PAPER_QUAD_SMOOTHING_MAX-PAPER_QUAD_SMOOTHING_MIN)*motion_ratio
                paper.quad=self.previous+(paper.quad-self.previous)*alpha
            self.previous=paper.quad.copy()
        self.signature=signature
        return paper
