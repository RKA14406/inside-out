"""Build balanced render, sketch, and real-prototype banks for the three-class demo."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from PIL import Image

from desktop.config import COMPETITION_CLASSES
from desktop.encoder import VisualEncoder,query_representations,shape_feature
from desktop.library import read_manifest
from desktop.paths import ASSETS,COMPETITION_INDEX,ENCODER,ROOT,local,relative


def sketch_references(image: np.ndarray) -> dict[str,np.ndarray]:
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY); background=gray>=248
    grayscale=gray.copy(); grayscale[background]=255
    edges=cv2.dilate(cv2.Canny(gray,32,96),np.ones((2,2),np.uint8)); edge=255-edges
    local_mean=cv2.GaussianBlur(gray,(0,0),5)
    lines=((gray.astype(np.int16)<local_mean.astype(np.int16)-7)&~background).astype(np.uint8)*255
    lines=cv2.morphologyEx(lines,cv2.MORPH_OPEN,np.ones((2,2),np.uint8)); line=255-cv2.dilate(lines,np.ones((2,2),np.uint8))
    foreground=(gray<247).astype(np.uint8)*255
    foreground=cv2.morphologyEx(foreground,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    contours=cv2.findContours(foreground,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
    silhouette=np.full_like(gray,255)
    if contours: cv2.drawContours(silhouette,contours,-1,0,thickness=cv2.FILLED)
    return {'grayscale':grayscale,'edge':edge,'line':line,'silhouette':silhouette}


def semantic_sketches(model_id: str) -> list[tuple[str,np.ndarray]]:
    """Small varied prototype set for supported symbols; never evaluation data."""
    def blank():
        return np.full((224,224),255,np.uint8)

    result=[]; blue=0
    if model_id=='human_heart':
        canvas=blank()
        t=np.linspace(0,2*np.pi,240)
        x=16*np.sin(t)**3; y=13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t)
        points=np.column_stack([112+x*4.3,110-y*4.3]).astype(np.int32)
        cv2.polylines(canvas,[points],True,blue,4,cv2.LINE_AA)
        result.append(('symbolic-heart',canvas))
    elif model_id=='toy_car':
        canvas=blank()
        body=np.array([[32,137],[43,105],[73,99],[92,72],[145,72],[169,99],[190,108],[195,137]],np.int32)
        cv2.polylines(canvas,[body],False,blue,5,cv2.LINE_AA); cv2.line(canvas,(32,137),(195,137),blue,5,cv2.LINE_AA)
        cv2.circle(canvas,(70,139),23,blue,5,cv2.LINE_AA); cv2.circle(canvas,(162,139),23,blue,5,cv2.LINE_AA)
        cv2.line(canvas,(96,75),(96,100),blue,4,cv2.LINE_AA); cv2.line(canvas,(145,74),(145,100),blue,4,cv2.LINE_AA)
        result.append(('sedan',canvas))

        # Child-like side view: body, trapezoid roof, and two explicit wheels.
        canvas=blank()
        cv2.rectangle(canvas,(35,105),(190,145),blue,5,cv2.LINE_AA)
        roof=np.array([[73,105],[96,76],[149,76],[174,105]],np.int32)
        cv2.polylines(canvas,[roof],False,blue,5,cv2.LINE_AA)
        cv2.circle(canvas,(72,145),20,blue,5,cv2.LINE_AA); cv2.circle(canvas,(161,145),20,blue,5,cv2.LINE_AA)
        result.append(('boxy-side-view',canvas))

        # Compact rounded profile tolerates a single arched roof stroke.
        canvas=blank()
        profile=np.array([[31,139],[39,112],[72,105],[91,82],[137,75],[168,104],[193,115],[196,139]],np.int32)
        cv2.polylines(canvas,[profile],False,blue,5,cv2.LINE_AA); cv2.line(canvas,(31,139),(196,139),blue,5,cv2.LINE_AA)
        cv2.circle(canvas,(69,140),20,blue,5,cv2.LINE_AA); cv2.circle(canvas,(164,140),20,blue,5,cv2.LINE_AA)
        result.append(('rounded-side-view',canvas))
    else:
        canvas=blank()
        cv2.circle(canvas,(112,112),78,blue,5,cv2.LINE_AA)
        africa=np.array([[108,58],[129,68],[136,87],[124,101],[130,119],[116,151],[102,133],[95,105],[78,91],[89,72]],np.int32)
        americas=np.array([[66,62],[83,68],[88,84],[78,96],[84,111],[75,136],[62,119],[58,93]],np.int32)
        cv2.polylines(canvas,[africa,americas],True,blue,4,cv2.LINE_AA)
        result.append(('two-continents',canvas))

        # Rough land blobs model the supported classroom drawing without
        # teaching that an undecorated circle means Earth.
        canvas=blank(); cv2.circle(canvas,(112,112),78,blue,5,cv2.LINE_AA)
        patches=[np.array([[72,65],[92,58],[104,74],[96,91],[78,96],[65,82]],np.int32),
                 np.array([[119,70],[145,77],[153,96],[137,106],[129,130],[112,119],[104,92]],np.int32),
                 np.array([[72,116],[92,126],[97,149],[82,160],[65,143]],np.int32)]
        for patch in patches: cv2.polylines(canvas,[patch],True,blue,4,cv2.LINE_AA)
        result.append(('rough-land-blobs',canvas))

        canvas=blank(); cv2.ellipse(canvas,(112,112),(80,73),0,0,360,blue,5,cv2.LINE_AA)
        patches=[np.array([[59,84],[78,68],[94,75],[91,96],[76,108],[62,100]],np.int32),
                 np.array([[116,60],[139,70],[153,92],[143,110],[151,128],[133,154],[116,137],[109,112],[98,95]],np.int32)]
        for patch in patches: cv2.polylines(canvas,[patch],True,blue,4,cv2.LINE_AA)
        result.append(('elliptical-globe',canvas))
    return result


def mild_variants(image: np.ndarray) -> list[tuple[str,np.ndarray]]:
    result=[]
    for angle in (-5,0,5):
        matrix=cv2.getRotationMatrix2D((image.shape[1]/2,image.shape[0]/2),angle,1.)
        result.append((f'rotation {angle:+d}',cv2.warpAffine(image,matrix,(image.shape[1],image.shape[0]),borderValue=(255,255,255))))
    return result


def main() -> None:
    models={model['id']:model for model in read_manifest()}
    missing=[model_id for model_id in COMPETITION_CLASSES if model_id not in models]
    if missing: raise ValueError('Missing competition models: '+', '.join(missing))
    encoder=VisualEncoder(); vectors=[]; shapes=[]; ids=[]; paths=[]; angles=[]; kinds=[]; banks=[]
    output_root=ASSETS/'competition_previews'; calibration=ROOT/'evaluation'/'competition_sketches'

    def add(model_id,bank,kind,angle,pixels,target):
        target.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(target),pixels)
        images.append(Image.fromarray(pixels).convert('RGB'))
        rows.append((model_id,bank,kind,angle,relative(target),pixels))

    images=[]; rows=[]
    for model_id in COMPETITION_CLASSES:
        model=models[model_id]; shaded=[v for v in model.get('previewImages',[]) if v.get('kind')=='shaded']
        if len(shaded)!=12: raise ValueError(f'{model["name"]} needs 12 shaded views; found {len(shaded)}')
        folder=output_root/model_id
        for view_index,view in enumerate(shaded):
            source=cv2.imread(str(local(view['path'])),cv2.IMREAD_COLOR)
            if source is None: raise ValueError('Unreadable render: '+view['path'])
            add(model_id,'render','rgb render',view['angle'],source,folder/f'{view_index:02d}-render.png')
            for kind,pixels in sketch_references(source).items():
                add(model_id,'sketch',kind,view['angle'],pixels,folder/f'{view_index:02d}-{kind}.png')
        for symbol_name,symbol in semantic_sketches(model_id):
            for label,pixels in mild_variants(symbol):
                suffix=label[-2:].replace('+','p').replace('-','m')
                add(model_id,'sketch',f'supported simple symbol: {symbol_name}',label,pixels,
                    folder/f'symbol-{symbol_name}-{suffix}.png')
        class_folder=calibration/{'human_heart':'heart','toy_car':'car','earth':'earth'}[model_id]
        prototype_files=[] if not class_folder.exists() else [p for p in class_folder.rglob('*') if p.suffix.lower() in {'.png','.jpg','.jpeg','.bmp','.webp'}]
        for prototype_index,path in enumerate(sorted(prototype_files)):
            source=cv2.imread(str(path),cv2.IMREAD_COLOR)
            if source is None: continue
            for augment_name,augmented in mild_variants(source):
                for representation_name,pixels in query_representations(augmented).items():
                    target=folder/f'prototype-{prototype_index:02d}-{augment_name[-2:].replace("+","p").replace("-","m")}-{representation_name}.png'
                    add(model_id,'prototype',f'real sketch {representation_name}',augment_name,pixels,target)
        print(f'Prepared {model["name"]}: {sum(row[0]==model_id for row in rows)} references',flush=True)
    encoded=encoder.encode(images)
    for vector,(model_id,bank,kind,angle,path,pixels) in zip(encoded,rows):
        vectors.append(vector); shapes.append(shape_feature(pixels)); ids.append(model_id)
        paths.append(path); angles.append(angle); kinds.append(kind); banks.append(bank)
    for image in images: image.close()
    COMPETITION_INDEX.parent.mkdir(parents=True,exist_ok=True)
    temporary=COMPETITION_INDEX.with_suffix('.partial.npz')
    np.savez_compressed(temporary,vectors=np.asarray(vectors,dtype=np.float32),shapes=np.asarray(shapes,dtype=np.float32),
                        model_ids=np.asarray(ids),paths=np.asarray(paths),angles=np.asarray(angles),kinds=np.asarray(kinds),
                        banks=np.asarray(banks),encoder=np.asarray(ENCODER),competition_classes=np.asarray(COMPETITION_CLASSES))
    temporary.replace(COMPETITION_INDEX)
    print(f'Saved {len(ids)} competition references to {COMPETITION_INDEX}',flush=True)


if __name__=='__main__': main()
