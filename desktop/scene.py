"""Native VTK scene: ray picking, hierarchy, elastic explosion and anchored reveal."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import vtk
from scipy.spatial.transform import Rotation
from vtk.util.numpy_support import numpy_to_vtk
from PySide6.QtCore import Signal, QTimer, QEvent, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from desktop.geometry import actor_for, add_lights
from desktop.performance import record, START
from desktop.config import (
    DEPTH_DEAD_ZONE, DEPTH_MAX_STEP, DEPTH_SENSITIVITY,
    ORBIT_DEAD_ZONE_PX, ORBIT_MAX_STEP_PX, ORBIT_SENSITIVITY,
    ROTATION_DEAD_ZONE_RADIANS, ROTATION_MAX_STEP_RADIANS, ROTATION_SENSITIVITY,
    TRANSLATION_DEAD_ZONE_PX, TRANSLATION_MAX_STEP_PX, TRANSLATION_SENSITIVITY,
)


@dataclass
class PartState:
    spec: dict
    actor: object
    position: np.ndarray
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))
    spin: object = field(default_factory=Rotation.identity)
    held: bool = False


class SceneWidget(QWidget):
    selection = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.vtk=QVTKRenderWindowInteractor(self); layout.addWidget(self.vtk)
        self.vtk.installEventFilter(self)
        self.window=self.vtk.GetRenderWindow(); self.window.SetNumberOfLayers(2); self.window.SetMultiSamples(4)
        self.background=vtk.vtkRenderer(); self.background.SetLayer(0); self.background.InteractiveOff()
        self.background.SetBackground(.065,.077,.091)
        self.renderer=vtk.vtkRenderer(); self.renderer.SetLayer(1); self.renderer.SetPreserveColorBuffer(True)
        self.renderer.SetUseDepthPeeling(True); self.renderer.SetMaximumNumberOfPeels(40)
        self.renderer.SetOcclusionRatio(.15); self.window.SetAlphaBitPlanes(1)
        self.window.AddRenderer(self.background); self.window.AddRenderer(self.renderer)
        add_lights(self.renderer)
        self.camera=self.renderer.GetActiveCamera(); self.camera.SetPosition(0,0,8)
        self.camera.SetFocalPoint(0,0,0); self.camera.SetViewUp(0,1,0); self.camera.ParallelProjectionOn(); self.camera.SetParallelScale(2.25)
        self.video_actor=vtk.vtkImageActor(); self.video_actor.InterpolateOn(); self.video_actor.PickableOff()
        self.background.AddActor(self.video_actor); self.video_actor.VisibilityOff()
        self.picker=vtk.vtkCellPicker(); self.picker.SetTolerance(.008); self.picker.PickFromListOn()
        self.pointer=vtk.vtkTextActor(); self.pointer.SetInput('o'); self.pointer.GetTextProperty().SetFontSize(26)
        self.pointer.GetTextProperty().SetColor(.98,.78,.37); self.pointer.PickableOff(); self.pointer.VisibilityOff()
        self.renderer.AddActor2D(self.pointer)
        self.title=vtk.vtkTextActor(); self.title.GetTextProperty().SetFontSize(15); self.title.GetTextProperty().SetColor(.72,.8,.82)
        self.title.PickableOff(); self.title.SetDisplayPosition(26,24); self.renderer.AddActor2D(self.title)
        style=vtk.vtkInteractorStyleTrackballCamera(); style.SetDefaultRenderer(self.renderer)
        self.vtk.SetInteractorStyle(style)
        self.vtk.AddObserver('MouseMoveEvent',self.mouse_move)
        self.vtk.AddObserver('LeftButtonPressEvent',self.mouse_down)
        self.vtk.AddObserver('LeftButtonReleaseEvent',self.mouse_up)
        # The scene auto-fits smoothly, so update that target after VTK's wheel zoom.
        self.vtk.AddObserver('MouseWheelForwardEvent',self.mouse_wheel)
        self.vtk.AddObserver('MouseWheelBackwardEvent',self.mouse_wheel)
        self.vtk.Initialize()
        self.parts={}; self.model=None; self.actor_keys={}
        self.selected=None; self.hovered=None; self.isolated=None; self.hidden=set()
        self.rotation=Rotation.identity(); self.explosion=0.; self.explosion_target=0.; self.level=1
        self.vectors={}; self.grab=None; self.mouse_grab=False; self.mode='capture'
        self.frame_shape=(720,960); self.anchor=np.zeros(3); self.paper_angle=0.; self.reveal_start=0.
        self.paper_anchor=False
        self.model_scale=1.; self.model_translation=np.zeros(3)
        self.last_tick=time.monotonic(); self.fps=0.; self.raycast=None
        self.focus_target=np.zeros(3); self.scale_target=2.25
        self.reduced_motion=False
        self.first_frame=True; self.fps_since=time.perf_counter(); self.fps_frames=0
        self.title.SetInput('Hold your drawing still, or choose Open drawing / Library')
        self.timer=QTimer(self); self.timer.timeout.connect(self.animate); self.timer.start(16)

    def load(self, model, paper=None):
        started=time.perf_counter()
        # Retain the current usable scene if any new mesh/texture cannot load.
        prepared=[(part,actor_for(part)) for part in model['components']]
        self.end_grab()
        for state in self.parts.values():
            self.renderer.RemoveActor(state.actor)
        self.picker.InitializePickList(); self.parts={}; self.actor_keys={}
        self.model=model; self.hidden.clear(); self.isolated=None; self.selected=None; self.hovered=None
        self.rotation=Rotation.identity(); self.explosion=self.explosion_target=0.
        self.camera.SetPosition(0,0,8); self.camera.SetFocalPoint(0,0,0); self.camera.SetViewUp(0,1,0)
        self.camera.SetParallelScale(2.25); self.focus_target=np.zeros(3); self.scale_target=2.25
        for part,actor in prepared:
            actor.SetPosition(0,0,0)
            self.parts[part['id']]=PartState(part,actor,np.array(part['center'],dtype=float))
            self.renderer.AddActor(actor); self.picker.AddPickList(actor)
            self.actor_keys[actor.GetAddressAsString('')]=part['id']
        self.compute_explosion()
        self.anchor=np.zeros(3); self.paper_angle=0.; self.paper_anchor=paper is not None and paper.quad is not None
        if paper is not None and paper.quad is not None:
            center=paper.quad.mean(0)
            x,y=self.video_position(center[0]/self.frame_shape[1],center[1]/self.frame_shape[0])
            self.anchor=self.display_to_plane(x,y,np.zeros(3))
            edge=paper.quad[1]-paper.quad[0]
            self.paper_angle=-math.atan2(edge[1],edge[0])
        self.mode='materialize'; self.reveal_start=time.monotonic()
        self.title.SetInput('Matched: '+model['name'])
        self.selection.emit('', '')
        record('model_load_ms',(time.perf_counter()-started)*1000,detail=model['id'])

    def clear(self):
        self.end_grab(); self.model=None; self.selected=None; self.hovered=None
        for state in self.parts.values():
            self.renderer.RemoveActor(state.actor)
        self.parts={}; self.actor_keys={}; self.picker.InitializePickList()
        self.hidden.clear(); self.isolated=None; self.explosion=self.explosion_target=0.
        self.pointer.VisibilityOff()
        self.mode='capture'; self.title.SetInput('Hold your drawing still, or press Capture')
        self.selection.emit('', '')

    def set_level(self, level):
        self.level=level
        self.compute_explosion()
        self.set_explosion(self.explosion_target)

    def set_reduced_motion(self,enabled):
        self.reduced_motion=bool(enabled)
        if enabled and self.mode=='materialize':
            self.reveal_start=time.monotonic()-2

    def compute_explosion(self):
        if not self.model:
            return
        nodes=self.model['nodes']; contribution={}; meaningful_depth={}

        def visit(key, depth):
            node=nodes[key]; children=node['children']
            meaningful_depth[key]=depth
            if len(children)>1:
                center=np.array(node['center']); ordered=sorted(children)
                positions=[]; radii=[]
                for index,child in enumerate(ordered):
                    child_node=nodes[child]; direction=np.array(child_node['center'])-center
                    override=self.model.get('explode',{}).get('axisOverrides',{}).get(child_node['sourceName'])
                    if override is not None:
                        direction=np.array(override,dtype=float)
                    if np.linalg.norm(direction)<.08:
                        angle=index*2.39996
                        direction=np.array([math.cos(angle),math.sin(angle),.3*((index%3)-1)])
                    direction/=max(np.linalg.norm(direction),1e-8)
                    distance=min(1.7,.5+child_node['radius']*.45)/(1+depth*.28)
                    positions.append(np.array(child_node['center'])+direction*distance)
                    radii.append(min(child_node['radius'],.6))
                # Bounded sphere repulsion at each branching level avoids identical vectors.
                positions=np.asarray(positions)
                for _ in range(5):
                    for i in range(len(ordered)):
                        for j in range(i):
                            delta=positions[i]-positions[j]; dist=np.linalg.norm(delta)
                            overlap=(radii[i]+radii[j])*.7-dist
                            if overlap>0 and dist>1e-6:
                                correction=delta/dist*min(overlap*.2,.12)
                                positions[i]+=correction; positions[j]-=correction
                for index,child in enumerate(ordered):
                    contribution[child]=(positions[index]-nodes[child]['center']) if depth < self.level else np.zeros(3)
                    visit(child,depth+1)
            else:
                for child in children:
                    contribution[child]=np.zeros(3); visit(child,depth)

        visit(self.model['root'],0)
        self.vectors={}
        for key in self.parts:
            delta=np.zeros(3); current=key
            while current in nodes:
                delta+=contribution.get(current,np.zeros(3)); current=nodes[current]['parent']
            self.vectors[key]=delta

    def video_position(self,x,y):
        width,height=self.window.GetSize(); fh,fw=self.frame_shape
        factor=min(width/max(fw,1),height/max(fh,1))
        return (width-fw*factor)/2+x*fw*factor, height-((height-fh*factor)/2+y*fh*factor)

    def set_frame(self,frame,paper,gestures,debug=False):
        self.frame_shape=frame.shape[:2]
        image=frame.copy()
        if self.mode != 'capture':
            progress=min(1.,(time.monotonic()-self.reveal_start)/1.9)
            image=(image.astype(float)*(1-progress*.90)).astype(np.uint8)
        if paper is not None and paper.quad is not None and (self.mode=='capture' or self.mode=='materialize' and self.paper_anchor):
            cv2.polylines(image,[paper.quad.astype(np.int32)],True,(100,210,240),2,cv2.LINE_AA)
            if self.mode=='capture':
                cv2.putText(image,f'Hold still {int(paper.stable*100)}%',tuple(paper.quad[0].astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.6,(100,230,240),2)
            else:
                center=paper.quad.mean(0)
                px,py=self.video_position(center[0]/image.shape[1],center[1]/image.shape[0])
                self.anchor=self.anchor*.8+self.display_to_plane(px,py,np.zeros(3))*.2
                edge=paper.quad[1]-paper.quad[0]
                self.paper_angle=-math.atan2(edge[1],edge[0])
        if debug:
            chains=((0,1,2,3,4),(0,5,6,7,8),(5,9,10,11,12),(9,13,14,15,16),(13,17,18,19,20),(0,17))
            for hand in gestures.hands:
                pts=(hand.points[:,:2]*np.array([image.shape[1],image.shape[0]])).astype(int)
                for chain in chains:
                    for a,b in zip(chain,chain[1:]):
                        cv2.line(image,tuple(pts[a]),tuple(pts[b]),(190,180,60),1,cv2.LINE_AA)
                for p in pts:
                    cv2.circle(image,tuple(p),3,(80,220,250),-1)
        rgb=np.flipud(cv2.cvtColor(image,cv2.COLOR_BGR2RGB)).copy()
        h,w=rgb.shape[:2]
        data=vtk.vtkImageData(); data.SetDimensions(w,h,1)
        data.GetPointData().SetScalars(numpy_to_vtk(rgb.reshape(-1,3),deep=True,array_type=vtk.VTK_UNSIGNED_CHAR))
        self.video_actor.SetInputData(data); self.video_actor.VisibilityOn()
        bgcam=self.background.GetActiveCamera(); bgcam.ParallelProjectionOn()
        bgcam.SetPosition((w-1)/2,(h-1)/2,1000); bgcam.SetFocalPoint((w-1)/2,(h-1)/2,0)
        rw,rh=self.window.GetSize(); aspect=max(rw,1)/max(rh,1)
        bgcam.SetParallelScale(max(h/2,w/(2*aspect))); self.background.ResetCameraClippingRange()

    def display_to_plane(self,x,y,origin):
        self.renderer.SetDisplayPoint(float(x),float(y),0); self.renderer.DisplayToWorld()
        near=np.array(self.renderer.GetWorldPoint()); near=near[:3]/near[3]
        self.renderer.SetDisplayPoint(float(x),float(y),1); self.renderer.DisplayToWorld()
        far=np.array(self.renderer.GetWorldPoint()); far=far[:3]/far[3]
        normal=np.array(self.camera.GetDirectionOfProjection()); direction=far-near
        denom=float(direction@normal)
        return near+direction*float((np.asarray(origin)-near)@normal)/denom if abs(denom)>1e-8 else near

    def pick(self,x,y):
        self.pointer.SetDisplayPosition(int(x)-8,int(y)-14); self.pointer.VisibilityOn()
        if self.picker.Pick(float(x),float(y),0,self.renderer):
            actor=self.picker.GetActor()
            key=self.actor_keys.get(actor.GetAddressAsString('')) if actor else None
            self.raycast=self.picker.GetPickPosition()
            return key
        self.raycast=None
        return None

    def highlight(self,key):
        self.hovered=key
        selected=set(self.members(self.selected))
        for pid,state in self.parts.items():
            active=pid==key or pid in selected
            prop=state.actor.GetProperty(); prop.SetEdgeVisibility(active)
            prop.SetEdgeColor(.95,.78,.4); prop.SetLineWidth(1.3)

    def members(self,key):
        return self.model['nodes'].get(key,{}).get('leaves',[]) if self.model and key else []

    def select(self,key):
        self.selected=key
        label=self.model['nodes'][key]['name'] if self.model and key else ''
        self.selection.emit(key or '',label)
        self.highlight(self.hovered)

    def set_explosion(self,value):
        self.explosion_target=float(np.clip(value,0,1))
        if not self.isolated:
            self.scale_target=2.25+self.explosion_target*1.4
            # Deep anatomical hierarchies can extend beyond the old fixed fit.
            # A conservative world-space bound keeps the full assembly visible
            # in any camera orientation, without overriding subsequent wheel zoom.
            if self.parts:
                radius=max(np.linalg.norm(np.asarray(s.spec['center'])+self.vectors.get(key,np.zeros(3))*self.explosion_target+s.offset)+s.spec['radius'] for key,s in self.parts.items())
                width,height=self.window.GetSize()
                self.scale_target=max(self.scale_target,radius*1.05/min(1.,max(width,1)/max(height,1)))

    def begin_grab(self,key,x,y,scale=1.,angle=0.):
        if not key:
            self.grab=dict(kind='orbit',x=x,y=y,angle=angle)
            return
        # Respect a selected group only when the picked mesh belongs to it.
        if self.selected and key in self.members(self.selected):
            key=self.selected
        self.select(key)
        members=self.members(key)
        if not members:
            return
        center=np.mean([self.parts[p].position for p in members],axis=0)
        world=self.rotation.apply(center)*self.model_scale+self.model_translation
        point=self.display_to_plane(x,y,world)
        self.grab=dict(kind='part',key=key,members=members,center=center,world=world,point=point,
                       positions={p:self.parts[p].position.copy() for p in members},
                       spins={p:self.parts[p].spin for p in members},scale=max(scale,.01),angle=angle,
                       x=x,y=y,last_scale=max(scale,.01),last_angle=angle)
        for p in members:
            self.parts[p].held=True

    def move_grab(self,x,y,scale=1.,angle=0.):
        grab=self.grab
        if not grab:
            return
        if grab['kind']=='orbit':
            dx=float(np.clip(x-grab['x'],-ORBIT_MAX_STEP_PX,ORBIT_MAX_STEP_PX))
            dy=float(np.clip(y-grab['y'],-ORBIT_MAX_STEP_PX,ORBIT_MAX_STEP_PX))
            if abs(dx)<ORBIT_DEAD_ZONE_PX: dx=0.
            if abs(dy)<ORBIT_DEAD_ZONE_PX: dy=0.
            self.camera.Azimuth(-dx*ORBIT_SENSITIVITY); self.camera.Elevation(-dy*ORBIT_SENSITIVITY)
            self.camera.OrthogonalizeViewUp()
            grab.update(x=x,y=y)
            return
        dx=x-grab['x']; dy=y-grab['y']
        if math.hypot(dx,dy)<TRANSLATION_DEAD_ZONE_PX:
            dx=dy=0.
        else:
            length=max(math.hypot(dx,dy),1e-8)
            factor=min(1.,TRANSLATION_MAX_STEP_PX/length)
            dx*=factor; dy*=factor
        previous_point=self.display_to_plane(grab['x'],grab['y'],grab['world'])
        point=self.display_to_plane(grab['x']+dx,grab['y']+dy,grab['world'])
        towards=-np.array(self.camera.GetDirectionOfProjection())
        depth=math.log(max(scale,.01)/grab['last_scale'])
        depth=0. if abs(depth)<DEPTH_DEAD_ZONE else float(np.clip(depth,-DEPTH_MAX_STEP,DEPTH_MAX_STEP))*DEPTH_SENSITIVITY
        delta=self.rotation.inv().apply((point-previous_point)*TRANSLATION_SENSITIVITY+towards*depth)/max(self.model_scale,.05)
        twist=math.atan2(math.sin(angle-grab['last_angle']),math.cos(angle-grab['last_angle']))
        twist=0. if abs(twist)<ROTATION_DEAD_ZONE_RADIANS else float(np.clip(twist,-ROTATION_MAX_STEP_RADIANS,ROTATION_MAX_STEP_RADIANS))*ROTATION_SENSITIVITY
        spin=Rotation.from_rotvec(self.rotation.inv().apply(towards)*(-twist))
        current={key:np.asarray(self.parts[key].spec['center'])+self.vectors[key]*self.explosion+self.parts[key].offset for key in grab['members']}
        center=np.mean(list(current.values()),axis=0)
        for key in grab['members']:
            state=self.parts[key]
            desired=center+delta+spin.apply(current[key]-center)
            base=np.array(state.spec['center'])+self.vectors[key]*self.explosion
            state.offset=desired-base; state.spin=spin*state.spin
        grab.update(x=x,y=y,last_scale=max(scale,.01),last_angle=angle)

    def end_grab(self):
        if self.grab and self.grab['kind']=='part':
            for key in self.grab['members']:
                if key in self.parts:
                    state=self.parts[key]; state.held=False
                    if np.linalg.norm(state.offset)<.17:
                        state.offset=np.zeros(3)
                        # Near-origin translation should not erase an intentional wrist turn.
                        if state.spin.magnitude()<.1:
                            state.spin=Rotation.identity()
        self.grab=None
        if self.mouse_grab:
            self.mouse_grab=False; self.vtk.releaseMouse()

    def isolate(self):
        if not self.selected:
            return
        self.isolated=None if self.isolated==self.selected else self.selected
        self.update_visibility()
        if self.isolated:
            keys=self.members(self.isolated)
            center=np.mean([self.parts[p].position for p in keys],axis=0)
            self.focus_target=self.rotation.apply(center)*self.model_scale+self.model_translation
            self.scale_target=max(.22,max(np.linalg.norm(self.parts[p].position-center)+self.parts[p].spec['radius'] for p in keys)*1.25)
        else:
            self.focus_target=np.zeros(3); self.set_explosion(self.explosion_target)

    def hide_selected(self):
        keys=self.members(self.selected)
        if keys and all(p in self.hidden for p in keys):
            self.hidden.difference_update(keys)
        else:
            self.hidden.update(keys)
        self.update_visibility()

    def show_all(self):
        self.hidden.clear(); self.isolated=None; self.update_visibility()
        self.focus_target=np.zeros(3); self.set_explosion(self.explosion_target)

    def update_visibility(self):
        allowed=set(self.members(self.isolated)) if self.isolated else set(self.parts)
        for key,state in self.parts.items():
            state.actor.SetVisibility(key in allowed and key not in self.hidden)

    def reset(self):
        self.end_grab()
        for state in self.parts.values():
            state.offset=np.zeros(3); state.spin=Rotation.identity()
        self.set_explosion(0); self.show_all(); self.select(None)
        self.camera.SetViewUp(0,1,0)

    def animate(self):
        render_started=time.perf_counter()
        now=time.monotonic(); dt=min(.1,now-self.last_tick); self.last_tick=now
        blend=1. if self.reduced_motion else 1-math.exp(-dt/.12)
        self.explosion+=(self.explosion_target-self.explosion)*blend
        self.model_scale=1.; self.model_translation=np.zeros(3)
        if self.mode=='materialize':
            t=min(1.,(now-self.reveal_start)/1.9); eased=t*t*(3-2*t)
            self.model_scale=.04+.96*eased; self.model_translation=self.anchor*(1-eased)
            self.rotation=Rotation.from_euler('z',self.paper_angle*(1-eased))
            if t>=1:
                self.mode='explore'; self.title.SetInput(self.model['name'] if self.model else '')
        root=self.rotation.as_matrix()
        for key,state in self.parts.items():
            target=np.asarray(state.spec['center'])+self.vectors.get(key,np.zeros(3))*self.explosion+state.offset
            state.position+=(target-state.position)*blend
            matrix=np.eye(4); matrix[:3,:3]=root@state.spin.as_matrix()*self.model_scale
            matrix[:3,3]=root@state.position*self.model_scale+self.model_translation
            vtkmat=vtk.vtkMatrix4x4(); vtkmat.DeepCopy(matrix.ravel())
            state.actor.SetUserMatrix(vtkmat)
        current=np.array(self.camera.GetFocalPoint()); shift=(self.focus_target-current)*blend
        self.camera.SetFocalPoint(*(current+shift)); self.camera.SetPosition(*(np.array(self.camera.GetPosition())+shift))
        self.camera.SetParallelScale(self.camera.GetParallelScale()+(self.scale_target-self.camera.GetParallelScale())*blend)
        self.renderer.ResetCameraClippingRange()
        self.window.Render()
        finished=time.perf_counter(); self.fps_frames+=1
        elapsed=finished-self.fps_since
        if elapsed>=1.:
            self.fps=self.fps_frames/elapsed
            record('renderer_fps',self.fps,'fps',self.model['id'] if self.model else 'capture')
            self.fps_frames=0; self.fps_since=finished
        record('scene_frame_ms',(finished-render_started)*1000,detail=self.model['id'] if self.model else 'capture')
        if self.first_frame and self.isVisible():
            record('startup_first_frame_ms',(finished-START)*1000)
            self.first_frame=False

    def mouse_move(self,obj,event):
        x,y=self.vtk.GetEventPosition()
        if self.mouse_grab:
            self.move_grab(x,y)
        else:
            self.highlight(self.pick(x,y))

    def eventFilter(self,watched,event):
        # Route Shift-drag before VTK's camera style grabs event focus. Disabling
        # that style inside its press callback can otherwise swallow move/up.
        if watched is self.vtk and event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseMove,QEvent.Type.MouseButtonRelease):
            width,height=self.window.GetSize()
            x=event.position().x()*width/max(self.vtk.width(),1)
            y=(self.vtk.height()-event.position().y())*height/max(self.vtk.height(),1)
            if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                key=self.pick(x,y)
                if key:
                    self.mouse_grab=True; self.begin_grab(key,x,y); self.vtk.grabMouse()
                    return True
            if self.mouse_grab:
                if event.type()==QEvent.Type.MouseMove:
                    self.move_grab(x,y); return True
                if event.type()==QEvent.Type.MouseButtonRelease and event.button()==Qt.MouseButton.LeftButton:
                    self.end_grab(); return True
        return super().eventFilter(watched,event)

    def mouse_down(self,obj,event):
        x,y=self.vtk.GetEventPosition(); key=self.pick(x,y)
        if key:
            self.select(key)
        if self.vtk.GetShiftKey() and key:
            self.mouse_grab=True
            self.begin_grab(key,x,y)
            self.vtk.GetInteractorStyle().SetEnabled(False)

    def mouse_up(self,obj,event):
        if self.mouse_grab:
            self.mouse_grab=False; self.end_grab(); self.vtk.GetInteractorStyle().SetEnabled(True)

    def mouse_wheel(self,obj,event):
        # Queue until the built-in camera style has applied its wheel event.
        QTimer.singleShot(0,self.remember_zoom)

    def remember_zoom(self):
        self.scale_target=float(np.clip(self.camera.GetParallelScale(),.08,20.))

    def shutdown(self):
        self.timer.stop(); self.vtk.Finalize()
