"""Opt-in validation timings. No frame/image recording or runtime dependencies."""
from __future__ import annotations

import atexit
import csv
import os
import threading
import time
from pathlib import Path

_path=os.environ.get('INSIDEOUT_PERF_FILE')
_lock=threading.Lock()
_rows=[]
START=float(os.environ.get('INSIDEOUT_START_PERF',time.perf_counter()))


def record(metric,value,unit='ms',detail=''):
    if _path:
        with _lock:
            _rows.append((os.getpid(),time.perf_counter(),metric,float(value),unit,str(detail)))


def flush():
    if not _path:
        return
    with _lock:
        pending=_rows[:]; _rows.clear()
    if not pending:
        return
    try:
        path=Path(_path); path.parent.mkdir(parents=True,exist_ok=True)
        exists=path.exists() and path.stat().st_size>0
        with path.open('a',newline='',encoding='utf-8') as stream:
            writer=csv.writer(stream)
            if not exists:
                writer.writerow(['pid','perf_counter','metric','value','unit','detail'])
            writer.writerows(pending)
    except OSError:
        # Measurement output must not take down the demonstration.
        pass


atexit.register(flush)
