"""Three-class, image-only OpenCLIP retrieval with paper-optional ROI support."""
from __future__ import annotations

import time

import cv2
import numpy as np
from PIL import Image

from desktop.config import (
    COMPETITION_CLASSES, MAX_QUERY_REGIONS, RETRIEVAL_MIN_MARGIN,
    RETRIEVAL_MIN_SCORE, SKETCH_SHAPE_WEIGHT,
)
from desktop.paths import COMPETITION_INDEX, ENCODER, WEIGHTS
from desktop.paper import normalize_sketch
from desktop.library import read_manifest
from desktop.performance import record


def shape_feature(image: np.ndarray) -> np.ndarray:
    gray = normalize_sketch(image, 64)
    ink = (255-gray).astype(np.float32)/255
    dx = cv2.Sobel(ink, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(ink, cv2.CV_32F, 0, 1)
    mag, angle = cv2.cartToPolar(dx,dy)
    bins = np.floor(angle*8/(2*np.pi)).astype(int)%8
    histogram = []
    for y in range(0,64,16):
        for x in range(0,64,16):
            histogram.extend(np.bincount(bins[y:y+16,x:x+16].ravel(),
                                         weights=mag[y:y+16,x:x+16].ravel(), minlength=8))
    vector = np.concatenate([cv2.resize(ink,(16,16)).ravel(),
                             np.asarray(histogram)/32]).astype(np.float32)
    return vector / max(float(np.linalg.norm(vector)), 1e-8)


def _square(image: np.ndarray, size: int = 224) -> np.ndarray:
    h, w = image.shape[:2]
    scale = (size*.90)/max(h, w, 1)
    resized = cv2.resize(image, (max(1, round(w*scale)), max(1, round(h*scale))),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    shape = (size, size) if resized.ndim == 2 else (size, size, resized.shape[2])
    canvas = np.full(shape, 255, np.uint8)
    y, x = (size-resized.shape[0])//2, (size-resized.shape[1])//2
    canvas[y:y+resized.shape[0], x:x+resized.shape[1]] = resized
    return canvas


def query_representations(image: np.ndarray) -> dict[str, np.ndarray]:
    """Keep colour for photos while offering clean line and edge views for sketches."""
    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    rgb = cv2.cvtColor(_square(bgr), cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.cvtColor(_square(gray), cv2.COLOR_GRAY2RGB)
    line = normalize_sketch(bgr)
    edge = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (3,3), 0), 35, 105)
    edge = _square(255-cv2.dilate(edge, np.ones((2,2), np.uint8)))
    return {'rgb':rgb, 'grayscale':gray,
            'line':cv2.cvtColor(line,cv2.COLOR_GRAY2RGB),
            'edge':cv2.cvtColor(edge,cv2.COLOR_GRAY2RGB)}


def query_diagnostics(image: np.ndarray) -> dict:
    query=normalize_sketch(image); ink=(query<180).astype(np.uint8)*255
    ink_ratio=float(np.mean(ink>0)); components=cv2.connectedComponentsWithStats(ink)[0]-1
    contours=cv2.findContours(ink,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
    plain_circle=False; interior_ink=0.
    if contours:
        contour=max(contours,key=cv2.contourArea); area=cv2.contourArea(contour)
        perimeter=cv2.arcLength(contour,True); x,y,w,h=cv2.boundingRect(contour)
        circularity=4*np.pi*area/max(perimeter*perimeter,1)
        mask=np.zeros_like(ink); cv2.drawContours(mask,[contour],-1,255,cv2.FILLED)
        inner=cv2.erode(mask,np.ones((13,13),np.uint8))
        interior_ink=float(np.sum((ink>0)&(inner>0))/max(np.sum(inner>0),1))
        plain_circle=bool(.80<w/max(h,1)<1.22 and circularity>.74 and interior_ink<.018)
    reason=''
    if ink_ratio<.002: reason='No visible drawing'
    elif ink_ratio>.34: reason='Drawing region is too dense'
    elif components>28: reason='Input contains too many disconnected marks'
    elif plain_circle: reason='A plain circle is not enough to identify Earth'
    return dict(inkRatio=ink_ratio,components=int(components),plainCircle=plain_circle,
                interiorInk=interior_ink,rejectionReason=reason)


class VisualEncoder:
    def __init__(self, device: str = 'auto'):
        import torch
        import open_clip
        if not WEIGHTS.exists():
            raise FileNotFoundError('Local OpenCLIP weights missing. Run scripts/download_demo_models.py.')
        self.torch=torch
        self.device=('cuda' if torch.cuda.is_available() else 'cpu') if device=='auto' else device
        torch.set_num_threads(min(4,torch.get_num_threads()))
        self.model,_,self.transform=open_clip.create_model_and_transforms(
            'ViT-B-32',pretrained=str(WEIGHTS),device='cpu')
        self.model.eval(); self.visual=self.model.visual; del self.model
        try: self.visual.to(self.device)
        except torch.cuda.OutOfMemoryError:
            self.device='cpu'; self.visual.cpu(); torch.cuda.empty_cache()

    def encode(self, images: list[Image.Image], batch_size: int = 8) -> np.ndarray:
        vectors=[]
        with self.torch.inference_mode():
            for start in range(0,len(images),batch_size):
                batch=self.torch.stack([self.transform(i.convert('RGB')) for i in images[start:start+batch_size]])
                try: values=self.visual(batch.to(self.device))
                except self.torch.cuda.OutOfMemoryError:
                    self.device='cpu'; self.visual.cpu(); self.torch.cuda.empty_cache(); values=self.visual(batch)
                values=values.float(); values/=values.norm(dim=-1,keepdim=True).clamp_min(1e-8)
                vectors.append(values.cpu().numpy())
        return np.concatenate(vectors)


class Retriever:
    def __init__(self, device: str = 'auto'):
        if not COMPETITION_INDEX.exists():
            raise FileNotFoundError('No competition index. Run scripts/build_competition_index.py first.')
        with np.load(COMPETITION_INDEX,allow_pickle=False) as data:
            self.vectors=data['vectors'].copy(); self.shapes=data['shapes'].copy()
            self.ids=data['model_ids'].copy(); self.paths=data['paths'].copy()
            self.angles=data['angles'].copy(); self.kinds=data['kinds'].copy()
            self.banks=data['banks'].copy() if 'banks' in data else np.full(len(self.ids),'sketch')
            self.encoder_name=str(data['encoder'].item())
        self.models={model['id']:model for model in read_manifest()}
        expected=set(COMPETITION_CLASSES)
        if not len(self.ids) or set(self.ids)!=expected or not expected.issubset(self.models):
            raise ValueError('The three-class competition library and retrieval index differ. Rebuild the competition index.')
        self.encoder=None; self.reason=''
        try:
            if self.encoder_name!=ENCODER: raise RuntimeError('Index uses a different encoder; rebuild it.')
            self.encoder=VisualEncoder(device)
        except Exception as exc: self.reason=str(exc)
        self.mode=ENCODER if self.encoder else 'OpenCV shape fallback (lower reliability)'

    def retrieve(self, input_data) -> dict:
        started=time.perf_counter()
        if isinstance(input_data,np.ndarray):
            regions=[dict(image=input_data,kind='provided-image',score=1.,
                          rect=(0,0,input_data.shape[1],input_data.shape[0]))]
        else: regions=list(input_data)[:MAX_QUERY_REGIONS]
        if not regions: raise ValueError('No usable visual query region was found.')
        labels=[]; representations=[]; diagnostics=[]
        for region_index,region in enumerate(regions):
            diagnostics.append(query_diagnostics(region['image']))
            variants=query_representations(region['image'])
            # The primary proposal receives every representation. Secondary
            # proposals keep only the most complementary colour/line signals,
            # reducing the common CPU batch from 16 images to 6-9.
            names=tuple(variants) if region_index==0 else ('rgb','line','edge')
            if region.get('kind') in {'center-fallback','full-frame'} and region_index:
                names=('rgb','line')
            for name in names:
                pixels=variants[name]
                representations.append(Image.fromarray(pixels).convert('RGB'))
                labels.append((region_index,name,pixels))
        if all(item['rejectionReason'] for item in diagnostics):
            reasons=', '.join(dict.fromkeys(item['rejectionReason'] for item in diagnostics))
            raise ValueError('Drawing not recognized clearly — '+reasons+'.')
        query_shapes=np.asarray([shape_feature(pixels) for _,_,pixels in labels],dtype=np.float32)
        preprocess_ms=(time.perf_counter()-started)*1000; stage=time.perf_counter()
        if self.encoder:
            query_vectors=self.encoder.encode(representations); embedding_ms=(time.perf_counter()-stage)*1000
            stage=time.perf_counter(); similarities=self.vectors@query_vectors.T
        else:
            embedding_ms=0.; similarities=self.shapes@query_shapes.T; stage=time.perf_counter()
        shape_similarities=self.shapes@query_shapes.T

        def score_region(region_index: int) -> list[dict]:
            """Compare every class against the same visual region."""
            query_positions=np.asarray(
                [position for position,(index,_,_) in enumerate(labels) if index==region_index],dtype=int)
            region_candidates=[]
            for model_id in COMPETITION_CLASSES:
                bank_scores={}; best_rows={}
                for bank in ('render','sketch','prototype'):
                    subset=np.flatnonzero((self.ids==model_id)&(self.banks==bank))
                    if not len(subset):
                        continue
                    matrix=similarities[np.ix_(subset,query_positions)].copy()
                    # A small geometric contribution applies only to line-style
                    # comparisons; RGB/render matching remains pure OpenCLIP.
                    if self.encoder and bank!='render' and SKETCH_SHAPE_WEIGHT:
                        for local_pos,query_pos in enumerate(query_positions):
                            if labels[query_pos][1] in {'line','edge'}:
                                matrix[:,local_pos]=(
                                    (1-SKETCH_SHAPE_WEIGHT)*matrix[:,local_pos]
                                    +SKETCH_SHAPE_WEIGHT*shape_similarities[subset,query_pos])
                    flat_index=int(np.argmax(matrix))
                    ref_pos,local_pos=np.unravel_index(flat_index,matrix.shape)
                    flat=np.sort(matrix.ravel())
                    bank_scores[bank]=float(np.mean(flat[-min(3,len(flat)):]))
                    best_rows[bank]=(int(subset[ref_pos]),int(query_positions[local_pos]))
                if not bank_scores:
                    continue
                best_bank=max(bank_scores,key=bank_scores.get)
                ref_index,query_pos=best_rows[best_bank]
                _,variant,_=labels[query_pos]
                model=self.models[str(model_id)]
                class_rows=np.flatnonzero(self.ids==model_id)
                region_candidates.append(dict(
                    id=str(model_id),name=model['name'],source=model.get('source',''),license=model['license'],
                    semanticParts=model.get('semanticParts',False),partCount=model['partCount'],
                    score=bank_scores[best_bank],cosine=float(similarities[ref_index,query_pos]),
                    bestCosine=(float(np.max(similarities[np.ix_(class_rows,query_positions)]))
                                if self.encoder else None),
                    shape=float(np.max(shape_similarities[np.ix_(class_rows,query_positions)])),
                    bankScores=bank_scores,view=str(self.paths[ref_index]),angle=str(self.angles[ref_index]),
                    referenceKind=str(self.kinds[ref_index]),referenceBank=best_bank,
                    queryVariant=variant,queryPos=int(query_pos),roiIndex=int(region_index),
                    roiType=regions[region_index]['kind']))
            region_candidates.sort(key=lambda row:row['score'],reverse=True)
            return region_candidates

        region_results=[]
        for region_index in range(len(regions)):
            if diagnostics[region_index]['rejectionReason']:
                continue
            rows=score_region(region_index)
            if len(rows)<2:
                continue
            margin=rows[0]['score']-rows[1]['score']
            accepted=bool(self.encoder and rows[0]['score']>=RETRIEVAL_MIN_SCORE
                          and margin>=RETRIEVAL_MIN_MARGIN)
            region_results.append((region_index,rows,margin,accepted))
        for image in representations: image.close()
        if not region_results:
            raise ValueError('Competition retrieval index does not contain all three classes.')
        # Region proposals are already ordered by cheap visual quality. Use the
        # first one that clears both confidence gates; otherwise report the
        # least ambiguous region without forcing a class.
        primary_result=region_results[0]
        primary_kind=regions[primary_result[0]].get('kind','')
        if primary_kind not in {'center-fallback','full-frame'}:
            # A real page/drawing/poster proposal owns the decision. An
            # uncertain primary region must reject rather than letting scene
            # background in a fallback crop become a confident false Car.
            selected_result=primary_result
        else:
            selected_result=next((result for result in region_results if result[3]),None)
            if selected_result is None:
                selected_result=max(region_results,key=lambda result:(result[2],result[1][0]['score']))
        selected_region,candidates,margin,accepted=selected_result
        diagnostic=diagnostics[selected_region]
        search_ms=(time.perf_counter()-stage)*1000; elapsed_ms=(time.perf_counter()-started)*1000
        timings=dict(preprocessingMs=preprocess_ms,embeddingMs=embedding_ms,searchMs=search_ms,totalMs=elapsed_ms)
        device=self.encoder.device if self.encoder else 'shape-only'
        for metric,value in timings.items(): record('retrieval_'+metric,value,detail=device)
        print('QUERY RANKING',flush=True)
        for candidate in candidates:
            print(f"{candidate['name'].upper()}: banks = {candidate['bankScores']}; final score = "
                  f"{candidate['score']:.4f}; ROI = {candidate['roiType']}; query = "
                  f"{candidate['queryVariant']}; reference = {candidate['referenceBank']}/"
                  f"{candidate['referenceKind']}/{candidate['angle']}",flush=True)
        print('ACCEPTED' if accepted else 'UNCERTAIN — Drawing not recognized clearly',flush=True)
        query=labels[candidates[0]['queryPos']][2]
        for candidate in candidates:
            candidate.pop('queryPos',None)
        return dict(candidates=candidates[:3],accepted=accepted,margin=margin,query=query,
                    elapsedMs=elapsed_ms,timings=timings,device=device,encoder=self.mode,
                    fallbackReason=self.reason,selectedROI={k:v for k,v in regions[selected_region].items() if k!='image'},
                    selectedROIImage=regions[selected_region]['image'],
                    roiCandidates=[{k:v for k,v in region.items() if k!='image'} for region in regions],
                    queryDiagnostics=diagnostic)
