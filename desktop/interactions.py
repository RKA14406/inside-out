"""Gesture arbitration and lifecycle. Rendering never consumes raw landmarks."""
from __future__ import annotations

import numpy as np

from desktop.config import (
    ENABLE_GESTURE_ISOLATE, EXPLODE_DEAD_ZONE, EXPLODE_FILTER_ALPHA,
    EXPLODE_SENSITIVITY, HAND_LOSS_RELEASE_SECONDS, POINT_DWELL_SECONDS,
)


class InteractionEngine:
    def __init__(self, scene):
        self.scene=scene
        self.owner=None; self.pinching=False; self.last_seen=0.
        self.spread_start=None; self.explosion_start=0.
        self.dwell_key=None; self.dwell_since=0.
        self.grab_since=0.; self.grab_point=None; self.grab_scale=1.; self.grab_angle=0.
        self.stationary=True; self.must_release=False; self.depth=0.
        self.state='IDLE'; self.spread_filtered=None

    def release(self):
        self.scene.end_grab(); self.owner=None; self.pinching=False; self.spread_start=None
        self.must_release=False; self.dwell_key=None; self.spread_filtered=None; self.state='IDLE'

    def update(self, frame):
        if self.scene.mode != 'explore':
            return
        now=frame.timestamp
        if frame.reset:
            self.release(); self.scene.reset()
            self.state='RESET'
            return
        if not frame.hands:
            self.scene.pointer.VisibilityOff()
            if now-self.last_seen > HAND_LOSS_RELEASE_SECONDS:
                self.release(); self.scene.highlight(None)
            return
        self.last_seen=now
        two=len(frame.hands)==2 and (all(h.palm for h in frame.hands) or all(h.pinch for h in frame.hands))
        if two and not self.pinching:
            distance=float(np.linalg.norm(frame.hands[0].points[9,:2]-frame.hands[1].points[9,:2]))
            if self.spread_start is None:
                self.spread_start=distance; self.spread_filtered=distance
                self.explosion_start=self.scene.explosion_target; self.state='TWO_HAND_EXPLODE'
            self.spread_filtered+=(distance-self.spread_filtered)*EXPLODE_FILTER_ALPHA
            delta=self.spread_filtered-self.spread_start
            if abs(delta)<=EXPLODE_DEAD_ZONE:
                delta=0.
            else:
                delta=np.sign(delta)*(abs(delta)-EXPLODE_DEAD_ZONE)**1.12
            self.scene.set_explosion(self.explosion_start+delta*EXPLODE_SENSITIVITY)
            return
        if self.state=='TWO_HAND_EXPLODE':
            self.state='IDLE'
        self.spread_start=None; self.spread_filtered=None
        hand=next((h for h in frame.hands if h.identity==self.owner),frame.hands[0])
        if self.owner and hand.identity!=self.owner:
            self.release()
        x,y=self.scene.video_position(hand.x,hand.y)
        if self.must_release:
            self.state='WAIT_RELEASE'
            if not hand.pinch:
                self.must_release=False; self.state='IDLE'
            return
        key=self.scene.pick(x,y) if hand.point or hand.pinch else None
        self.scene.highlight(key)
        if hand.point and not self.pinching:
            self.state='HOVER'
            if key!=self.dwell_key:
                self.dwell_key=key; self.dwell_since=now
            elif key and now-self.dwell_since > POINT_DWELL_SECONDS:
                self.scene.select(key)
        else:
            self.dwell_key=None
            if not self.pinching:
                self.state='IDLE'
        if hand.pinch and not self.pinching:
            self.owner=hand.identity; self.pinching=True; self.grab_since=now
            self.grab_point=np.array([x,y]); self.grab_scale=hand.scale; self.grab_angle=hand.angle; self.stationary=True
            self.scene.begin_grab(key,x,y,hand.scale,hand.angle)
            self.state='PINCH_CONFIRMED'
        elif hand.pinch and self.pinching:
            self.state='DRAGGING'
            self.scene.move_grab(x,y,hand.scale,hand.angle)
            self.depth=float(np.clip(np.log(hand.scale/self.grab_scale)*1.6,-1.8,1.8))
            if np.linalg.norm(np.array([x,y])-self.grab_point)>22 or abs(hand.scale/self.grab_scale-1)>.12 or abs(hand.angle-self.grab_angle)>.2:
                self.stationary=False
            if ENABLE_GESTURE_ISOLATE and self.stationary and now-self.grab_since>1.3 and self.scene.grab and self.scene.grab['kind']=='part':
                self.scene.end_grab(); self.scene.isolate(); self.pinching=False; self.must_release=True
        elif self.pinching:
            self.scene.end_grab(); self.pinching=False; self.owner=None; self.state='IDLE'
