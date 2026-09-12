"""GLB/GLTF/OBJ ingestion and an on-disk, part-aware scene format."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import trimesh

from desktop.paths import ASSETS, MANIFEST, local, relative


def identifier(text: str) -> str:
    return re.sub(r'[^a-z0-9_-]+', '_', text.lower()).strip('_')[:65] or 'model'


def node_id(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def readable(name: str) -> str:
    name = re.sub(r'^(VH_[MF]_?|VHMaleOrgans_?)', '', name)
    return re.sub(r'[_|]+', ' ', name).strip() or 'Mesh'


def read_manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else []


def save_manifest(models: list[dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temp = MANIFEST.with_suffix('.json.partial')
    temp.write_text(json.dumps(models, indent=2), encoding='utf-8')
    temp.replace(MANIFEST)


def ingest(path: Path, source: dict) -> dict:
    scene = trimesh.load_scene(path, process=False)
    if not scene.geometry:
        raise ValueError(f'{path.name} contains no mesh geometry')
    model_id = identifier(source.get('id', path.stem))
    folder = ASSETS / 'cache' / model_id
    folder.mkdir(parents=True, exist_ok=True)
    # Some valid GLBs exported by trimesh include an identity base-frame edge.
    # Never turn that harmless self-edge into a recursive hierarchy.
    raw_parent = {str(child): str(parent) for parent, child, _ in scene.graph.to_edgelist()
                  if str(child) != str(parent)}
    nodes = {}
    root_name = str(scene.graph.base_frame)
    for name in scene.graph.nodes:
        name = str(name)
        key = node_id(name)
        nodes[key] = dict(id=key, name=readable(name), sourceName=name,
                          parent=node_id(raw_parent[name]) if name in raw_parent else None,
                          children=[], part=None)
    root_key = node_id(root_name)
    meshes = []
    # GLTF convention is Y-up. OBJ has no guaranteed up-axis; a sidecar can
    # declare Z-up or provide explicit XYZ degrees, without guessing anatomy.
    orientation=np.eye(4)
    if source.get('upAxis','Y').upper()=='Z':
        orientation=trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0])
    rotation=source.get('defaultRotation',[0,0,0])
    if len(rotation)!=3 or not np.isfinite(rotation).all():
        raise ValueError('defaultRotation must be three finite XYZ angles in degrees')
    orientation=trimesh.transformations.euler_matrix(*np.radians(rotation))@orientation
    for name in scene.graph.nodes_geometry:
        matrix, geom_name = scene.graph[name]
        geom = scene.geometry[geom_name].copy()
        if not isinstance(geom, trimesh.Trimesh) or not len(geom.faces):
            continue
        geom.apply_transform(orientation@matrix)
        if not np.isfinite(geom.vertices).all():
            raise ValueError(f'Non-finite geometry: {name}')
        meshes.append((str(name), geom))
    if not meshes:
        raise ValueError('No triangle meshes in asset')
    bounds = np.array([[m.bounds[0] for _,m in meshes], [m.bounds[1] for _,m in meshes]])
    lo, hi = bounds[0].min(0), bounds[1].max(0)
    center = (lo+hi)/2
    scale = 3.0 / max(float(np.max(hi-lo)), 1e-8)
    parts = []
    split_count = 0
    for name, mesh in meshes:
        parent_key = node_id(name)
        pieces = [mesh]
        if len(meshes) == 1:
            groups = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)), min_len=20)
            if 1 < len(groups) <= 64:
                covered = np.concatenate(groups)
                remainder = np.setdiff1d(np.arange(len(mesh.faces)), covered)
                groups = list(groups) + ([remainder] if len(remainder) else [])
                pieces = [mesh.submesh([g], append=True, repair=False) for g in groups]
                split_count = len(pieces)
        for part_index, piece in enumerate(pieces):
            label = name if len(pieces) == 1 else f'{name} / geometric component {part_index+1}'
            key = node_id(label + '/mesh')
            nodes[key] = dict(id=key, name=readable(label), sourceName=label, parent=parent_key, children=[], part=key)
            vertices = (np.asarray(piece.vertices)-center)*scale
            part_center = (vertices.min(0)+vertices.max(0))/2
            arrays = dict(vertices=(vertices-part_center).astype(np.float32),
                          faces=np.asarray(piece.faces, dtype=np.int64),
                          normals=np.asarray(piece.vertex_normals, dtype=np.float32))
            color = [0.65, 0.71, 0.75, 1.0]
            texture = None
            visual = piece.visual
            mat = getattr(visual, 'material', None)
            if mat is not None:
                base = getattr(mat, 'baseColorFactor', None)
                if base is None:
                    base = getattr(mat, 'diffuse', None)
                if base is not None:
                    base = np.asarray(base, dtype=float)
                    if base.max() > 1:
                        base /= 255
                    color = base.tolist()[:4]
                    if len(color)==3:
                        color.append(1.)
                image = getattr(mat, 'baseColorTexture', None)
                if image is None:
                    image = getattr(mat, 'image', None)
                uv = getattr(visual, 'uv', None)
                if image is not None and uv is not None and len(uv) == len(vertices):
                    texture_path = folder / f'{key}.png'
                    image.convert('RGBA').save(texture_path)
                    texture = relative(texture_path)
                    arrays['uv'] = np.asarray(uv, dtype=np.float32)
            elif getattr(visual, 'kind', None) == 'vertex':
                arrays['colors'] = np.asarray(visual.vertex_colors, dtype=np.uint8)
            file = folder / f'{key}.npz'
            np.savez_compressed(file, **arrays)
            part = dict(id=key, name=readable(label), node=key, file=relative(file),
                        center=part_center.tolist(), bounds=[vertices.min(0).tolist(), vertices.max(0).tolist()],
                        radius=float(np.linalg.norm(vertices.max(0)-vertices.min(0))/2),
                        color=color, texture=texture, triangles=len(piece.faces))
            parts.append(part)
    for key, node in nodes.items():
        parent = node['parent']
        if parent in nodes:
            nodes[parent]['children'].append(key)
    part_by_id = {p['id']:p for p in parts}

    def populate(key, depth=0):
        node = nodes[key]
        node['depth'] = depth
        leaves = [node['part']] if node['part'] else []
        for child in node['children']:
            leaves += populate(child, depth+1)
        node['leaves'] = leaves
        if leaves:
            boxes = np.array([part_by_id[p]['bounds'] for p in leaves])
            bmin, bmax = boxes[:,0].min(0), boxes[:,1].max(0)
            node['center'] = ((bmin+bmax)/2).tolist()
            node['radius'] = float(np.linalg.norm(bmax-bmin)/2)
        return leaves

    populate(root_key)
    nodes = {key:node for key,node in nodes.items() if node.get('leaves')}
    for node in nodes.values():
        node['children'] = [key for key in node['children'] if key in nodes]
    metadata = dict(source, id=model_id, root=root_key, nodes=nodes, components=parts,
                    parts=len(parts)>1, partCount=len(parts), hierarchy=any(len(n['children'])>1 for n in nodes.values()),
                    hierarchyDepth=max(n['depth'] for n in nodes.values()), scale=scale,
                    originalCenter=center.tolist(), defaultRotation=rotation, geometrySplit=split_count > 0,
                    semanticParts=bool(source.get('semanticParts', False)) and not split_count,
                    previewImages=[], embeddingFile='data/model_index/desktop.npz',
                    explode=source.get('explode', dict(mode='hierarchical', axisOverrides={})))
    cache = folder / 'scene.json'
    cache.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    metadata['cache'] = relative(cache)
    return metadata
