# InsideOut

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
  <img alt="InsideOut" src="assets/logo-light.svg" width="520">
</picture>

**Draw an object, retrieve its local 3D model, and explore the parts—without a browser or cloud inference.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows)](#requirements)
[![Retrieval](https://img.shields.io/badge/competition%20classes-Heart%20%7C%20Car%20%7C%20Earth-EFC57B)](#supported-objects)
[![License](https://img.shields.io/badge/project%20license-not%20declared-lightgrey)](#license)

**English** · [简体中文](README_CN.md)

InsideOut is a native PySide6/VTK computer-vision prototype for AIO 2026. It captures a physical drawing or opens an image, proposes likely visual regions without requiring paper, compares RGB and sketch representations with a local OpenCLIP index, and opens an interactive multipart 3D object. The competition recognizer is intentionally closed to three classes: **Heart, Car, and Earth**.

![InsideOut heart model](screenshots%20prototype/3d%20heart%20reavel.png)

## Demo

1. Start the native window with `start_insideout.bat`.
2. Choose a camera, or use **Open drawing**.
3. Show a Heart, side-view Car, or globe with visible continent-like marks.
4. Press **Space** or enable stable auto-capture.
5. Rotate, explode, isolate, and reset the retrieved model with hands, mouse, or buttons.

The recognizer rejects low-score or low-margin inputs instead of forcing a class. A plain circle is intentionally insufficient for Earth.

## Who Is This For?

- AIO 2026 judges and demonstrators evaluating the native competition prototype.
- Students exploring local computer vision, image retrieval, and interactive 3D graphics.
- Developers reproducing the measured Windows build or extending the offline validation tools.

## Features

- Native Python window using PySide6 and VTK; no web server, browser, account, or API key.
- Paper-optional ROI proposals: detected page, grouped drawing region, poster-like rectangle, and conservative center fallback.
- Four query representations per primary ROI: RGB, grayscale, cleaned line art, and edge map.
- Local OpenCLIP ViT-B-32 image embeddings plus a small calibrated edge-shape contribution for sketch banks.
- A 237-vector competition index: 36 render, 165 sketch/edge, and 36 real-sketch prototype references.
- Conservative acceptance gates: score at least `0.78` and Top-1 margin at least `0.04`.
- Semantic Heart (14 parts), CarConcept Car (11 grouped assemblies), and layered Earth (4 parts).
- MediaPipe hand tracking with latest-frame processing, One Euro landmark filtering, pinch hysteresis, dead zones, and interaction-state locking.
- Reliable competition fallbacks: CPU encoder, image-file input, direct library access, and mouse interaction.
- CV debug drawer showing ROI, processed query, ranked classes, scores, timings, gesture state, and FPS.

## Supported Objects

Only the first three objects participate in competition retrieval. The remaining library objects can be opened directly.

| Object | Retrieval | Runtime parts | Source / license |
|---|---:|---:|---|
| Human Heart | Yes | 14 named anatomical components | HuBMAP HRA, CC BY 4.0 |
| Car | Yes | 11 source-supported assemblies | Khronos CarConcept, CC BY 4.0 |
| Earth | Yes | 4 educational layers | InsideOut procedural fallback, CC0 1.0 |
| Human Lungs | Library only | 67 source components | HuBMAP HRA, CC BY 4.0 |
| Antique Camera | Library only | 2 source groups | Khronos/UX3D, CC0 1.0 plus mark notice |
| Lantern | Library only | 3 source groups | Khronos, CC0 1.0 |
| Water Bottle | Library only | 6 geometric components | Khronos, CC0 1.0 |

See [ATTRIBUTION.md](ATTRIBUTION.md) for authors, URLs, checksums, modifications, logo handling, and complete notices.

## Quick Start

On the prepared competition computer:

```powershell
.\start_insideout.bat
```

Safe camera-free CPU fallback:

```powershell
.\start_insideout.bat --cpu --no-camera
```

## Installation

### Requirements

- Windows 10 or 11, 64-bit.
- Python 3.12, 64-bit.
- A VTK/OpenGL-capable graphics driver.
- Webcam for camera input; optional when using image files.
- Several gigabytes of disk space for Python packages and generated model caches.
- Network access during first setup only. Normal retrieval is local.

### Setup

From PowerShell in the project directory:

```powershell
.\setup_insideout.ps1
```

Setup creates `.venv-desktop`, installs [requirements-desktop.txt](requirements-desktop.txt), downloads attributed source assets and the approximately 605 MB OpenCLIP checkpoint, builds runtime geometry/previews, and creates the competition index. It does not launch the app.

Useful setup options:

```powershell
.\setup_insideout.ps1 -SkipAssets
.\setup_insideout.ps1 -Python 'C:\Path\To\python.exe'
.\setup_insideout.ps1 -UseSystemPackages
```

## Usage

### Camera

```powershell
.\start_insideout.bat
.\start_insideout.bat --camera 1
```

Choose Camera 0–5 in the **Input** selector before pressing **Camera on**. An unavailable device produces a visible error while file and library fallbacks remain available. Paper helps perspective correction but is not required.

### Image file

Start normally or without a camera, then select **Open drawing**:

```powershell
.\start_insideout.bat --no-camera
```

PNG, JPEG, BMP, and WebP are accepted. Camera and file inputs use the same ROI and retrieval engine.

### CPU fallback

```powershell
.\start_insideout.bat --cpu
.\start_insideout.bat --cpu --no-camera
```

CUDA is optional. If unavailable, automatic mode falls back to CPU. On the validated machine, CPU retrieval over four retained physical captures averaged 470 ms after encoder loading; individual results ranged from 370–606 ms.

### Controls

| Input | Action |
|---|---|
| Point and dwell | Hover/select a mesh |
| Pinch and move | Grab and pull the selected part |
| Wrist turn while pinching | Rotate the selected part/assembly |
| Pinch empty space and move | Orbit the full object |
| Two hands spread/close | Explode or reassemble continuously |
| Hold one open palm | Reset/reassemble |
| Mouse left drag / wheel | Orbit / zoom |
| Shift + left drag | Pull a part |
| `I`, `H`, `R` | Isolate, hide/show, reset |
| `N`, `D`, `F11` | New drawing, debug drawer, full screen |

Gesture isolation is disabled in competition mode; the button and keyboard fallback remain available.

## Retrieval and Validation

The competition path compares each selected ROI independently so classes cannot win using different crops. A strong page/drawing/poster proposal owns the decision; an uncertain primary ROI rejects instead of falling through to a background crop that resembles Car.

The current retained physical-capture regression set contains one Heart frame, one Car frame, and two Earth frames. The CPU file/ROI pipeline classified all four correctly. This is a small calibration/regression set—not a general accuracy claim. Detailed drawings, posters, and broad variations still require more manually collected data.

Run the regression and negative checks:

```powershell
.\.venv-desktop\Scripts\python.exe scripts\evaluate_retrieval.py evaluation\competition_frames --device cpu --output evaluation\frame_evaluation
.\.venv-desktop\Scripts\python.exe scripts\validate_negatives.py
.\.venv-desktop\Scripts\python.exe scripts\validate_runtime.py --device cpu --models human_heart toy_car earth
```

See [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md), [docs/COMPETITION_BUILD_STATUS.md](docs/COMPETITION_BUILD_STATUS.md), and [docs/TECHNICAL_FACTS.md](docs/TECHNICAL_FACTS.md).

## Architecture

```text
Camera / image file
        │
        ├─ page, drawing, poster, center ROI proposals
        │       └─ RGB / grayscale / line / edge queries
        │               └─ OpenCLIP + calibrated sketch shape score
        │                       └─ score + margin gate ──> 3D model
        │
        └─ latest camera frame ──> MediaPipe hands ──> filtered interaction state

GLB/source geometry ──> offline VTK cache + hierarchy ──> selectable part scene
```

Important entry points:

| Path | Purpose |
|---|---|
| `insideout.py` | Native launcher and CLI options |
| `desktop/query_regions.py` | Paper-optional ROI proposals |
| `desktop/encoder.py` | Query variants, retrieval banks, scoring, rejection |
| `desktop/camera.py` | Latest-frame camera and hand workers |
| `desktop/gestures.py`, `desktop/interactions.py` | Filtering and interaction state |
| `desktop/scene.py` | VTK selection, movement, explosion, isolation, reset |
| `scripts/build_competition_index.py` | Rebuild the three-class index |
| `scripts/evaluate_retrieval.py` | Exact file/ROI regression evaluation |

## Build and Package

Build the local source release ZIP with:

```powershell
.\scripts\build_release.ps1
```

The ZIP omits virtual environments, package caches, logs, temporary evidence, model weights, and generated geometry caches. Run `setup_insideout.ps1` after extraction to download/build machine-specific dependencies and assets. A standalone EXE is not supplied because bundling PyTorch, OpenCLIP, VTK, Qt, MediaPipe, model weights, and attributed assets produces a very large, fragile build that was not validated for competition use.

## Security and Privacy

- Camera frames, landmarks, and queries remain local; the app has no upload path or telemetry.
- Runtime errors are written locally to `data/logs/insideout.log`.
- Setup uses the network to download Python packages, model assets, and weights from documented sources.
- Treat imported 3D/image files as untrusted input. Their native parsers are not a sandbox.
- No API keys or credentials are required. Never commit local secrets, virtual environments, logs, or model-download tokens.

## Contributing

Keep changes scoped to the native Python prototype. Preserve factual attribution and distinguish physical tests from software replay. Before opening a change, run compilation, negative retrieval, retained-frame evaluation, and the relevant runtime validation subset. Do not add assets without a clear redistribution license and source metadata.

## License

No general open-source license has been selected for InsideOut’s own source code; default copyright restrictions therefore apply. Third-party models, packages, and weights retain their separate licenses. See [ATTRIBUTION.md](ATTRIBUTION.md). The repository’s availability does not grant rights beyond those notices.
