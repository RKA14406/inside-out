from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPixmap, QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox

from desktop.paths import local


def pixmap(image):
    if isinstance(image,str):
        return QPixmap(str(local(image)))
    gray=image.ndim==2
    image=np.ascontiguousarray(image)
    format=QImage.Format.Format_Grayscale8 if gray else QImage.Format.Format_RGB888
    return QPixmap.fromImage(QImage(image.data,image.shape[1],image.shape[0],image.strides[0],format).copy())


class LibraryDialog(QDialog):
    def __init__(self, models, parent=None):
        super().__init__(parent); self.setWindowTitle('Object library'); self.resize(590,500); self.chosen=None
        layout=QVBoxLayout(self)
        label=QLabel('Open an object directly to explore its parts. This bypasses sketch retrieval.')
        label.setWordWrap(True); layout.addWidget(label)
        listing=QListWidget(); listing.setIconSize(QSize(105,105)); listing.setSpacing(6)
        for model in models:
            text=f"{model['name']}  /  {model['partCount']} parts\n{model.get('author','')}\n{model['license']}"
            item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,model['id'])
            views=model.get('previewImages',[])
            if views:
                item.setIcon(QIcon(str(local(views[0]['path']))))
            listing.addItem(item)
        layout.addWidget(listing)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Open|QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons); buttons.rejected.connect(self.reject)
        def choose():
            item=listing.currentItem()
            if item:
                self.chosen=item.data(Qt.ItemDataRole.UserRole); self.accept()
        buttons.accepted.connect(choose); listing.itemDoubleClicked.connect(lambda item:choose())


class CandidatesDialog(QDialog):
    def __init__(self, result, models, parent=None):
        super().__init__(parent); self.setWindowTitle('Choose the closest match'); self.resize(650,560); self.chosen=None
        layout=QVBoxLayout(self)
        text=QLabel('The drawing has no clear winner. Choose a candidate or capture again.\nScores are visual similarity, not certainty percentages.')
        text.setWordWrap(True); layout.addWidget(text)
        query=QLabel(); query.setPixmap(pixmap(result['query']).scaled(110,110,Qt.AspectRatioMode.KeepAspectRatio)); layout.addWidget(query)
        for candidate in result['candidates']:
            model=models[candidate['id']]
            button=QPushButton(f"{model['name']}  /  similarity {candidate['score']:.3f}\n{model['partCount']} parts  /  {model['license']}  /  {candidate['angle']}")
            button.setIcon(QIcon(str(local(candidate['view'])))); button.setIconSize(QSize(90,90)); button.setMinimumHeight(96)
            button.clicked.connect(lambda checked=False,key=candidate['id']: self.choose(key)); layout.addWidget(button)
        cancel=QPushButton('Capture again'); cancel.clicked.connect(self.reject); layout.addWidget(cancel)

    def choose(self,key):
        self.chosen=key; self.accept()
