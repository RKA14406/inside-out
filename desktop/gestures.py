"""Smoothed, temporally confirmed gestures from all 21 MediaPipe landmarks."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from desktop.config import (
    ONE_EURO_BETA, ONE_EURO_D_CUTOFF, ONE_EURO_MIN_CUTOFF,
    PINCH_CONFIRMATION_SECONDS, PINCH_ENTER_THRESHOLD, PINCH_RELEASE_THRESHOLD,
    POINT_CONFIRMATION_SECONDS, RESET_DWELL_SECONDS,
)


class OneEuroLandmarkFilter:
    """Adaptive low-pass filter: steady hands are stable, fast motion stays responsive."""
    def __init__(self, value: np.ndarray, timestamp: float):
        self.value=np.asarray(value,dtype=float).copy()
        self.derivative=np.zeros_like(self.value)
        self.timestamp=timestamp

    @staticmethod
    def alpha(cutoff, dt):
        tau=1/(2*np.pi*np.maximum(cutoff,1e-6))
        return 1/(1+tau/max(dt,1e-6))

    def update(self, raw: np.ndarray, timestamp: float) -> np.ndarray:
        dt=float(np.clip(timestamp-self.timestamp,.005,.2))
        raw=np.asarray(raw,dtype=float)
        derivative=(raw-self.value)/dt
        da=self.alpha(ONE_EURO_D_CUTOFF,dt)
        self.derivative=da*derivative+(1-da)*self.derivative
        cutoff=ONE_EURO_MIN_CUTOFF+ONE_EURO_BETA*np.abs(self.derivative)
        a=self.alpha(cutoff,dt)
        self.value=a*raw+(1-a)*self.value
        self.timestamp=timestamp
        return self.value.copy()


@dataclass
class Hand:
    identity: str
    points: np.ndarray
    world: np.ndarray | None
    x: float
    y: float
    scale: float
    pinch_distance: float
    pinch: bool
    point: bool
    palm: bool
    angle: float


@dataclass
class GestureFrame:
    hands: list[Hand] = field(default_factory=list)
    reset: bool = False
    timestamp: float = 0.
    label: str = 'No hands / mouse available'


class GestureEngine:
    def __init__(self):
        self.states = {}
        self.palm_since = None
        self.reset_latched = False
        self.last_reset = -100.

    def update(self, detected: list[dict], now: float) -> GestureFrame:
        output = []
        used = set()
        for hand in detected[:2]:
            identity = hand['identity']
            if identity in used:
                identity += '-2'
            used.add(identity)
            raw = np.asarray(hand['points'],dtype=float)
            old = self.states.get(identity)
            if old is None or now-old['seen'] > .3:
                old = dict(filter=OneEuroLandmarkFilter(raw,now), seen=now,
                           pinch=False, candidate=False, since=now, point_since=now)
            smooth = old['filter'].update(raw,now)
            scale = max(float(np.linalg.norm(smooth[0,:2]-smooth[9,:2])), .015)
            ratio = float(np.linalg.norm(smooth[4,:2]-smooth[8,:2]))/scale
            wanted = ratio < (PINCH_RELEASE_THRESHOLD if old['pinch'] else PINCH_ENTER_THRESHOLD)
            if wanted != old['candidate']:
                old['candidate'] = wanted; old['since'] = now
            if now-old['since'] >= PINCH_CONFIRMATION_SECONDS:
                old['pinch'] = wanted
            extended = [np.linalg.norm(smooth[tip,:2]-smooth[0,:2]) > np.linalg.norm(smooth[tip-2,:2]-smooth[0,:2])*1.12 for tip in (8,12,16,20)]
            is_point = extended[0] and sum(extended[1:]) <= 1
            if not is_point:
                old['point_since'] = now
            point = is_point and now-old['point_since'] > POINT_CONFIRMATION_SECONDS
            palm = all(extended) and ratio > .6
            angle = math.atan2(smooth[5,1]-smooth[17,1], smooth[5,0]-smooth[17,0])
            output.append(Hand(identity,smooth,hand.get('world'),float(smooth[8,0]),float(smooth[8,1]),scale,ratio,old['pinch'],point,palm,angle))
            old.update(seen=now)
            self.states[identity] = old
        self.states = {key:value for key,value in self.states.items() if now-value['seen'] < .35}
        # Reset needs exactly one open palm held for 1.2 seconds. Two open hands spread.
        resetting = len(output)==1 and output[0].palm
        reset = False
        if resetting:
            if self.palm_since is None:
                self.palm_since = now
            if now-self.palm_since > RESET_DWELL_SECONDS and not self.reset_latched and now-self.last_reset > 2.:
                reset=True; self.reset_latched=True; self.last_reset=now
        else:
            self.palm_since=None; self.reset_latched=False
        label = 'No hands / mouse available'
        if len(output)==2:
            label='Two hands / spread to explode'
        elif output:
            label='Pinch / grab' if output[0].pinch else 'Point / select' if output[0].point else 'Hold palm to reassemble' if output[0].palm else 'Hand detected'
        return GestureFrame(output,reset,now,label)
