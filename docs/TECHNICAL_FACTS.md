# InsideOut technical facts

Verified from the active code, generated index, retained physical captures, and native runtime checks on 2026-09-12. Physical behavior is not marked tested unless a person supplied or performed that test.

## Runtime

| Item | Verified implementation |
|---|---|
| Language / GUI | Python 3.12.4; PySide6 / Qt 6.10.0 native desktop window |
| Rendering | VTK 9.5.2, `QVTKRenderWindowInteractor`, OpenGL triangle actors |
| Geometry | trimesh 4.12.2 ingestion; NumPy NPZ runtime caches; SciPy rotations |
| Computer vision | OpenCV 4.11.0 |
| Hand tracking | MediaPipe 0.10.14 Hands; 21 landmarks; maximum two hands; model complexity 0; detection/tracking confidence 0.6 |
| Retrieval | OpenCLIP 2.32.0 / PyTorch 2.5.1, image tower only |

`insideout.py` is launched by `start_insideout.bat`. The renderer requests a 16 ms update; UI polling is 33 ms. Camera, paper processing, MediaPipe, and retrieval run outside the render loop. Camera/paper/hand workers use one-slot latest-frame buffers, so stale frames are discarded.

## Competition retrieval

- Classes: `human_heart`, `toy_car`, `earth` only. Four other library objects remain directly loadable but never participate in competition ranking.
- Encoder: OpenCLIP **ViT-B-32**, checkpoint identity **laion2b_s34b_b79k**, local file `data/weights/open_clip_model.safetensors`, **512 dimensions**.
- Active index: `data/model_index/competition.npz`, **237 L2-normalized 512-D embeddings** and matching normalized 384-D diagnostic shape vectors.
- Banks: **36 render**, **165 sketch/edge**, and **36 real-prototype** references. Totals: Car 81, Heart 75, Earth 81.
- Query regions: at most three candidates. Sources are an optional detected/perspective-corrected page, grouped local-contrast/chromatic strokes, a rectangular poster/image contour, a center crop, and full-frame fallback. The cheap detector ranks/deduplicates candidates before OpenCLIP.
- Query representations per ROI: RGB, grayscale, cleaned black-line-on-white, and Canny edge. RGB preserves photographs/colour; line/edge preserves simple ink drawings, including blue ink.
- Similarity: L2-normalized dot product (cosine). Every class is compared on the same ROI. For sketch/prototype banks, line and edge cells combine 90% OpenCLIP cosine with 10% normalized shape similarity; RGB/render cells remain pure OpenCLIP. For each class/bank, the bank score is the mean of its three strongest reference/query similarities; the class score is the maximum bank score. No class-name text or filename rule is used.
- Output: per-class render/sketch/prototype scores, Top-1/Top-2 margin, winning ROI type/index, query representation, reference bank/type/view, timings, and accepted/uncertain state.
- Acceptance: Top-1 score ≥ **0.78** and Top-1 minus Top-2 margin ≥ **0.040**. A strong page/drawing/poster proposal owns the decision; an uncertain primary proposal does not fall through to a background crop. A blank, excessively dense input, input with more than 28 disconnected marks, or a near-circular outline with insufficient interior ink is rejected before acceptance. A plain circle is explicitly insufficient for Earth.
- OpenCLIP failure: shape-only ranking remains diagnostic but is never automatically accepted.

The final full-ROI CPU replay of retained physical frames produced Heart 0.9705, Car 1.0000, and Earth 0.8971/0.8712, all accepted correctly. Average total retrieval was 470.0 ms over four frames. These images contributed prototype references and are regression/calibration evidence, not a held-out accuracy claim. The original physical Heart failure scored Car 0.7877 versus Heart 0.6559 in the old six-class bank.

## Region and sketch processing

The optional page path resizes to at most 640 px, applies grayscale, 5×5 blur, Canny 35/110 plus 5×5 close, and a bright threshold at `max(110, 68th percentile)`. The largest 20 contours are approximated at 2.2% perimeter; valid pages are convex quadrilaterals with 12–96% frame area, minimum edge 35 px, edge ratio ≤3, and mean grayscale ≥95. A bounded 128-px six-cluster Lab fallback handles coloured/torn/occluded notes. `getPerspectiveTransform` and `warpPerspective` rectify accepted quads.

The paper-independent drawing proposal uses local Lab-colour difference, local grayscale difference, Canny edges, morphology, nearby-stroke grouping, contour density/area/center scoring, and padded bounding crops. It does not assume black ink. Poster candidates use convex quadrilateral contours and rectangularity. Center/full-frame fallbacks are always available at lower priority.

Clean line processing trims 2.5%, uses grayscale, 3×3 blur, Gaussian background estimation (sigma 18), division-based illumination correction, inverse threshold 205, connected-component cleanup, central stroke focus with enclosed detail retention, tight crop, and 82% fit on a 224×224 white canvas.

Stable auto-capture accumulates for 0.55 s. With a paper quad it uses corner motion and query change; without paper it uses query-image change. Manual Space capture no longer waits for or requires a paper quad.

Supported Earth sketch: circle/ellipse plus rough continent/land shapes. `circle = Earth` is not implemented.

## 3D assets and interaction

| Object | Runtime parts | Triangles | Meaning |
|---|---:|---:|---|
| Heart | 14 | 164,119 | Named HuBMAP anatomical meshes |
| Car | 11 | 213,229 | CarConcept groups: body, hood, doors, rear hatch, interior, mechanical, four wheels |
| Earth | 4 | 7,050 | Surface/Crust, Mantle, Outer Core, Inner Core |

Scene selection uses VTK cell ray-picking. A hierarchy node selects all descendant runtime parts. Explosion computes bounded directions per hierarchy branch, supports source-name axis overrides, applies sphere repulsion, and scales to the current hierarchy depth. Isolate hides all parts outside the selected node; reset restores visibility, positions, rotations, camera framing, and explosion.

CarConcept's original 11,778,688-byte GLB has 101 source nodes, 97 declared meshes, 109 trimesh geometry instances, and 213,347 source triangles. The competition copy excludes `InteriorSteeringEmblem`, omits textures, and combines remaining geometry into 11 assemblies (213,229 triangles). The original remains retained for attribution.

The requested Earth Core V.1 page reports CC BY 4.0, 22.6k triangles, and 11.5k vertices, but official download required an unavailable logged-in account. The application therefore uses the brief's permitted procedural fallback: a 122,068-byte CC0 cutaway with four parts and stylized continent-like surface colours. Terminology is validated against NASA and USGS; colours/radii are illustrative, not to scale.

## Hand and mouse controls

MediaPipe coordinates are filtered per landmark with a One Euro filter: min cutoff 1.15 Hz, beta 0.32, derivative cutoff 1.0 Hz. Pinch is thumb tip 4 to index tip 8 distance divided by wrist-to-middle-MCP palm scale; enter <0.28, release ≥0.43, confirmation 80 ms. The interaction states are `IDLE`, `HOVER`, `PINCH_CONFIRMED`, `DRAGGING`, `TWO_HAND_EXPLODE`, `WAIT_RELEASE`, and `RESET`. A live drag remains owned by one hand until deliberate release or >0.22 s hand loss.

| Action | Mapping |
|---|---|
| Point/select | Index-extension heuristic; 100 ms confirmation; 0.60 s stable VTK ray-pick dwell |
| Grab/move | Confirmed pinch; filtered incremental XY movement; 2.5 px dead zone; 42 px/update clamp; 0.82 sensitivity |
| Model rotation | Pinch empty space; incremental deltas; 2 px dead zone; 32 px/update clamp; 0.22°/px |
| Part rotation | Filtered wrist-angle delta; 0.020 rad dead zone; 0.14 rad/update clamp; 0.72 sensitivity |
| Relative depth | Log palm-scale change; 0.025 dead zone; 0.08/update clamp; 0.55 sensitivity; non-metric |
| Two-hand explosion | Baseline at second-hand acquisition; distance EMA alpha 0.20; dead zone 0.012; signed power 1.12; sensitivity 2.25; clamped 0–1 |
| Reset | One open palm for 1.20 s |

Mouse fallback: left-drag orbit, wheel zoom, Shift+left-drag move selected part; Parts, Explode, Isolate, Show all, Hide/show, and Reassemble controls remain available.

## Measured current asset runtime

Native CPU validation, 2026-09-12; VTK still uses the graphics driver:

| Asset | Load samples ms (avg/min/max) | Renderer FPS samples (avg/min/max) |
|---|---|---|
| CarConcept competition copy | 53.58 / 47.91 / 57.67 (n=3) | 61.64 / 54.55 / 62.91 (n=16) |
| Four-layer Earth fallback | 8.20 / 7.37 / 9.21 (n=3) | 62.08 / 60.49 / 62.57 (n=14) |

The four retained physical-frame CPU evaluations measured 369.7–606.2 ms end-to-end (average 470.0 ms). A fresh native integration run reached the first VTK frame in 2.231 s and CPU retrieval readiness in 10.492 s. These are measured samples, not universal guarantees; start the app before judging.

Approximate local heavyweight files: OpenCLIP checkpoint about 605 MB; CarConcept original 11.78 MB; generated Earth 0.12 MB. Python environment size depends on installed wheels and is not claimed as a hardware requirement. Validated host: Windows 11 x64, i7-12650H, about 16 GB RAM, RTX 3050 Laptop 4 GB. `--cpu` works; CUDA is optional. Camera and MediaPipe are optional because file input, Library, and mouse controls remain functional.

Asset licenses and modifications are listed in [ATTRIBUTION.md](../ATTRIBUTION.md).
