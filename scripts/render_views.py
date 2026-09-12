"""Build 12 shaded views and 12 contour views from actual cached geometry."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from desktop.geometry import actor_for, add_lights
from desktop.library import read_manifest, save_manifest
from desktop.paths import ASSETS, relative


def render_model(model: dict) -> list[dict]:
    renderer = vtk.vtkRenderer(); renderer.SetBackground(1,1,1)
    for part in model['components']:
        renderer.AddActor(actor_for(part))
    add_lights(renderer)
    window = vtk.vtkRenderWindow(); window.SetOffScreenRendering(1); window.SetShowWindow(False)
    window.SetSize(320,320); window.SetMultiSamples(4); window.AddRenderer(renderer)
    camera = renderer.GetActiveCamera(); camera.ParallelProjectionOn(); camera.SetParallelScale(2.)
    camera.SetFocalPoint(0,0,0); camera.SetViewUp(0,1,0)
    capture = vtk.vtkWindowToImageFilter(); capture.SetInput(window); capture.SetInputBufferTypeToRGB(); capture.ReadFrontBufferOff()
    folder = ASSETS / 'previews' / model['id']; folder.mkdir(parents=True,exist_ok=True)
    views = []
    for index in range(12):
        azimuth = index*30; elevation = 15 if index%2 == 0 else -15
        az, el = math.radians(azimuth), math.radians(elevation)
        camera.SetPosition(7*math.sin(az)*math.cos(el),7*math.sin(el),7*math.cos(az)*math.cos(el))
        renderer.ResetCameraClippingRange(); window.Render(); capture.Modified(); capture.Update()
        raw = capture.GetOutput(); w,h,_ = raw.GetDimensions()
        rgb = np.flipud(vtk_to_numpy(raw.GetPointData().GetScalars()).reshape(h,w,3)).copy()
        gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        edge = cv2.Canny(gray,40,105)
        edge = cv2.dilate(edge,np.ones((2,2),np.uint8))
        for kind, pixels in [('shaded',cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)),('contour',255-edge)]:
            file = folder / f'{index:02d}-{kind}.png'
            cv2.imwrite(str(file), pixels)
            views.append(dict(path=relative(file), angle=f'az {azimuth}, el {elevation}', kind=kind))
    window.Finalize()
    return views


def main():
    models = read_manifest()
    for model in models:
        print('Rendering '+model['name'],flush=True)
        model['previewImages'] = render_model(model)
    save_manifest(models)


if __name__ == '__main__':
    main()
