from __future__ import annotations

import queue
import time

from PySide6.QtCore import QThread, Signal
from desktop.performance import record


class RetrievalWorker(QThread):
    ready=Signal(str)
    result=Signal(int,object)
    error=Signal(int,str)

    def __init__(self,device='auto',parent=None):
        super().__init__(parent)
        self.device=device; self.jobs=queue.Queue(maxsize=1)

    def submit(self, token, image):
        if self.jobs.full():
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                pass
        if isinstance(image, list):
            payload=[{**region,'image':region['image'].copy()} for region in image]
        else:
            payload=image.copy()
        self.jobs.put_nowait((token,payload))

    def run(self):
        started=time.perf_counter()
        try:
            from desktop.encoder import Retriever
            retriever=Retriever(self.device)
        except Exception as exc:
            self.error.emit(-1,str(exc))
            return
        record('encoder_load_ms',(time.perf_counter()-started)*1000,detail=self.device)
        self.ready.emit(retriever.mode)
        while not self.isInterruptionRequested():
            try:
                token,image=self.jobs.get(timeout=.25)
            except queue.Empty:
                continue
            try:
                self.result.emit(token,retriever.retrieve(image))
            except Exception as exc:
                self.error.emit(token,str(exc))
