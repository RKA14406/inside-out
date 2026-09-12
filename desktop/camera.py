"""Latest-frame camera, paper, and hand workers with no stale-frame queues."""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from desktop.gestures import GestureEngine, GestureFrame
from desktop.paper import StablePaper, detect_paper
from desktop.performance import record


class _LatestProcessor:
    """One-slot worker: a new frame replaces any unprocessed older frame."""
    def __init__(self):
        self.condition=threading.Condition()
        self.pending=None
        self.latest=None
        self.stopping=False
        self.thread=threading.Thread(target=self.run,daemon=True)

    def start(self):
        self.thread.start()

    def submit(self, frame, captured_at):
        with self.condition:
            self.pending=(frame,captured_at)
            self.condition.notify()

    def next_frame(self):
        with self.condition:
            while self.pending is None and not self.stopping:
                self.condition.wait(.25)
            if self.stopping:
                return None
            item=self.pending; self.pending=None
            return item

    def take_latest(self):
        with self.condition:
            return self.latest

    def publish(self, value):
        with self.condition:
            self.latest=value

    def stop(self):
        with self.condition:
            self.stopping=True; self.condition.notify_all()
        self.thread.join(timeout=2.)


class _PaperProcessor(_LatestProcessor):
    def __init__(self, metrics):
        super().__init__(); self.metrics=metrics; self.stability=StablePaper()

    def run(self):
        while True:
            item=self.next_frame()
            if item is None:
                return
            frame,captured_at=item
            started=time.perf_counter()
            try:
                paper=self.stability.update(detect_paper(frame),frame.shape)
                duration=(time.perf_counter()-started)*1000
                self.metrics['paperMs']=duration
                record('camera_paper_ms',duration)
                self.publish((paper,captured_at))
            except Exception as exc:
                self.metrics['paperError']=str(exc)


class _HandProcessor(_LatestProcessor):
    def __init__(self, metrics, notice):
        super().__init__(); self.metrics=metrics; self.notice=notice
        self.engine=GestureEngine()

    def run(self):
        tracker=None
        try:
            try:
                import mediapipe as mp
                tracker=mp.solutions.hands.Hands(
                    static_image_mode=False,max_num_hands=2,model_complexity=0,
                    min_detection_confidence=.6,min_tracking_confidence=.6)
                self.notice('Hand tracking ready')
            except Exception as exc:
                self.notice(f'Hand tracking unavailable: {exc}. Mouse controls remain available.')
                return
            rate_since=time.perf_counter(); processed=0; landmark_updates=0
            while True:
                item=self.next_frame()
                if item is None:
                    return
                frame,captured_at=item
                ratio=640/frame.shape[1]
                rgb=cv2.cvtColor(cv2.resize(frame,(640,max(1,round(frame.shape[0]*ratio)))),cv2.COLOR_BGR2RGB)
                started=time.perf_counter()
                try:
                    detected=tracker.process(rgb)
                except Exception as exc:
                    self.notice(f'Hand tracker stopped: {exc}')
                    return
                duration=(time.perf_counter()-started)*1000
                hands=[]
                for index,landmarks in enumerate(detected.multi_hand_landmarks or []):
                    world=detected.multi_hand_world_landmarks[index] if detected.multi_hand_world_landmarks else None
                    identity=detected.multi_handedness[index].classification[0].label
                    hands.append(dict(
                        identity=identity,
                        points=np.array([[p.x,p.y,p.z] for p in landmarks.landmark]),
                        world=np.array([[p.x,p.y,p.z] for p in world.landmark]) if world else None,
                    ))
                now=time.monotonic()
                gestures=self.engine.update(hands,now)
                processed+=1
                if hands:
                    landmark_updates+=1
                elapsed=time.perf_counter()-rate_since
                self.metrics['handInferenceMs']=duration
                self.metrics['handLatencyMs']=(time.monotonic()-captured_at)*1000
                if elapsed>=1.:
                    self.metrics['handInferenceFps']=processed/elapsed
                    self.metrics['landmarkUpdateFps']=landmark_updates/elapsed
                    record('hand_tracking_fps',processed/elapsed,'fps')
                    if hands:
                        record('landmark_update_fps',landmark_updates/elapsed,'fps','visible hand')
                    processed=0; landmark_updates=0; rate_since=time.perf_counter()
                record('hand_inference_ms',duration)
                self.publish((gestures,captured_at))
        finally:
            if tracker is not None:
                tracker.close()


class CameraWorker(QThread):
    notice = Signal(str)

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index=camera_index
        self.lock=threading.Lock()
        self.latest=None
        self.serial=0
        self.metrics={}

    def take_latest(self):
        with self.lock:
            return self.latest

    def run(self):
        capture=None; hand_worker=None; paper_worker=None
        try:
            capture=cv2.VideoCapture(self.camera_index,cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release(); capture=cv2.VideoCapture(self.camera_index)
            if not capture.isOpened():
                self.notice.emit('Camera unavailable. Open a drawing image or choose an object from Library.')
                return
            # This webcam exposes its higher-rate mode at VGA. MediaPipe and the
            # paper detector already operate at 640 px, so larger capture only
            # adds latency and can force a low-FPS USB mode.
            capture.set(cv2.CAP_PROP_FRAME_WIDTH,640); capture.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
            capture.set(cv2.CAP_PROP_FPS,30); capture.set(cv2.CAP_PROP_BUFFERSIZE,1)
            hand_worker=_HandProcessor(self.metrics,self.notice.emit); hand_worker.start()
            paper_worker=_PaperProcessor(self.metrics); paper_worker.start()
            camera_since=time.perf_counter(); camera_frames=0; last_paper_submit=0.
            gestures=GestureFrame(); paper=None
            while not self.isInterruptionRequested():
                ok,frame=capture.read()
                if not ok:
                    self.notice.emit('Camera disconnected. Use Open drawing or reconnect the camera.')
                    break
                frame=cv2.flip(frame,1)
                captured_at=time.monotonic()
                camera_frames+=1
                elapsed=time.perf_counter()-camera_since
                if elapsed>=1.:
                    self.metrics['cameraFps']=camera_frames/elapsed
                    record('camera_capture_fps',camera_frames/elapsed,'fps',f'camera {self.camera_index}')
                    camera_frames=0; camera_since=time.perf_counter()
                hand_worker.submit(frame,captured_at)
                if captured_at-last_paper_submit>=.10:
                    paper_worker.submit(frame,captured_at); last_paper_submit=captured_at
                hand_result=hand_worker.take_latest()
                if hand_result is not None:
                    gestures=hand_result[0]
                paper_result=paper_worker.take_latest()
                if paper_result is not None:
                    paper=paper_result[0]
                with self.lock:
                    self.serial+=1
                    self.latest=(self.serial,frame,paper,gestures)
                self.msleep(1)
        except Exception as exc:
            self.notice.emit(f'Camera error: {exc}')
        finally:
            if hand_worker is not None:
                hand_worker.stop()
            if paper_worker is not None:
                paper_worker.stop()
            if capture is not None:
                capture.release()
