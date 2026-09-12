"""A single native Python window, with optional hierarchy and CV detail drawers."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,QSlider,QCheckBox,
    QFileDialog,QDockWidget,QTreeWidget,QTreeWidgetItem,QPlainTextEdit,QScrollArea,
    QSpinBox,QDialog,QSizePolicy,QApplication,QComboBox,QMessageBox,
)

from desktop.camera import CameraWorker
from desktop.dialogs import LibraryDialog,pixmap
from desktop.interactions import InteractionEngine
from desktop.library import read_manifest
from desktop.paper import detect_paper, sketch_stages
from desktop.query_regions import detect_query_regions, draw_regions
from desktop.paths import ROOT
from desktop.retrieval_worker import RetrievalWorker
from desktop.scene import SceneWidget
from desktop.performance import record, flush, START


STYLE='''
QMainWindow,QWidget { background:#141b23; color:#e7eeee; font-family:"Segoe UI"; font-size:12px; }
QLabel#Brand { font-size:22px; font-weight:700; letter-spacing:2px; color:#efc57b; }
QLabel#ObjectName { font-size:17px; font-weight:600; }
QLabel#Hint { color:#acbdc8; padding:3px; }
QPushButton { border:1px solid #425461; border-radius:5px; background:#23303c; padding:8px 13px; }
QPushButton:hover { background:#334857; border-color:#91b6bf; }
QPushButton:pressed { background:#455965; }
QPushButton:disabled { color:#70808a; background:#1a242d; }
QPushButton:focus { border:2px solid #efc57b; }
QPushButton#Capture { color:#172029; background:#efc57b; font-weight:600; }
QSlider::groove:horizontal { height:5px; background:#40515d; border-radius:2px; }
QSlider::handle:horizontal { width:15px; margin:-6px 0; border-radius:7px; background:#efc57b; }
QTreeWidget,QListWidget,QPlainTextEdit { background:#111921; border:1px solid #354653; padding:5px; }
QTreeWidget::item:selected,QListWidget::item:selected { background:#355265; }
QDockWidget::title { background:#273540; padding:9px; }
QCheckBox { spacing:6px; }
QSpinBox { border:1px solid #425461; padding:5px; }
QStatusBar { background:#101820; color:#b1c1c8; }
'''


class InsideOutWindow(QMainWindow):
    def __init__(self, camera_index=0,device='auto',start_camera=True):
        super().__init__(); self.setWindowTitle('InsideOut | Draw. Reveal. Explore.'); self.resize(1360,860)
        self.setMinimumSize(900,600); self.setStyleSheet(STYLE)
        self.models={m['id']:m for m in read_manifest()}; self.result=None
        self.frame=None; self.paper=None; self.capture_paper=None; self.gestures=None
        self.last_serial=0; self.token=0; self.busy=False; self.retriever_ready=False
        self.startup_encoder_recorded=False; self.encoder_error=''
        self.camera_message='Camera off. Use Open drawing or Library.'; self.debug_paper=None
        self.next_auto=0.; self.encoder_name='Loading visual encoder...'; self.camera_index=camera_index
        self.camera_worker=None; self.closing=False; self.close_started=0.; self.pending_camera_index=None
        self.last_sketch_debug=None; self.query_regions=[]; self.last_region_update=0.
        central=QWidget(); self.setCentralWidget(central); outer=QVBoxLayout(central)
        outer.setContentsMargins(12,10,12,8); outer.setSpacing(8)
        header=QHBoxLayout(); brand=QLabel('INSIDEOUT'); brand.setObjectName('Brand'); header.addWidget(brand)
        header.addStretch(); self.mode_label=QLabel('DRAW / hold a sketch in view'); header.addWidget(self.mode_label); header.addStretch()
        header.addWidget(QLabel('Input'))
        self.camera_choice=QComboBox(); self.camera_choice.setAccessibleName('Camera selection')
        for index in range(6):
            self.camera_choice.addItem(f'Camera {index}',index)
        if self.camera_choice.findData(camera_index)<0:
            self.camera_choice.addItem(f'Camera {camera_index}',camera_index)
        self.camera_choice.setCurrentIndex(self.camera_choice.findData(camera_index))
        self.camera_choice.currentIndexChanged.connect(self.camera_selection_changed)
        header.addWidget(self.camera_choice)
        self.camera_button=self.button('Camera on',self.toggle_camera,header)
        self.button('Library',self.open_library,header); self.button('Parts',lambda:self.parts_dock.setVisible(not self.parts_dock.isVisible()),header)
        self.button('Debug · D',self.toggle_debug,header); outer.addLayout(header)
        acquisition=QHBoxLayout()
        self.capture_button=self.button('Capture · Space',self.capture,acquisition); self.capture_button.setObjectName('Capture')
        self.button('Open drawing',self.open_drawing,acquisition)
        self.auto=QCheckBox('Auto-capture stable view'); self.auto.setChecked(True); acquisition.addWidget(self.auto)
        self.reduced=QCheckBox('Reduce motion'); acquisition.addWidget(self.reduced)
        acquisition.addStretch(); self.button('New drawing · N',self.new_drawing,acquisition); outer.addLayout(acquisition)
        self.scene=SceneWidget(); self.scene.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.reduced.toggled.connect(self.scene.set_reduced_motion)
        outer.addWidget(self.scene,1); self.interactions=InteractionEngine(self.scene)
        bottom=QHBoxLayout(); self.object_name=QLabel('Show a drawing to the camera'); self.object_name.setObjectName('ObjectName')
        bottom.addWidget(self.object_name); bottom.addStretch(); self.part_name=QLabel('Point to select a part'); bottom.addWidget(self.part_name); outer.addLayout(bottom)
        controls=QHBoxLayout(); controls.addWidget(QLabel('Explode'))
        self.explode=QSlider(Qt.Orientation.Horizontal); self.explode.setRange(0,100); self.explode.setAccessibleName('Explosion amount')
        self.explode.setMinimumWidth(140); self.explode.setMaximumWidth(280)
        self.explode.valueChanged.connect(lambda value:self.scene.set_explosion(value/100)); controls.addWidget(self.explode)
        controls.addWidget(QLabel('Depth')); self.level=QSpinBox(); self.level.setRange(1,8); self.level.setAccessibleName('Hierarchy explosion depth')
        self.level.valueChanged.connect(self.scene.set_level); controls.addWidget(self.level)
        self.button('Isolate · I',self.scene.isolate,controls); self.button('Hide/show · H',self.scene.hide_selected,controls)
        self.button('Show all',self.scene.show_all,controls); self.button('Reassemble · R',self.reset,controls); controls.addStretch()
        self.help_button=self.button('Controls',self.show_help,controls); outer.addLayout(controls)
        self.hint=QLabel('Point to select · pinch to pull · wrist turn to rotate · spread two hands to explode · hold one palm to reset')
        self.hint.setObjectName('Hint'); self.hint.setWordWrap(True); outer.addWidget(self.hint)
        self.parts_dock=QDockWidget('Object structure',self); self.parts_dock.setObjectName('parts')
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(['Component']); self.tree.itemClicked.connect(self.tree_select)
        self.parts_dock.setWidget(self.tree); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.parts_dock); self.parts_dock.hide()
        self.debug_dock=QDockWidget('Computer vision / live data',self); self.debug_dock.setObjectName('debug')
        debug_container=QWidget(); debug_layout=QVBoxLayout(debug_container)
        self.query_label=QLabel('Query preview'); self.query_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rectified_label=QLabel('Selected query region'); self.rectified_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rectified_label.setToolTip('Selected page, drawing, poster, center crop, or full-frame region')
        self.view_label=QLabel('Best rendered view'); self.view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        debug_layout.addWidget(self.rectified_label); debug_layout.addWidget(self.query_label); debug_layout.addWidget(self.view_label)
        self.trace=QPlainTextEdit(); self.trace.setReadOnly(True); debug_layout.addWidget(self.trace)
        self.debug_dock.setWidget(debug_container); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.debug_dock); self.debug_dock.hide()
        self.scene.selection.connect(self.on_selection)
        self.shortcuts=[]
        for key,callback in [('D',self.toggle_debug),('Space',self.capture),('N',self.new_drawing),('R',self.reset),('Escape',self.reset),('I',self.scene.isolate),('H',self.scene.hide_selected),('F11',self.full_screen)]:
            shortcut=QShortcut(QKeySequence(key),self); shortcut.activated.connect(callback); self.shortcuts.append(shortcut)
        self.retrieval=RetrievalWorker(device,self); self.retrieval.ready.connect(self.on_encoder_ready)
        self.retrieval.result.connect(self.on_result); self.retrieval.error.connect(self.on_retrieval_error); self.retrieval.start()
        self.poller=QTimer(self); self.poller.timeout.connect(self.poll); self.poller.start(33)
        self.statusBar().showMessage('Preparing local image encoder. You can open the object library now.')
        if start_camera:
            self.start_camera()
        else:
            self.camera_button.setText('Camera off')

    def button(self,text,callback,layout):
        button=QPushButton(text); button.clicked.connect(callback); layout.addWidget(button); return button

    def start_camera(self):
        if self.camera_worker and self.camera_worker.isRunning():
            return
        self.camera_index=int(self.camera_choice.currentData())
        self.pending_camera_index=None; self.camera_message=f'Opening Camera {self.camera_index}...'
        self.last_serial=0; self.frame=None; self.paper=None
        self.camera_worker=CameraWorker(self.camera_index,self); self.camera_worker.notice.connect(self.camera_notice)
        self.camera_worker.finished.connect(self.camera_finished); self.camera_worker.start(); self.camera_button.setText('Camera on')

    def camera_notice(self,message):
        self.camera_message=message
        self.statusBar().showMessage(message)

    def camera_finished(self):
        self.camera_button.setText('Camera off'); self.camera_button.setEnabled(True)
        self.interactions.release(); self.gestures=None; self.paper=None; self.frame=None
        self.scene.pointer.VisibilityOff()
        if self.pending_camera_index is not None and not self.closing:
            index=self.pending_camera_index; self.pending_camera_index=None
            self.camera_choice.blockSignals(True); self.camera_choice.setCurrentIndex(self.camera_choice.findData(index)); self.camera_choice.blockSignals(False)
            self.start_camera()

    def camera_selection_changed(self,index):
        if not self.camera_worker or not self.camera_worker.isRunning():
            self.camera_index=int(self.camera_choice.itemData(index)); return
        selected=int(self.camera_choice.itemData(index))
        if selected==self.camera_index and self.pending_camera_index is None:
            return
        self.pending_camera_index=selected
        self.camera_button.setText('Switching camera...'); self.camera_button.setEnabled(False)
        self.camera_worker.requestInterruption()

    def toggle_camera(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.requestInterruption(); self.camera_button.setText('Stopping camera...'); self.camera_button.setEnabled(False)
        else:
            self.start_camera()

    def on_encoder_ready(self,name):
        self.encoder_name=name; self.retriever_ready=True
        self.encoder_error=''
        if not self.startup_encoder_recorded:
            record('startup_retrieval_ready_ms',(time.perf_counter()-START)*1000,detail=name)
            self.startup_encoder_recorded=True; flush()
        message='Shape-only fallback active; matches always require confirmation.' if 'fallback' in name else 'Ready. Show any drawing or image, then press Capture.'
        self.statusBar().showMessage(message+' '+self.camera_message)

    def poll(self):
        if self.closing:
            return
        self.capture_button.setEnabled(self.frame is not None and self.retriever_ready and not self.busy)
        modal=QApplication.activeModalWidget() is not None
        packet=self.camera_worker.take_latest() if self.camera_worker and self.camera_worker.isRunning() else None
        if packet and packet[0]!=self.last_serial:
            self.last_serial,self.frame,self.paper,self.gestures=packet
            if self.scene.mode=='capture' and (self.debug_dock.isVisible() or time.monotonic()-self.last_region_update>.35):
                self.query_regions=detect_query_regions(self.frame,self.paper)
                self.last_region_update=time.monotonic()
            display=self.frame
            if self.debug_dock.isVisible() and self.scene.mode=='capture' and self.query_regions:
                display=draw_regions(self.frame,self.query_regions)
            self.scene.set_frame(display,self.paper,self.gestures,self.debug_dock.isVisible())
            if self.debug_dock.isVisible() and self.scene.mode=='capture' and not self.busy and self.result is None and self.paper is not None and self.paper is not self.debug_paper:
                self.debug_paper=self.paper
                preview=self.query_regions[0].image if self.query_regions else self.paper.crop
                self.rectified_label.setPixmap(pixmap(cv2.cvtColor(preview,cv2.COLOR_BGR2RGB)).scaled(190,110,Qt.AspectRatioMode.KeepAspectRatio))
            if self.reduced.isChecked() and self.scene.mode=='materialize':
                self.scene.reveal_start=time.monotonic()-2
            if not modal and not self.busy:
                self.interactions.update(self.gestures)
            if not modal and self.scene.mode=='capture' and self.auto.isChecked() and not self.busy and self.retriever_ready and self.paper and self.paper.ready and time.monotonic()>self.next_auto:
                self.capture()
        self.explode.blockSignals(True); self.explode.setValue(round(self.scene.explosion_target*100)); self.explode.blockSignals(False)
        if self.scene.mode=='explore':
            self.mode_label.setText('EXPLORE / '+(self.gestures.label if self.gestures else 'mouse controls available'))
        if self.debug_dock.isVisible():
            self.update_debug()

    def capture(self):
        if self.frame is None or self.busy or not self.retriever_ready:
            return
        self.capture_paper=self.paper if self.paper is not None and self.paper.quad is not None else None
        self.query_regions=detect_query_regions(self.frame,self.paper)
        if not self.query_regions:
            self.statusBar().showMessage('No usable drawing or image region was found.'); return
        if self.debug_dock.isVisible() or os.environ.get('INSIDEOUT_SKETCH_DEBUG'):
            self.last_sketch_debug=self.save_sketch_debug(self.query_regions)
        self.submit([region.payload() for region in self.query_regions])

    def save_sketch_debug(self,regions):
        label=re.sub(r'[^a-z0-9_-]+','-',os.environ.get('INSIDEOUT_SKETCH_LABEL','unlabeled').lower()).strip('-') or 'unlabeled'
        folder=ROOT/'docs'/'evidence'/'sketch_debug'/f"{label}-{time.strftime('%Y%m%d-%H%M%S')}"
        folder.mkdir(parents=True,exist_ok=True)
        cv2.imwrite(str(folder/'01-camera-frame.png'),self.frame)
        overlay=draw_regions(self.frame,regions)
        cv2.imwrite(str(folder/'02-query-regions.png'),overlay)
        image=regions[0].image; cv2.imwrite(str(folder/'03-primary-region.png'),image)
        stages=sketch_stages(image)
        cv2.imwrite(str(folder/'04-cropped-drawing.png'),stages['cropped'])
        cv2.imwrite(str(folder/'05-final-retrieval-query.png'),stages['query'])
        for index,region in enumerate(regions):
            cv2.imwrite(str(folder/f'roi-{index+1:02d}-{region.kind.replace("/","-")}.png'),region.image)
        metadata=dict(label=label,capturedAt=time.strftime('%Y-%m-%dT%H:%M:%S'),
                      paperQuad=None if self.paper is None or self.paper.quad is None else self.paper.quad.tolist(),
                      candidates=[{k:v for k,v in region.payload().items() if k!='image'} for region in regions])
        (folder/'capture.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        return folder

    def submit(self,image):
        if not self.retriever_ready:
            self.statusBar().showMessage(self.encoder_error or 'Wait for the local visual encoder to finish loading.'); return
        if self.busy:
            return
        self.busy=True; self.token+=1; self.mode_label.setText('MATCHING / searching rendered views')
        first=image[0]['image'] if isinstance(image,list) else image
        preview=cv2.cvtColor(first,cv2.COLOR_BGR2RGB) if first.ndim==3 else first
        self.rectified_label.setPixmap(pixmap(preview).scaled(190,110,Qt.AspectRatioMode.KeepAspectRatio))
        self.statusBar().showMessage('Comparing drawing with the local model library...')
        self.interactions.release(); self.retrieval.submit(self.token,image)

    def open_drawing(self):
        if self.busy:
            return
        file,_=QFileDialog.getOpenFileName(self,'Open a drawing','','Images (*.png *.jpg *.jpeg *.bmp *.webp)')
        if not file:
            return
        try:
            encoded=np.fromfile(file,dtype=np.uint8)
            image=cv2.imdecode(encoded,cv2.IMREAD_COLOR) if encoded.size else None
            if image is None:
                raise ValueError('Unreadable or empty image')
            paper=detect_paper(image); regions=detect_query_regions(image,paper)
        except (OSError,ValueError,cv2.error) as exc:
            self.statusBar().showMessage(f'Cannot read that image. Choose a valid PNG or JPEG. ({exc})'); return
        # File coordinates cannot anchor a model to an unrelated webcam image.
        self.capture_paper=None
        self.submit([region.payload() for region in regions])

    def on_result(self,token,result):
        if self.closing or token!=self.token:
            return
        self.busy=False; self.result=result; self.next_auto=time.monotonic()+5
        selected=result['selectedROIImage']; selected_rgb=cv2.cvtColor(selected,cv2.COLOR_BGR2RGB) if selected.ndim==3 else selected
        self.rectified_label.setPixmap(pixmap(selected_rgb).scaled(190,110,Qt.AspectRatioMode.KeepAspectRatio))
        self.query_label.setPixmap(pixmap(result['query']).scaled(190,190,Qt.AspectRatioMode.KeepAspectRatio))
        best=result['candidates'][0]
        self.view_label.setPixmap(pixmap(best['view']).scaled(190,190,Qt.AspectRatioMode.KeepAspectRatio))
        if self.last_sketch_debug:
            evidence=dict(accepted=result['accepted'],margin=result['margin'],device=result['device'],
                          candidates=result['candidates'],timings=result['timings'])
            (Path(self.last_sketch_debug)/'ranking.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            self.last_sketch_debug=None
        if result['accepted']:
            self.open_model(best['id'])
        else:
            QMessageBox.warning(self,'Drawing not recognized clearly',
                                'Drawing not recognized clearly — please try again.\n\nMove closer, improve lighting, or use a clearer drawing/image.')
            self.new_drawing(); self.next_auto=time.monotonic()+6

    def open_model(self,key):
        self.interactions.release()
        try:
            model=self.models[key]
            self.scene.load(model,self.capture_paper)
        except Exception as exc:
            self.statusBar().showMessage(f'Could not load model: {exc}'); return
        if self.reduced.isChecked():
            self.scene.reveal_start=time.monotonic()-2
        self.object_name.setText(f"{model['name']}  /  {model['partCount']} parts")
        self.mode_label.setText('REVEAL / '+model['name'])
        self.level.setMaximum(max(1,model['hierarchyDepth']))
        self.populate_tree(model)
        score=next((c['score'] for c in self.result['candidates'] if c['id']==key),None) if self.result else None
        match=f'Visual similarity {score:.3f}. ' if score is not None else 'Opened directly from library. '
        self.statusBar().showMessage(match+f"{model.get('author','')} | {model['license']}")

    def on_retrieval_error(self,token,message):
        if token!=-1 and token!=self.token:
            return
        self.busy=False; self.next_auto=time.monotonic()+8
        if token==-1:
            self.encoder_name='Retrieval unavailable: '+message
            self.retriever_ready=False; self.encoder_error=message
        self.statusBar().showMessage(message)
        self.mode_label.setText('DRAW / capture again')
        if token>=0 and not self.closing:
            QMessageBox.warning(self,'Drawing not recognized clearly',message)

    def new_drawing(self):
        self.token+=1; self.busy=False; self.interactions.release(); self.scene.clear(); self.capture_paper=None
        self.next_auto=time.monotonic()+2; self.result=None; self.query_regions=[]
        self.object_name.setText('Show a drawing to the camera'); self.part_name.setText('Point to select a part')
        self.mode_label.setText('DRAW / hold a sketch in view'); self.tree.clear()

    def reset(self):
        self.interactions.release(); self.scene.reset()

    def open_library(self):
        self.interactions.release()
        dialog=LibraryDialog(list(self.models.values()),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.token+=1; self.busy=False; self.result=None; self.capture_paper=None
            self.open_model(dialog.chosen)

    def populate_tree(self,model):
        self.tree.clear()
        nodes=model['nodes']
        def add(key,parent):
            node=nodes[key]
            # Collapse identity-only wrappers visually, but retain the source tree in data.
            if not node['part'] and len(node['children'])==1:
                add(node['children'][0],parent); return
            item=QTreeWidgetItem([node['name']]); item.setData(0,Qt.ItemDataRole.UserRole,key)
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in node['children']:
                add(child,item)
        add(model['root'],None); self.tree.expandToDepth(1)

    def tree_select(self,item,column):
        self.scene.select(item.data(0,Qt.ItemDataRole.UserRole))

    def on_selection(self,key,name):
        self.part_name.setText(name or 'Point to select a part')

    def toggle_debug(self):
        self.debug_dock.setVisible(not self.debug_dock.isVisible())

    def full_screen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def update_debug(self):
        hands=self.gestures.hands if self.gestures else []
        info=dict(fps=round(self.scene.fps),mode=self.scene.mode,encoder=self.encoder_name,
                  cameraStatus=self.camera_message,cameraMetrics=self.camera_worker.metrics if self.camera_worker else {},
                  loadedModel=self.scene.model['name'] if self.scene.model else None,
                  gesture=self.gestures.label if self.gestures else 'No camera',
                  interactionState=self.interactions.state,
                  hands=[dict(id=h.identity,pinch=round(h.pinch_distance,3),palmScale=round(h.scale,3),wristAngle=round(h.angle,3)) for h in hands],
                  selected=self.scene.selected,hover=self.scene.hovered,raycast=self.scene.raycast,
                  relativeDepth=round(self.interactions.depth,3),explosion=round(self.scene.explosion,3),
                  meshes=len(self.scene.parts),hierarchyDepth=self.scene.model['hierarchyDepth'] if self.scene.model else 0,
                  roiCandidates=[dict(type=r.kind,score=round(r.score,3),rect=r.rect) for r in self.query_regions])
        if self.result:
            info.update(queryMs=round(self.result['elapsedMs']),margin=round(self.result['margin'],4),
                        timings=self.result.get('timings',{}),device=self.result.get('device',''),
                        retrievalStatus='Accepted' if self.result['accepted'] else 'Uncertain',
                        selectedROI=self.result.get('selectedROI',{}),queryDiagnostics=self.result.get('queryDiagnostics',{}),
                        candidates=[dict(name=self.models[c['id']]['name'],score=round(c['score'],4),bestCosine=c['bestCosine'],
                                         banks=c.get('bankScores',{}),roi=c.get('roiType',''),queryVariant=c['queryVariant'],
                                         referenceBank=c.get('referenceBank',''),referenceKind=c['referenceKind'],view=c['angle']) for c in self.result['candidates']],
                        fallbackReason=self.result['fallbackReason'])
        scroll=self.trace.verticalScrollBar(); position=scroll.value()
        self.trace.setPlainText(json.dumps(info,indent=2))
        scroll.setValue(position)

    def show_help(self):
        dialog=QDialog(self); dialog.setWindowTitle('InsideOut controls'); layout=QVBoxLayout(dialog)
        text=QLabel('Point: hover; hold the point briefly to select.\nPinch over a part: grab. Move X/Y or move toward the camera.\nTurn your wrist while pinching: rotate the part.\nPinch empty space: rotate the whole object.\nHold a pinch still for 1.3 seconds: isolate/restore selection.\nTwo open palms or two pinches: spread/close to control explosion.\nOne open palm held for 1.2 seconds: reassemble.\n\nFallback: left drag orbits; wheel zooms; Shift + left drag pulls a part.\nI isolates; H hides/shows; R resets; N starts a new drawing; D opens debug.\nUse Parts to select an entire parent assembly. Depth controls nested explosion.\n\nDepth uses apparent palm size; it is relative, not a measurement in centimeters.')
        text.setWordWrap(True); layout.addWidget(text); self.button('Close',dialog.accept,layout); dialog.resize(620,380); dialog.exec()

    def closeEvent(self,event):
        # Do not destroy QThreads while native camera or model inference is finishing.
        if not self.closing:
            self.closing=True; self.close_started=time.monotonic(); self.poller.stop(); self.scene.timer.stop()
            self.retrieval.requestInterruption()
            if self.camera_worker:
                self.camera_worker.requestInterruption()
            self.statusBar().showMessage('Closing camera and model worker...')
        running=self.retrieval.isRunning() or (self.camera_worker and self.camera_worker.isRunning())
        if running:
            event.ignore(); QTimer.singleShot(100,self.close)
        else:
            self.scene.shutdown(); flush(); event.accept()
