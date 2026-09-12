"""Exercise the existing native application and save measured runtime evidence.

These are software integration checks, not physical hand-gesture success trials.
Reference render smoke inputs are explicitly not a held-out sketch evaluation.
"""
from __future__ import annotations

import argparse
import copy
import csv
import importlib.metadata
import json
import os
import platform
import statistics
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--device',choices=['cpu','auto'],default='cpu')
parser.add_argument('--output',type=Path,default=ROOT/'evaluation'/'runtime')
parser.add_argument('--camera',type=int,default=None,help='Sample actual camera input for 12 seconds')
parser.add_argument('--quick',action='store_true',help='Rerun failure and mouse checks on the heart only')
parser.add_argument('--retrieval-only',action='store_true',help='Measure the native file/retrieval pipeline without repeating model-part checks')
parser.add_argument('--framing-only',action='store_true',help='Check actual projected geometry stays inside the viewport')
parser.add_argument('--models',nargs='+',help='Validate only the named model IDs')
parser.add_argument('--model-only',action='store_true',help='Skip mouse, failure, retrieval, and camera checks')
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
os.environ['INSIDEOUT_PERF_FILE']=str(args.output/'performance_samples.csv')
os.environ['INSIDEOUT_START_PERF']=str(time.perf_counter())
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')

import cv2
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
from PySide6.QtCore import QTimer,QEventLoop,Qt,QPoint,QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QDialog,QPushButton
from desktop.window import InsideOutWindow
from desktop.paths import local,INDEX,COMPETITION_INDEX,WEIGHTS
from desktop.gestures import GestureFrame,Hand
from desktop.performance import flush,record

report=dict(kind='native runtime integration',device=args.device,started=time.strftime('%Y-%m-%dT%H:%M:%S'),
            checks=[],models=[],exceptions=[],reference_smoke=[],camera=None,
            physical_gesture_attempts=0,manual_sketch_status='Awaiting manually collected sketches.')
app=QApplication([])
app.setApplicationName('InsideOut')
window=InsideOutWindow(device=args.device,start_camera=False)
window.show()


def exception_hook(kind,value,tb):
    message=''.join(traceback.format_exception(kind,value,tb))
    report['exceptions'].append(message); print(message,flush=True)


sys.excepthook=exception_hook


def wait(milliseconds):
    loop=QEventLoop(); QTimer.singleShot(milliseconds,loop.quit); loop.exec()


def check(name,passed,details=None):
    item=dict(name=name,passed=bool(passed),details=details)
    report['checks'].append(item)
    print(('PASS ' if passed else 'FAIL ')+name+((': '+str(details)) if not passed else ''),flush=True)
    return bool(passed)


def snapshot(name):
    scene=window.scene; scene.window.Render()
    capture=vtk.vtkWindowToImageFilter(); capture.SetInput(scene.window)
    capture.SetInputBufferTypeToRGB(); capture.ReadFrontBufferOff(); capture.Update()
    raw=capture.GetOutput(); width,height,_=raw.GetDimensions()
    rgb=np.flipud(vtk_to_numpy(raw.GetPointData().GetScalars()).reshape(height,width,3)).copy()
    destination=ROOT/'docs'/'evidence'/name; destination.parent.mkdir(parents=True,exist_ok=True)
    cv2.imwrite(str(destination),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    return dict(path=str(destination.relative_to(ROOT)),width=width,height=height,nonuniform=bool(np.std(rgb)>2))


def project(point):
    renderer=window.scene.renderer
    renderer.SetWorldPoint(*point,1.); renderer.WorldToDisplay()
    return renderer.GetDisplayPoint()[:2]


def find_pick(key):
    state=window.scene.parts[key]
    poly=state.actor.GetMapper().GetInput(); matrix=state.actor.GetMatrix()
    for index in np.linspace(0,poly.GetNumberOfCells()-1,min(60,poly.GetNumberOfCells()),dtype=int):
        cell=poly.GetCell(int(index))
        center=np.mean([poly.GetPoint(cell.GetPointId(i)) for i in range(cell.GetNumberOfPoints())],axis=0)
        point=matrix.MultiplyPoint((*center,1.))[:3]
        x,y=project(point)
        if window.scene.pick(x,y)==key:
            return float(x),float(y)
    return None


def validate_model(model):
    scene=window.scene; key=model['id']
    print('MODEL '+key,flush=True)
    for _ in range(3):
        window.open_model(key); wait(80)
    wait(2100)
    count=len(scene.parts)
    record_=dict(id=key,name=model['name'],runtime_meshes=count,source=model['source'],license=model['license'],
                 geometry_split=model.get('geometrySplit'),semantic_parts=model.get('semanticParts'),
                 names=[s.spec['name'] for s in scene.parts.values()],
                 triangles=sum(s.actor.GetMapper().GetInput().GetNumberOfCells() for s in scene.parts.values()))
    report['models'].append(record_)
    record_['loads']=check(key+' loads and renders',scene.model['id']==key and count==model['partCount'] and count>0)
    record_['complete']=snapshot(key+'-complete.png')
    scene.set_level(model['hierarchyDepth']); window.level.setValue(model['hierarchyDepth'])
    window.explode.setValue(100); wait(1300)
    moved=sum(np.linalg.norm(s.position-np.asarray(s.spec['center']))>.01 for s in scene.parts.values())
    record_['exploded']=check(key+' explode',scene.explosion>.98 and moved>0,{'moved':moved,'total':count})
    record_['exploded_evidence']=snapshot(key+'-exploded.png')
    window.reset(); wait(1100)
    ray_hits=[]; independent=[]; isolated=[]
    for part_id,state_ in list(scene.parts.items()):
        scene.select(part_id); scene.isolate(); wait(360)
        visible=[pid for pid,s in scene.parts.items() if s.actor.GetVisibility()]
        isolated.append(visible==[part_id])
        hit=find_pick(part_id)
        if hit:
            ray_hits.append(part_id)
        x,y=hit or project(state_.position)
        before={pid:s.position.copy() for pid,s in scene.parts.items()}
        scene.begin_grab(part_id,x,y,.2,0.); scene.move_grab(x+80,y+40,.24,.35); wait(180)
        changed=np.linalg.norm(state_.position-before[part_id])>.01 and state_.spin.magnitude()>.1
        others=all(np.allclose(s.position,before[pid],atol=.002) for pid,s in scene.parts.items() if pid!=part_id)
        independent.append(changed and others)
        scene.end_grab(); window.reset(); wait(350)
        if len(independent)%10==0:
            print(f'  {key}: inspected {len(independent)}/{count} runtime parts',flush=True)
    record_['raycast_selectable']=len(ray_hits)
    record_['independent_manipulation']=check(key+' every mesh moves/rotates independently',all(independent),{'passed':sum(independent),'total':count})
    record_['raycast']=check(key+' every isolated mesh raycasts',len(ray_hits)==count,{'hit':len(ray_hits),'total':count})
    record_['isolation']=check(key+' every component isolates',all(isolated))
    first=max(scene.parts,key=lambda p:scene.parts[p].spec['radius'])
    scene.select(first); scene.isolate(); wait(700)
    record_['isolated_evidence']=snapshot(key+'-isolated.png')
    scene.hide_selected(); hidden=not scene.parts[first].actor.GetVisibility()
    scene.hide_selected(); check(key+' hide/show',hidden and bool(scene.parts[first].actor.GetVisibility()))
    window.reset(); wait(1000)
    good=scene.explosion<.01 and all(np.allclose(s.position,s.spec['center'],atol=.01) and s.spin.magnitude()<.001
                                   and bool(s.actor.GetVisibility()) for s in scene.parts.values())
    record_['reset']=check(key+' reset restores assembly',good)


def validate_mouse():
    scene=window.scene; widget=scene.vtk
    position=np.asarray(scene.camera.GetPosition()); center=QPoint(widget.width()//2,widget.height()//2)
    QTest.mousePress(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,center)
    QTest.mouseMove(widget,center+QPoint(90,35),100)
    QTest.mouseRelease(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,center+QPoint(90,35))
    wait(300)
    check('mouse drag rotates camera',not np.allclose(position,scene.camera.GetPosition()))
    scale=scene.camera.GetParallelScale()
    wheel=QWheelEvent(QPointF(center),QPointF(widget.mapToGlobal(center)),QPoint(),QPoint(0,120),
                      Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(widget,wheel); wait(350)
    check('mouse wheel zoom persists',abs(scene.camera.GetParallelScale()-scale)>.01)
    part=max(scene.parts,key=lambda p:scene.parts[p].spec['radius'])
    scene.select(part); scene.isolate(); wait(800); hit=find_pick(part)
    if hit:
        rw,rh=scene.window.GetSize(); x,y=hit
        origin=QPoint(round(x*widget.width()/rw),round((rh-y)*widget.height()/rh))
        before=scene.parts[part].position.copy()
        QTest.mousePress(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ShiftModifier,origin)
        held=scene.grab is not None
        QTest.mouseMove(widget,origin+QPoint(95,35),100); wait(250)
        QTest.mouseRelease(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ShiftModifier,origin+QPoint(95,35))
        wait(250)
        check('shift mouse drag moves part',held and np.linalg.norm(scene.parts[part].position-before)>.02)
        check('mouse release clears grab',scene.grab is None and not scene.mouse_grab)
    else:
        check('shift mouse drag moves part',False,'No raycast target')
    window.reset(); wait(600)
    part=next(iter(scene.parts)); x,y=project(scene.parts[part].position)
    scene.begin_grab(part,x,y,.2,0.); scene.move_grab(x,y,.2,.7); wait(200)
    scene.end_grab()
    check('component rotation survives release without translation',scene.parts[part].spin.magnitude()>.08,
          {'radians':scene.parts[part].spin.magnitude(),'per_update_clamp':True})
    window.reset(); wait(300)


def validate_framing():
    scene=window.scene
    for model in window.models.values():
        window.open_model(model['id']); wait(2300)
        scene.set_level(model['hierarchyDepth']); scene.set_explosion(1); wait(1500)
        coords=[]
        for state_ in scene.parts.values():
            bounds=state_.actor.GetBounds()
            for x in bounds[:2]:
                for y in bounds[2:4]:
                    for z in bounds[4:]:
                        coords.append(project((x,y,z)))
        extent=np.asarray(coords); width,height=scene.window.GetSize()
        visible=extent[:,0].min()>=0 and extent[:,0].max()<=width and extent[:,1].min()>=0 and extent[:,1].max()<=height
        check(model['id']+' full explosion stays in frame',visible,dict(minimum=extent.min(0).tolist(),maximum=extent.max(0).tolist(),viewport=[width,height],scale=scene.camera.GetParallelScale()))
        snapshot(model['id']+'-exploded.png')
        scene.reset(); wait(600)


def validate_failures():
    from desktop.encoder import Retriever
    from desktop.retrieval_worker import RetrievalWorker
    scene=window.scene
    key=next(iter(scene.parts)); scene.begin_grab(key,200,200,.2,0)
    window.interactions.owner='Left'; window.interactions.pinching=True; window.interactions.last_seen=0
    window.interactions.update(GestureFrame(timestamp=time.monotonic()))
    check('hand loss releases active drag (state replay)',scene.grab is None and window.interactions.owner is None)
    window.interactions.update(GestureFrame(timestamp=time.monotonic()))
    check('empty tracking frame does not crash',scene.model is not None)
    pose=Hand('Left',np.zeros((21,3)),None,.5,.5,.2,1.,False,False,False,0.)
    before=(scene.explosion_target,scene.selected)
    window.interactions.update(GestureFrame(hands=[pose],timestamp=time.monotonic(),label='Hand detected'))
    check('unsupported gesture state does not manipulate model (state replay)',scene.grab is None and before==(scene.explosion_target,scene.selected))
    window.interactions.release()
    class StoppingCamera:
        def isRunning(self): return True
        def requestInterruption(self): pass
    actual_worker=window.camera_worker; window.camera_worker=StoppingCamera(); window.camera_index=0
    window.pending_camera_index=None; opened=[]
    try:
        with patch.object(window,'start_camera',side_effect=lambda:opened.append(window.camera_choice.currentData())):
            window.camera_choice.setCurrentIndex(1); window.camera_choice.setCurrentIndex(0)
            window.camera_finished()
        check('rapid camera 0 to 1 to 0 keeps last choice (state replay)',opened==[0],opened)
    finally:
        window.camera_worker=actual_worker; window.pending_camera_index=None
        window.camera_choice.setCurrentIndex(0)
    original=copy.deepcopy(window.models['human_heart']); old_id=scene.model['id']; old_parts=set(scene.parts)
    broken=copy.deepcopy(original); broken['components'][0]['file']='assets/desktop/missing-for-validation.npz'
    window.models['human_heart']=broken
    try:
        window.open_model('human_heart'); wait(200)
        check('missing model status visible','Could not load model' in window.statusBar().currentMessage())
        check('missing model preserves previous usable scene',scene.model['id']==old_id and set(scene.parts)==old_parts)
    finally:
        window.models['human_heart']=original
    window.open_model('human_heart'); wait(2200)
    with tempfile.TemporaryDirectory(prefix='insideout-validation-') as temporary:
        empty=Path(temporary)/'empty.png'; empty.touch()
        for name,path_ in [('malformed text image',ROOT/'README.md'),('zero-byte image',empty),('missing image',Path(temporary)/'missing.png')]:
            error=None
            try:
                with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path_),'')):
                    window.open_drawing()
            except Exception as exc:
                error=repr(exc)
            check(name+' handled',error is None and 'Cannot' in window.statusBar().currentMessage(),error or window.statusBar().currentMessage())
    worker=RetrievalWorker('cpu'); failures=[]; worker.error.connect(lambda token,message:failures.append((token,message)))
    worker.error.connect(window.on_retrieval_error)
    with patch('desktop.encoder.COMPETITION_INDEX',ROOT/'data'/'model_index'/'missing-for-validation.npz'):
        worker.start()
        while worker.isRunning():
            wait(30)
        wait(60)
    check('missing embeddings has visible error',bool(failures) and 'index' in window.statusBar().currentMessage().lower(),failures)
    window.submit(cv2.imread(str(local(original['previewImages'][1]['path']))))
    check('missing embeddings error survives capture retry',not window.busy and 'index' in window.statusBar().currentMessage().lower())
    window.open_model('human_heart'); wait(250)
    check('direct library model remains available without embeddings',scene.model['id']=='human_heart' and len(scene.parts)==14)
    window.on_encoder_ready('ViT-B-32/laion2b_s34b_b79k')
    # No actual CUDA or model files are removed; availability is injected only in this process.
    import torch
    with patch.object(torch.cuda,'is_available',return_value=False):
        retriever=Retriever('auto')
        check('CUDA unavailable selects CPU encoder',retriever.encoder is not None and retriever.encoder.device=='cpu')
    with patch('desktop.encoder.WEIGHTS',ROOT/'data'/'weights'/'missing-for-validation.safetensors'):
        fallback=Retriever('cpu')
        image=cv2.imread(str(local(window.models['human_heart']['previewImages'][1]['path'])))
        result=fallback.retrieve(image)
        check('missing weights exposes shape fallback and requires confirmation',fallback.encoder is None and not result['accepted'] and bool(result['fallbackReason']))


def validate_camera_failures():
    from desktop.camera import CameraWorker
    active=window.camera_worker
    if active and active.isRunning():
        active.requestInterruption()
        while active.isRunning():
            wait(30)
        wait(80)
    notices=[]
    unavailable=CameraWorker(99)
    unavailable.notice.connect(notices.append); unavailable.notice.connect(window.camera_notice)
    unavailable.start()
    deadline=time.perf_counter()+20
    while unavailable.isRunning() and time.perf_counter()<deadline:
        wait(30)
    unavailable.requestInterruption(); unavailable.wait(5000); wait(100)
    check('unavailable camera exits with visible file/library fallback',not unavailable.isRunning() and any('Camera unavailable' in s for s in notices),notices)
    window.on_encoder_ready(window.encoder_name)
    check('encoder ready does not erase camera failure message','Camera unavailable' in window.statusBar().currentMessage())
    notices=[]; worker=CameraWorker(args.camera)
    worker.notice.connect(notices.append); worker.notice.connect(window.camera_notice)
    # Deliberately fail the import, without uninstalling or changing MediaPipe.
    with patch.dict(sys.modules,{'mediapipe':None}):
        worker.start(); wait(4000)
        packet=worker.take_latest()
        worker.requestInterruption(); worker.wait(5000); wait(100)
    check('MediaPipe initialization failure keeps actual camera frames available',packet is not None and any('Hand tracking unavailable' in s for s in notices),notices)
    check('MediaPipe failure supplies empty gestures for mouse fallback',packet is not None and not packet[3].hands)
    report['camera_faults']=dict(unavailable_index=99,mediapipe_failure='Injected import failure; real camera capture',notices=notices)


def validate_reference_smoke():
    from desktop.encoder import Retriever
    from desktop.paper import detect_paper
    retriever=Retriever(args.device)
    check('real OpenCLIP image encoder loaded',retriever.encoder is not None,retriever.reason)
    norms=np.linalg.norm(retriever.vectors,axis=1)
    report['index']=dict(encoder=retriever.encoder_name,dimension=int(retriever.vectors.shape[1]),count=len(norms),
                         norm_min=float(norms.min()),norm_max=float(norms.max()),
                         views={str(k):int(sum(retriever.ids==k)) for k in np.unique(retriever.ids)},
                         weights_bytes=WEIGHTS.stat().st_size,index_bytes=COMPETITION_INDEX.stat().st_size)
    for model in window.models.values():
        source=local(model['previewImages'][1]['path'])
        image=cv2.imread(str(source)); paper=detect_paper(image)
        for attempt in range(3):
            result=retriever.retrieve(paper.crop)
            item=dict(model=model['id'],input=str(source.relative_to(ROOT)),kind='indexed contour render; pipeline smoke only',
                      attempt=attempt+1,top3=result['candidates'],timings=result['timings'],accepted=result['accepted'],device=result['device'])
            report['reference_smoke'].append(item)
    check('reference smoke returns ranked top three',all(len(r['top3'])==3 for r in report['reference_smoke']))
    # Use an existing render, openly labelled in evidence. Do not create a pretend sketch.
    file_=local(window.models['human_heart']['previewImages'][1]['path'])
    window.new_drawing()
    def confirm_real_candidate():
        dialog=QApplication.activeModalWidget()
        if dialog is not None and hasattr(dialog,'choose') and window.result:
            report['candidate_dialog_observed']=True
            dialog.choose(window.result['candidates'][0]['id'])
    confirmation=QTimer(); confirmation.timeout.connect(confirm_real_candidate); confirmation.start(150)
    with patch.object(QFileDialog,'getOpenFileName',return_value=(str(file_),'')):
        window.open_drawing()
    deadline=time.perf_counter()+25
    while window.busy and time.perf_counter()<deadline:
        wait(50)
    wait(2200)
    confirmation.stop()
    check('image-file pipeline reaches real retrieval result',window.result is not None)
    if window.result:
        window.debug_dock.show(); wait(250)
        report['file_flow']=dict(source=str(file_),top3=window.result['candidates'],accepted=window.result['accepted'])
        scroll=window.trace.verticalScrollBar(); scroll.setValue(scroll.maximum()); position=scroll.value()
        wait(250)
        # Qt can adjust the bottom value as changing numeric text reflows;
        # remaining at the bottom is valid, jumping back to zero is the bug.
        check('debug ranked results remain scrolled during live refresh',position>0 and scroll.value()>=min(position,scroll.maximum()),
              dict(before=position,after=scroll.value(),maximum=scroll.maximum()))
    window.debug_dock.hide()


def summarize():
    flush()
    samples=args.output/'performance_samples.csv'
    grouped={}
    if samples.exists():
        with samples.open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                grouped.setdefault(row['metric']+' / '+row['detail'],[]).append(float(row['value']))
    summary={key:dict(count=len(values),average=statistics.mean(values),minimum=min(values),maximum=max(values)) for key,values in grouped.items()}
    (args.output/'performance_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    report['finished']=time.strftime('%Y-%m-%dT%H:%M:%S')
    (args.output/'runtime_results.json').write_text(json.dumps(report,indent=2,default=lambda value:value.item() if isinstance(value,np.generic) else str(value)),encoding='utf-8')


def run():
    try:
        deadline=time.perf_counter()+90
        while not window.retriever_ready and window.retrieval.isRunning() and time.perf_counter()<deadline:
            wait(50)
        check('native startup reaches retrieval ready',window.retriever_ready,window.encoder_name)
        report['environment']=dict(python=sys.version,platform=platform.platform(),
                                   packages={name:importlib.metadata.version(name) for name in
                                             ['PySide6','vtk','trimesh','opencv-contrib-python','mediapipe','torch','torchvision','open_clip_torch','numpy']})
        report['main_frame']=snapshot('runtime-main.png')
        model_keys=args.models or ['human_heart','human_lungs','antique_camera','toy_car','lantern','water_bottle','earth']
        for key in ([] if args.quick or args.retrieval_only or args.framing_only else model_keys):
            try:
                validate_model(window.models[key])
            except Exception:
                report['exceptions'].append(traceback.format_exc()); print(traceback.format_exc(),flush=True)
        if args.quick:
            window.open_model('human_heart'); wait(2200)
        if args.framing_only:
            validate_framing()
        if not args.retrieval_only and not args.framing_only and not args.model_only:
            validate_mouse(); validate_failures()
        if not args.quick and not args.framing_only and not args.model_only:
            validate_reference_smoke()
        if args.camera is not None:
            window.new_drawing(); window.camera_choice.setCurrentIndex(args.camera); window.start_camera()
            wait(12000)
            worker=window.camera_worker; packet=worker.take_latest()
            report['camera']=dict(index=args.camera,frame_received=packet is not None,metrics=worker.metrics,
                                  paper_detected=bool(packet and packet[2] and packet[2].quad is not None),
                                  hands=len(packet[3].hands) if packet else 0,
                                  mean_brightness=float(packet[1].mean()) if packet else None)
            report['camera']['evidence']=snapshot('runtime-camera.png')
            if packet and packet[2] and packet[2].quad is None:
                check('actual no-paper input does not auto-capture',not packet[2].ready and window.result is None)
            validate_camera_failures()
        check('no unhandled Python exceptions',not report['exceptions'],report['exceptions'])
    except Exception:
        report['exceptions'].append(traceback.format_exc()); print(traceback.format_exc(),flush=True)
    finally:
        try:
            summarize()
        finally:
            window.close()


QTimer.singleShot(250,run)
app.exec()
summarize()
print('Runtime report: '+str(args.output/'runtime_results.json'),flush=True)
raise SystemExit(1 if report['exceptions'] or any(not row['passed'] for row in report['checks']) else 0)
