"""Evaluate old and three-class retrieval on manually collected paper sketches."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from PIL import Image

from desktop.encoder import Retriever, shape_feature
from desktop.paper import normalize_sketch
from desktop.paths import INDEX


LABELS={'heart':'human_heart','car':'toy_car','earth':'earth','unknown':None}
EXTENSIONS={'.png','.jpg','.jpeg','.bmp','.webp'}


def legacy_normalize(image,size=224):
    """Exact pre-fix query path, retained only for before/after measurement."""
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image.copy()
    h,w=gray.shape; gray=gray[int(h*.025):max(int(h*.975),1),int(w*.025):max(int(w*.975),1)]
    gray=cv2.GaussianBlur(gray,(3,3),0)
    background=cv2.GaussianBlur(gray,(0,0),18)
    corrected=cv2.divide(gray,np.maximum(background,1),scale=245)
    _,ink=cv2.threshold(corrected,205,255,cv2.THRESH_BINARY_INV)
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink)
    clean=np.zeros_like(ink)
    for i in range(1,count):
        x,y,bw,bh,area=stats[i]
        touches=x==0 or y==0 or x+bw>=ink.shape[1] or y+bh>=ink.shape[0]
        if area>=max(4,ink.size*.000015) and not (touches and (bw>ink.shape[1]*.9 or bh>ink.shape[0]*.9)):
            clean[labels==i]=255
    points=cv2.findNonZero(clean); canvas=np.full((size,size),255,np.uint8)
    if points is None: return canvas
    x,y,w,h=cv2.boundingRect(points); crop=clean[y:y+h,x:x+w]
    scale=(size*.82)/max(w,h); nw,nh=max(1,round(w*scale)),max(1,round(h*scale))
    resized=cv2.resize(crop,(nw,nh),interpolation=cv2.INTER_AREA); x,y=(size-nw)//2,(size-nh)//2
    canvas[y:y+nh,x:x+nw]=255-resized
    return canvas


def legacy_shape_feature(image):
    gray=legacy_normalize(image,64); ink=(255-gray).astype(np.float32)/255
    dx=cv2.Sobel(ink,cv2.CV_32F,1,0); dy=cv2.Sobel(ink,cv2.CV_32F,0,1)
    mag,angle=cv2.cartToPolar(dx,dy); bins=np.floor(angle*8/(2*np.pi)).astype(int)%8
    histogram=[]
    for y in range(0,64,16):
        for x in range(0,64,16):
            histogram.extend(np.bincount(bins[y:y+16,x:x+16].ravel(),weights=mag[y:y+16,x:x+16].ravel(),minlength=8))
    vector=np.concatenate([cv2.resize(ink,(16,16)).ravel(),np.asarray(histogram)/32]).astype(np.float32)
    return vector/max(float(np.linalg.norm(vector)),1e-8)


def bank_scores(index,encoder,query,shape_vector,model_ids):
    base=Image.fromarray(query).convert('RGB')
    variants=[base,base.rotate(-8,fillcolor='white'),base.rotate(8,fillcolor='white'),
              base.transpose(Image.Transpose.FLIP_LEFT_RIGHT)]
    vectors=encoder.encode(variants)
    clip=(index['vectors']@vectors.T).max(1)
    shape=index['shapes']@shape_vector
    ranking=.92*clip+.08*shape
    scores={}
    for model_id in model_ids:
        subset=np.flatnonzero(index['model_ids']==model_id)
        top=np.sort(ranking[subset])[-3:]
        scores[model_id]=float(.8*top[-1]+.2*top.mean())
    return scores


def old_scores(index,encoder,image):
    query=legacy_normalize(image)
    scores=bank_scores(index,encoder,query,legacy_shape_feature(query),('human_heart','toy_car'))
    scores['earth']=None
    return scores


def old_bank_new_preprocessing(index,encoder,image):
    query=normalize_sketch(image)
    return bank_scores(index,encoder,query,shape_feature(query),('human_heart','toy_car'))


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'evaluation/competition_sketches').resolve()
    files=[]
    for label in LABELS:
        folder=root/label
        if folder.exists():
            files.extend((label,path) for path in sorted(folder.iterdir()) if path.suffix.lower() in EXTENSIONS)
    if not files:
        print('Awaiting manually collected sketches.')
        return 2
    retriever=Retriever()
    with np.load(INDEX,allow_pickle=False) as data:
        legacy={key:data[key].copy() for key in ('vectors','shapes','model_ids')}
    rows=[]
    for label,path in files:
        image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:
            print(f'SKIP unreadable: {path}')
            continue
        old=old_scores(legacy,retriever.encoder,image)
        old_bank_clean=old_bank_new_preprocessing(legacy,retriever.encoder,image)
        new=retriever.retrieve(image)
        by_id={candidate['id']:candidate for candidate in new['candidates']}
        expected=LABELS[label]
        top=new['candidates'][0]
        row=dict(
            file=str(path),expected=expected or 'reject',top1=top['id'],accepted=new['accepted'],
            correct=(not new['accepted']) if expected is None else (new['accepted'] and top['id']==expected),
            margin=new['margin'],oldHeart=old['human_heart'],oldCar=old['toy_car'],oldEarth=None,
            oldBankNewPreHeart=old_bank_clean['human_heart'],oldBankNewPreCar=old_bank_clean['toy_car'],
            newHeart=by_id['human_heart']['score'],newCar=by_id['toy_car']['score'],newEarth=by_id['earth']['score'],
            heartCosine=by_id['human_heart']['bestCosine'],carCosine=by_id['toy_car']['bestCosine'],
            earthCosine=by_id['earth']['bestCosine'],bestQueryVariant=top['queryVariant'],
            bestReferenceKind=top['referenceKind'],preprocessingMs=new['timings']['preprocessingMs'],
            embeddingMs=new['timings']['embeddingMs'],searchMs=new['timings']['searchMs'],totalMs=new['timings']['totalMs'],
        )
        rows.append(row)
        print(f"QUERY: {label} / {path.name}")
        print(f"OLD  HEART={old['human_heart']:.4f} CAR={old['toy_car']:.4f} EARTH=N/A (class did not exist)")
        print(f"OLD BANK + NEW PREPROCESSING  HEART={old_bank_clean['human_heart']:.4f} CAR={old_bank_clean['toy_car']:.4f}")
        for model_id in ('human_heart','toy_car','earth'):
            candidate=by_id[model_id]
            print(f"NEW  {model_id.upper()}: best cosine={candidate['bestCosine']:.4f}; final score={candidate['score']:.4f}; "
                  f"variant={candidate['queryVariant']}; reference={candidate['referenceKind']}")
        print('ACCEPTED' if new['accepted'] else 'UNCERTAIN')
    output=Path('evaluation')
    output.mkdir(exist_ok=True)
    csv_path=output/'competition_retrieval_results.csv'
    with csv_path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary=dict(samples=len(rows),correct=sum(bool(row['correct']) for row in rows),
                 accuracy=sum(bool(row['correct']) for row in rows)/len(rows),
                 note='Earth old score is unavailable because Earth was not in the old index.')
    (output/'competition_retrieval_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
