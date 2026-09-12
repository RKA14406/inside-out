"""Launch the native InsideOut prototype (no browser, server or port)."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('INSIDEOUT_START_PERF',str(time.perf_counter()))


def main():
    parser=argparse.ArgumentParser(description='InsideOut native desktop prototype')
    parser.add_argument('--camera',type=int,default=0)
    parser.add_argument('--cpu',action='store_true',help='Use CPU for the visual encoder')
    parser.add_argument('--no-camera',action='store_true',help='Use image files and the object library')
    args=parser.parse_args()
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    root=Path(__file__).resolve().parent
    logs=root/'data'/'logs'; logs.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=logs/'insideout.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from PySide6.QtWidgets import QApplication,QMessageBox
    app=QApplication(sys.argv[:1]); app.setApplicationName('InsideOut'); app.setOrganizationName('InsideOut')
    def exception_hook(kind,error,trace):
        logging.error('Unhandled application exception',exc_info=(kind,error,trace))
        QMessageBox.warning(None,'InsideOut',f'{error}\nDetails saved in data/logs/insideout.log')
    sys.excepthook=exception_hook
    from desktop.window import InsideOutWindow
    window=InsideOutWindow(args.camera,'cpu' if args.cpu else 'auto',not args.no_camera)
    window.show()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
