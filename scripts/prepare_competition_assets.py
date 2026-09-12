"""Prepare the two competition display assets without changing the renderer."""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import trimesh

from desktop.library import ingest,read_manifest,save_manifest
from desktop.paths import ASSETS,relative

CAR_URL='https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/glTF-Binary/CarConcept.glb'
CAR_SOURCE='https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarConcept'
CAR_LICENSE='https://github.com/KhronosGroup/glTF-Sample-Assets/blob/main/Models/CarConcept/LICENSE.md'
CAR_LICENSE_RAW='https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/LICENSE.md'
CAR_README_RAW='https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/README.md'
EARTH_CORE_SOURCE='https://sketchfab.com/3d-models/earth-core-v1-4c3ea4018a7442c4b221d91b8f373a55'


def download(url: str,path: Path) -> None:
    if path.exists() and path.stat().st_size: return
    path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix(path.suffix+'.partial')
    request=urllib.request.Request(url,headers={'User-Agent':'InsideOut-local-prototype/1.0'})
    with urllib.request.urlopen(request,timeout=120) as response,temporary.open('wb') as output:
        while chunk:=response.read(1024*1024): output.write(chunk)
    temporary.replace(path)


def material_color(mesh: trimesh.Trimesh) -> np.ndarray:
    material=getattr(mesh.visual,'material',None); base=getattr(material,'baseColorFactor',None)
    if base is None: base=getattr(material,'diffuse',None)
    if base is None: return np.array([165,180,190,255],dtype=np.uint8)
    base=np.asarray(base,dtype=float)
    if base.max()<=1: base*=255
    if len(base)==3: base=np.append(base,255)
    return np.clip(base[:4],0,255).astype(np.uint8)


def prepare_car(original: Path,target: Path) -> dict:
    scene=trimesh.load_scene(original,process=False)
    parent={str(child):str(root) for root,child,_ in scene.graph.to_edgelist()}

    def ancestry(name):
        result=[name]
        while result[-1] in parent and len(result)<32: result.append(parent[result[-1]])
        return result

    def group(name):
        lineage=ancestry(name)
        tests=[('Front Left Wheel',('WheelFrontL',)),('Front Right Wheel',('WheelFrontR',)),
               ('Rear Left Wheel',('WheelRearL',)),('Rear Right Wheel',('WheelRearR',)),
               ('Hood',('BodyHood',)),('Left Door',('BodyDoorLColor1',)),('Right Door',('BodyDoorRColor1',)),
               ('Rear Hatch',('BodyRearPanelsColor1',))]
        for label,prefixes in tests:
            if any(any(item.startswith(prefix) for prefix in prefixes) for item in lineage): return label
        joined=' '.join(lineage).lower()
        if any(word in joined for word in ('interior','seat','steering','pedal','gearstick','floormat')): return 'Interior'
        if any(word in name.lower() for word in ('engine','axle','driveshaft','brake','radiator','exhaust')): return 'Mechanical'
        return 'Body'

    grouped={}
    excluded=[]
    for name in scene.graph.nodes_geometry:
        if 'emblem' in str(name).lower() or 'logo' in str(name).lower():
            excluded.append(str(name)); continue
        matrix,geometry_name=scene.graph[name]; mesh=scene.geometry[geometry_name].copy()
        if not isinstance(mesh,trimesh.Trimesh) or not len(mesh.faces): continue
        mesh.apply_transform(matrix)
        rgba=material_color(mesh); mesh.visual=trimesh.visual.ColorVisuals(mesh=mesh,vertex_colors=np.tile(rgba,(len(mesh.vertices),1)))
        grouped.setdefault(group(str(name)),[]).append(mesh)
    prepared=trimesh.Scene()
    preferred=['Body','Hood','Left Door','Right Door','Rear Hatch','Interior','Mechanical',
               'Front Left Wheel','Front Right Wheel','Rear Left Wheel','Rear Right Wheel']
    for label in preferred:
        meshes=grouped.get(label,[])
        if meshes: prepared.add_geometry(trimesh.util.concatenate(meshes),node_name=label,geom_name=label)
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(prepared.export(file_type='glb'))
    return dict(groups=[label for label in preferred if grouped.get(label)],excluded=excluded,
                sourceMeshes=len(scene.geometry),sourceNodes=len(scene.graph.nodes),
                triangles=sum(len(mesh.faces) for meshes in grouped.values() for mesh in meshes))


def cutaway_sphere(radius: float,color: tuple[int,int,int,int],surface=False) -> trimesh.Trimesh:
    mesh=trimesh.creation.icosphere(subdivisions=4 if surface else 3,radius=radius)
    centers=mesh.triangles_center
    # Remove one 75-degree wedge so the nested layers remain visible together.
    angle=np.arctan2(centers[:,1],centers[:,0]); keep=~((angle>-.68)&(angle<.68)&(centers[:,0]>0))
    mesh.update_faces(keep); mesh.remove_unreferenced_vertices()
    colors=np.tile(np.asarray(color,dtype=np.uint8),(len(mesh.vertices),1))
    if surface:
        points=mesh.vertices/max(radius,1e-8); lon=np.arctan2(points[:,1],points[:,0]); lat=np.arcsin(points[:,2])
        field=np.sin(lon*2.1)+.62*np.cos(lat*5.2)+.48*np.sin(lon*4.3+lat*2.4)
        land=(field>.48)&(np.abs(lat)<1.30)
        colors[land]=np.array([72,145,76,255],dtype=np.uint8)
    mesh.visual=trimesh.visual.ColorVisuals(mesh=mesh,vertex_colors=colors)
    return mesh


def prepare_earth(target: Path) -> dict:
    scene=trimesh.Scene()
    layers=[('Surface / Crust',1.00,(44,112,190,255),True),('Mantle',.82,(226,102,45,255),False),
            ('Outer Core',.53,(246,181,55,255),False),('Inner Core',.28,(255,232,132,255),False)]
    for name,radius,color,surface in layers:
        scene.add_geometry(cutaway_sphere(radius,color,surface),node_name=name,geom_name=name)
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(scene.export(file_type='glb'))
    return dict(layers=[name for name,_,_,_ in layers],triangles=sum(len(g.faces) for g in scene.geometry.values()))


def metadata_file(folder: Path,data: dict) -> None:
    data={**data,'downloadDate':datetime.date.today().isoformat()}
    (folder/'metadata.json').write_text(json.dumps(data,indent=2),encoding='utf-8')


def main() -> None:
    car_folder=ASSETS/'sources'/'toy_car'; car_original=car_folder/'CarConcept-original.glb'; car_file=car_folder/'toy_car.glb'
    download(CAR_URL,car_original); download(CAR_LICENSE_RAW,car_folder/'SOURCE_LICENSE.md')
    download(CAR_README_RAW,car_folder/'SOURCE_README.md'); car_info=prepare_car(car_original,car_file)
    car_source=dict(id='toy_car',name='Car',category='Mechanics',author='Eric Chadwick / Darmstadt Graphics Group GmbH; Khronos Group',
                    license='CC-BY-4.0',licenseUrl='https://creativecommons.org/licenses/by/4.0/',source=CAR_SOURCE,url=CAR_URL,
                    licenseText=CAR_LICENSE,semanticParts=True,file=relative(car_file),sourceFile=relative(car_original),
                    sha256=hashlib.sha256(car_original.read_bytes()).hexdigest(),bytes=car_original.stat().st_size,
                    modifications='Grouped 109 imported geometry instances into meaningful runtime assemblies; textures omitted and logo/emblem nodes excluded so Khronos/DGG marks are not displayed.',
                    runtimeGroups=car_info['groups'],excludedNodes=car_info['excluded'])
    metadata_file(car_folder,car_source)

    earth_folder=ASSETS/'sources'/'earth'; earth_file=earth_folder/'earth.glb'; earth_info=prepare_earth(earth_file)
    earth_source=dict(id='earth',name='Earth',category='Planet / geology',author='InsideOut project',license='CC0-1.0',
                      licenseUrl='https://creativecommons.org/publicdomain/zero/1.0/',source='Local procedural fallback',
                      requestedPrimarySource=EARTH_CORE_SOURCE,semanticParts=True,file=relative(earth_file),
                      sha256=hashlib.sha256(earth_file.read_bytes()).hexdigest(),bytes=earth_file.stat().st_size,
                      modifications='Four lightweight cutaway layers with a stylized blue/green surface. Used because official Sketchfab download required an unavailable logged-in account.',
                      layerNames=earth_info['layers'],explode=dict(mode='hierarchical',axisOverrides={
                          'Surface / Crust':[1,0,0],'Mantle':[.35,.55,0],'Outer Core':[-.35,-.55,0],'Inner Core':[-1,0,0]}))
    metadata_file(earth_folder,earth_source)

    replacements={item['id']:ingest(Path(item['file']),item) for item in (car_source,earth_source)}
    manifest=[replacements.get(model['id'],model) for model in read_manifest()]
    for model_id,model in replacements.items():
        if not any(item['id']==model_id for item in manifest): manifest.append(model)
    save_manifest(manifest)
    sources_file=ASSETS/'sources.json'
    sources=json.loads(sources_file.read_text(encoding='utf-8')) if sources_file.exists() else []
    sources=[item for item in sources if item.get('id') not in {'toy_car','earth'}]+[car_source,earth_source]
    sources_file.write_text(json.dumps(sources,indent=2),encoding='utf-8')
    print(json.dumps({'car':car_info,'earth':earth_info},indent=2))


if __name__=='__main__': main()
