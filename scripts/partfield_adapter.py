"""Optional offline PartField runner and hierarchy importer; never used by the UI.

Run this adapter with InsideOut's Python. --python selects a separately installed
official PartField environment. Only processed input geometry receives face labels:
the upstream loader may change the original mesh, so labels must not be applied
blindly to the original GLB.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import trimesh

from desktop.library import identifier
from desktop.paths import ROOT


def export_hierarchy(mesh_path, label_paths, destination, metadata):
    mesh=trimesh.load(mesh_path,force='mesh',process=False)
    if not isinstance(mesh,trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError('PartField processed input must contain triangle faces.')
    levels=[]
    for path in label_paths:
        raw=np.load(path,allow_pickle=False).reshape(-1)
        if len(raw)!=len(mesh.faces) or not np.isfinite(raw).all() or not np.equal(raw,np.floor(raw)).all():
            raise ValueError(f'{path.name}: expected one integer cluster label per processed face.')
        levels.append(raw.astype(np.int64))
    levels.sort(key=lambda labels:len(np.unique(labels)))
    if not levels or len(np.unique(levels[-1]))<2:
        raise ValueError('Need a segmentation with at least two parts.')
    scene=trimesh.Scene(base_frame='assembly')
    previous=None
    for depth,labels in enumerate(levels):
        for label in np.unique(labels):
            mask=labels==label
            name=f'partfield_level_{depth+1}_cluster_{int(label)}'
            parent='assembly'
            if previous is not None:
                owners=np.unique(previous[mask])
                if len(owners)!=1:
                    raise ValueError('Clustering levels are not nested. Use agglomerative outputs from the same run.')
                parent=f'partfield_level_{depth}_cluster_{int(owners[0])}'
            scene.graph.update(frame_from=parent,frame_to=name,matrix=np.eye(4))
            if depth==len(levels)-1:
                piece=mesh.submesh([np.flatnonzero(mask)],append=True,repair=False)
                scene.add_geometry(piece,node_name=name+'_mesh',geom_name=name,parent_node_name=name)
        previous=labels
    destination.mkdir(parents=True,exist_ok=False)
    output=destination/'segmented.glb'
    scene.export(output,file_type='glb')
    record=dict(metadata)
    record.update(id=identifier(destination.name),name=metadata.get('name','Imported object')+' / PartField',
                  semanticParts=False,segmentation='PartField agglomerative hierarchy; geometric labels only',
                  modifications='Segmented the PartField processed input mesh. No internal geometry or semantic anatomy invented.',
                  segmentationSource='https://github.com/nv-tlabs/PartField',
                  labelFiles=[str(p.resolve()) for p in label_paths],processedMesh=str(mesh_path.resolve()))
    record.setdefault('license','Unspecified - verify input asset rights before sharing')
    record.setdefault('author','Unspecified')
    (destination/'metadata.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Segmented GLB prepared: '+str(output))
    print('Add it to InsideOut with:')
    print(f'  "{sys.executable}" scripts/ingest_models.py "{destination}"')


def run(args):
    repo=args.repo.resolve(); python=args.python.resolve(); checkpoint=args.checkpoint.resolve()
    for required in (repo/'partfield_inference.py',repo/'run_part_clustering.py',repo/'configs/final/demo.yaml',python,checkpoint,args.input):
        if not required.is_file():
            raise FileNotFoundError(f'Missing {required}. See docs/OFFLINE_CV.md for the separate environment.')
    run_id='insideout'+uuid.uuid4().hex[:12]
    folder=ROOT/'data'/'partfield'/run_id
    source_dir=folder/'input'; source_dir.mkdir(parents=True,exist_ok=False)
    # Self-contained GLB staging avoids external OBJ material and GLTF URI issues.
    asset=trimesh.load_scene(args.input,process=False)
    asset.export(source_dir/'asset.glb',file_type='glb')
    feature_name='partfield_features/'+run_id
    feature_dir=repo/'exp_results'/feature_name
    cluster_dir=folder/'clusters'
    commands=[
        [str(python),'partfield_inference.py','-c','configs/final/demo.yaml','--opts',
         'continue_ckpt',str(checkpoint),'result_name',feature_name,'dataset.data_path',str(source_dir)],
        [str(python),'run_part_clustering.py','--root',str(feature_dir),'--dump_dir',str(cluster_dir),
         '--source_dir',str(source_dir),'--use_agglo','True','--max_num_clusters',str(max(args.levels)),
         '--option','0'],
    ]
    (folder/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
    for command in commands:
        subprocess.run(command,cwd=repo,check=True)
    processed=feature_dir/'input_asset_0.ply'
    labels=[cluster_dir/'cluster_out'/f'asset_0_{level:02d}.npy' for level in sorted(set(args.levels))]
    # Preserve the exact mesh whose face order the upstream clustering used.
    shutil.copy2(processed,folder/'processed-input.ply')
    metadata=read_metadata(args.metadata)
    metadata.setdefault('source',str(args.input.resolve()))
    destination=args.output or ROOT/'assets'/'import'/(identifier(args.input.stem)+'_parts_'+run_id[-6:])
    export_hierarchy(folder/'processed-input.ply',labels,destination.resolve(),metadata)


def read_metadata(path):
    return json.loads(path.read_text(encoding='utf-8')) if path else {}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    runner=commands.add_parser('run',help='Run an existing separate PartField installation, then export GLB')
    runner.add_argument('input',type=Path)
    runner.add_argument('--repo',type=Path,required=True)
    runner.add_argument('--python',type=Path,required=True,help='Python executable in the PartField environment')
    runner.add_argument('--checkpoint',type=Path,required=True)
    runner.add_argument('--levels',type=int,nargs='+',default=[2,4,8])
    runner.add_argument('--metadata',type=Path)
    runner.add_argument('--output',type=Path,help='New destination directory; existing directories are not overwritten')
    importer=commands.add_parser('import',help='Import outputs from a PartField run performed elsewhere')
    importer.add_argument('--mesh',type=Path,required=True,help='input_<id>_0.ply from the SAME feature run')
    importer.add_argument('--labels',type=Path,nargs='+',required=True)
    importer.add_argument('--metadata',type=Path)
    importer.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='run':
        if any(level<2 or level>64 for level in args.levels):
            parser.error('Choose cluster counts between 2 and 64.')
        run(args)
    else:
        export_hierarchy(args.mesh,args.labels,args.output.resolve(),read_metadata(args.metadata))


if __name__=='__main__':
    main()
