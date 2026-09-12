# Optional offline CV integrations

## Why OpenCLIP is the runtime baseline

[OpenCLIP](https://github.com/mlfoundations/open_clip) offers a practical local image encoder whose views can be indexed in advance. The prepared [ViT-B-32 LAION checkpoint](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K) is approximately 605 MB on disk. The runtime drops the text tower and encodes only captured drawings. CUDA is selected when available, with CPU operation supported.

This choice is an engineering baseline, not a claim that it beats sketch-specialized systems. Accuracy on physical hand drawings is untested. Adding a second encoder would require separately indexed vectors and evidence that the extra memory/latency helps; no unmeasured ensemble was installed.

## PartField: adapter implemented, upstream environment not installed

Optional experimental adapter implemented but not validated or required by the competition MVP.

The [official NVIDIA PartField implementation](https://github.com/nv-tlabs/PartField) uses Python 3.10, PyTorch 2.4, CUDA 12.4, and additional geometry/native packages, including torch-scatter. The current InsideOut environment is Python 3.12 with its own CUDA-enabled PyTorch. Keep these environments separate; do not install the upstream dependency list over the desktop environment.

An adapter is provided at `scripts/partfield_adapter.py`. It has two modes:

1. `run`: stage a self-contained GLB, invoke a separately installed upstream feature-extraction script and agglomerative clustering script, then import the segmentation.
2. `import`: import the exact processed mesh and face labels from a PartField run performed elsewhere, including Linux/WSL.

Neither mode runs during application startup. Neither has been executed in this build. Install the official toolchain and obtain its [Objaverse-trained checkpoint](https://huggingface.co/mikaelaangel/partfield-ckpt/blob/main/model_objaverse.ckpt) separately before using `run`. Memory needs depend on the asset; successful execution on the 4 GB laptop GPU is not established.

Example command structure (replace upstream installation/checkpoint paths with real locations):

```powershell
.\.venv-desktop\Scripts\python.exe scripts/partfield_adapter.py run assets/import/object/model.glb --repo C:\tools\PartField --python C:\tools\partfield-env\python.exe --checkpoint C:\tools\PartField\model\model_objaverse.ckpt --metadata assets/import/object/metadata.json --levels 2 4 8
```

The adapter uses a unique job folder under `data/partfield/`, writes feature outputs to a unique `exp_results/partfield_features/insideout...` folder in the selected upstream checkout, and never overwrites an existing output-model folder. It retains command arguments and the processed input mesh. An upstream failure propagates; there is no synthetic segmentation fallback.

To import outputs made on another machine:

```powershell
.\.venv-desktop\Scripts\python.exe scripts/partfield_adapter.py import --mesh data/partfield/job/input_asset_0.ply --labels data/partfield/job/asset_0_02.npy data/partfield/job/asset_0_04.npy data/partfield/job/asset_0_08.npy --metadata assets/import/object/metadata.json --output assets/import/object_segmented
.\.venv-desktop\Scripts\python.exe scripts/ingest_models.py assets/import/object_segmented
```

Use the `input_<id>_0.ply` emitted by the **same feature run**, not the original GLB. PartField may preprocess topology; original and processed faces need not correspond. The importer requires one finite integer label per processed face and checks that chosen clustering levels are genuinely nested. Fine clusters become separate meshes, coarse levels become parent nodes. Names remain geometric cluster labels. Source license/author information comes from your metadata.

This adapter preserves segmentation hierarchy, but it does not transfer original PBR textures onto remeshed output. It does not generate a heart's missing chambers or a car's missing engine. Segmentation separates existing geometry only.

## DepthART: investigated, deliberately optional

Investigated as potential future work; not integrated into the current prototype.

The [official DepthART repository](https://github.com/bulatko/DepthART) presents a research depth-estimation pipeline with its own environment, checkpoints, and configuration. It is not a drop-in hand metric-depth API. We did not install its weights or add it to the live camera loop.

InsideOut instead uses a smoothed change in apparent palm size relative to pinch start. Moving toward the camera increases that scale and pulls the grabbed component toward the viewer. This is a relative interaction signal, not centimeters. Palm tilt, occlusion, articulation, or tracking error can distort it. XY dragging remains available, and mouse controls do not depend on depth inference.

Future depth work should calibrate against actual hand motion and compare quality/latency before replacing the fallback. No research-model accuracy or performance has been borrowed as a claim about this prototype.
