"""Evaluate manually collected images through the exact file-input ROI/retrieval path."""
from __future__ import annotations

import argparse,csv,json,os,statistics,sys,time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('HF_HUB_OFFLINE','1')
from desktop.paths import ROOT

CLASSES={'heart':'human_heart','car':'toy_car','earth':'earth','unknown':None,'negative':None}
FIELDS=['input','input_type','roi_selected','expected_class','top1','top1_score','top2','top2_score','margin',
        'accepted','correct','top3','preprocessing_ms','embedding_ms','search_ms','total_retrieval_ms','device','error']


def stats(values):
    return dict(samples=values,count=len(values),average=statistics.mean(values),minimum=min(values),maximum=max(values)) \
        if values else dict(samples=[],count=0,average=None,minimum=None,maximum=None)


def inferred_type(path: Path) -> str:
    for part in path.parts:
        value=part.lower()
        if value in {'basic','detailed','photo','poster','image'}:
            return 'photo' if value in {'photo','poster','image'} else value
    return 'unspecified'


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('folder',type=Path)
    parser.add_argument('--device',choices=['cpu','auto','cuda'],default='cpu')
    parser.add_argument('--output',type=Path,default=ROOT/'evaluation'); args=parser.parse_args()
    folder=args.folder.resolve(); suffixes={'.png','.jpg','.jpeg','.bmp','.webp'}
    files=[(name,file) for name in CLASSES for file in sorted((folder/name).rglob('*'))
           if file.is_file() and file.suffix.lower() in suffixes]
    args.output.mkdir(parents=True,exist_ok=True); rows=[]
    summary=dict(status='Awaiting manually collected sketches.',input_folder=str(folder),image_count=len(files),
                 evaluated_count=0,accuracy=None,requested_device=args.device,timing_units='milliseconds',timings={},errors=[])
    if files:
        import cv2,numpy as np
        from desktop.encoder import Retriever
        from desktop.paper import detect_paper
        from desktop.query_regions import detect_query_regions
        started=time.perf_counter(); retriever=Retriever(args.device)
        summary.update(encoder=retriever.mode,encoder_load_ms=(time.perf_counter()-started)*1000,
                       reference_embeddings=len(retriever.ids),embedding_dimension=int(retriever.vectors.shape[1]),
                       bank_counts={bank:int(np.sum(retriever.banks==bank)) for bank in np.unique(retriever.banks)},
                       fallback_reason=retriever.reason)
        if not retriever.encoder:
            summary['status']='OpenCLIP unavailable; no accuracy evaluation performed.'; summary['errors'].append(retriever.reason)
        else:
            for expected,path in files:
                row=dict.fromkeys(FIELDS,''); row.update(input=str(path.relative_to(folder)),input_type=inferred_type(path),expected_class=expected)
                try:
                    image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
                    if image is None: raise ValueError('Cannot decode image')
                    started=time.perf_counter(); paper=detect_paper(image); regions=detect_query_regions(image,paper)
                    roi_ms=(time.perf_counter()-started)*1000; result=retriever.retrieve([region.payload() for region in regions])
                    total=(time.perf_counter()-started)*1000; top=result['candidates']; expected_id=CLASSES[expected]
                    correct=(not result['accepted']) if expected_id is None else (result['accepted'] and top[0]['id']==expected_id)
                    row.update(roi_selected=result['selectedROI']['kind'],top1=top[0]['id'],top1_score=top[0]['score'],
                               top2=top[1]['id'],top2_score=top[1]['score'],margin=result['margin'],accepted=result['accepted'],
                               correct=correct,top3=json.dumps([{'id':c['id'],'score':c['score']} for c in top]),
                               preprocessing_ms=roi_ms+result['timings']['preprocessingMs'],embedding_ms=result['timings']['embeddingMs'],
                               search_ms=result['timings']['searchMs'],total_retrieval_ms=total,device=result['device'])
                except Exception as exc:
                    # A deliberate pre-embedding rejection is correct for a negative input.
                    if CLASSES[expected] is None and 'not recognized clearly' in str(exc):
                        row.update(roi_selected='rejected by input checks',accepted=False,correct=True,total_retrieval_ms=(time.perf_counter()-started)*1000)
                    else:
                        row['error']=str(exc); summary['errors'].append({'input':row['input'],'error':str(exc)})
                rows.append(row); print(json.dumps(row),flush=True)
            valid=[row for row in rows if not row['error']]
            summary.update(status='Evaluation completed' if not summary['errors'] else 'Evaluation completed with errors',
                           evaluated_count=len(valid),accuracy=sum(bool(r['correct']) for r in valid)/len(valid) if valid else None,
                           failed_count=len(rows)-len(valid))
            summary['timings']={field:stats([float(r[field]) for r in valid if r[field]!='']) for field in
                                ['preprocessing_ms','embedding_ms','search_ms','total_retrieval_ms']}
            summary['by_input_type']={kind:{'count':sum(r['input_type']==kind for r in valid),
                                                   'correct':sum(r['input_type']==kind and bool(r['correct']) for r in valid)}
                                      for kind in ('basic','detailed','photo','unspecified')}
    with (args.output/'retrieval_results.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    (args.output/'retrieval_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(summary['status']); return 1 if summary['errors'] else 0


if __name__=='__main__': raise SystemExit(main())
