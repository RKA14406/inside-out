"""Shared VTK actor conversion for the desktop scene and offline rendering."""
from __future__ import annotations

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

from desktop.paths import local


def actor_for(part: dict) -> vtk.vtkActor:
    with np.load(local(part['file']), allow_pickle=False) as data:
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(data['vertices'], deep=True))
        cells = vtk.vtkCellArray()
        faces = data['faces']
        packed = np.column_stack([np.full(len(faces), 3), faces]).astype(np.int64).ravel()
        cells.SetCells(len(faces), numpy_to_vtkIdTypeArray(packed, deep=True))
        poly = vtk.vtkPolyData(); poly.SetPoints(points); poly.SetPolys(cells)
        poly.GetPointData().SetNormals(numpy_to_vtk(data['normals'], deep=True))
        if 'uv' in data:
            poly.GetPointData().SetTCoords(numpy_to_vtk(data['uv'], deep=True))
        if 'colors' in data:
            poly.GetPointData().SetScalars(numpy_to_vtk(data['colors'], deep=True, array_type=vtk.VTK_UNSIGNED_CHAR))
    mapper = vtk.vtkPolyDataMapper(); mapper.SetInputData(poly)
    if poly.GetPointData().GetScalars() is None:
        mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor(); actor.SetMapper(mapper); actor.SetPosition(*part['center'])
    prop = actor.GetProperty(); prop.SetColor(*part['color'][:3])
    prop.SetOpacity(max(.12, part['color'][3])); prop.SetInterpolationToPhong()
    prop.SetAmbient(.22); prop.SetDiffuse(.78); prop.SetSpecular(.3); prop.SetSpecularPower(32)
    if part.get('texture'):
        reader = vtk.vtkPNGReader(); reader.SetFileName(str(local(part['texture']))); reader.Update()
        texture = vtk.vtkTexture(); texture.SetInputConnection(reader.GetOutputPort()); texture.InterpolateOn()
        actor.SetTexture(texture)
    return actor


def add_lights(renderer: vtk.vtkRenderer) -> None:
    renderer.RemoveAllLights()
    for position, intensity, color in [((3,5,7),.85,(1.,.96,.9)),((-4,1,3),.5,(.7,.83,1.)),((0,-3,-4),.65,(.65,1.,.92))]:
        light = vtk.vtkLight(); light.SetLightTypeToSceneLight(); light.SetPosition(*position)
        light.SetFocalPoint(0,0,0); light.SetIntensity(intensity); light.SetColor(*color)
        renderer.AddLight(light)
