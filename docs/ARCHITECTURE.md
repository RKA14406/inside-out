# InsideOut implementation notes

## Status and scope

Native desktop build dated 2026-09-11. Final validation explicitly supersedes the prior build-only restriction. The native window, six rendered models, 95 independent mesh parts, file retrieval, mouse controls and graceful failure paths have been exercised. Physical hand/paper trials and real-sketch accuracy remain unverified. See `VALIDATION_REPORT.md` for measured results and the distinction between real UI checks, injected failures and reference-render smoke inputs. No architecture, frameworks or assets were replaced.

The older `frontend/` and `backend/` remain for provenance only. Desktop launch does not use their procedural assets, scores, endpoints, JavaScript, or browser.

## Thread and data ownership

- Qt main thread owns all widgets and VTK/OpenGL. A 16 ms timer requests interpolated scene rendering; actual frame rate is hardware-dependent.
- `CameraWorker` owns VideoCapture and MediaPipe. It exposes only the latest completed frame under a lock, so obsolete camera frames do not build up in the Qt queue. Paper detection is scheduled every 250 ms; hand inference targets 24 Hz. Requested rates are not measured guarantees.
- `RetrievalWorker` loads the image encoder once. A bounded queue accepts captures; request tokens discard obsolete results if a new drawing or direct-library selection supersedes them.
- Modal dialogs suspend automatic acquisition and gesture interaction. Camera/encoder workers are interrupted and allowed to finish before the window destroys their resources.
- OpenGL, GUI event handling, and scene changes stay on the main thread. Rendering/index generation and PartField run as separate offline commands.

## Paper acquisition

OpenCV combines edge and bright-region contours, filters convex quadrilaterals, orders corners, and warps the candidate into a rectangular crop. Illumination normalization, dark-stroke extraction, speck suppression, ink bounding-box cropping, and square padding produce the encoder query.

Stable capture requires a detected page, plausible ink coverage, and accumulated stability confidence for 0.55 seconds. Small handheld motion continues accumulating confidence; moderate motion decays progress slowly instead of resetting the timer, and corner coordinates are smoothed. Manual webcam capture requires a detected crop and refuses to submit the full room when detection fails. File uploads use the same detector but do not use their coordinates as a webcam anchor.

Limitations: this is a document heuristic, not a trained paper detector. Busy backgrounds, reflective or dark paper, hands covering corners, and low-contrast pencil can defeat it. A full-frame manual fallback is not an assurance that the sketch was localized.

## Actual visual retrieval

Encoder: [OpenCLIP](https://github.com/mlfoundations/open_clip) ViT-B-32 with [laion2b_s34b_b79k weights](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K). Only its visual tower is retained in memory after loading. Neither text embeddings nor category/filename lookup contributes to similarity. This is a general-purpose baseline, not a sketch-specialized model trained or calibrated for this collection.

Each object has 12 azimuth/elevation views, each stored as a shaded render and a contour image: 24 views per object, 144 total. Index building embeds the actual shaded/contour images, retaining model ID, angle, image path, and encoder identity. The NPZ vector search is appropriate for this small collection; FAISS is unnecessary at this scale.

The normalized query has small rotational variants and a mirrored variant. L2-normalized visual embeddings use dot-product cosine similarity. A lightweight gradient/ink signature provides an auxiliary shape term:

```text
view score = 0.92 × visual cosine + 0.08 × shape similarity
model score = 0.8 × best view score + 0.2 × mean(top 3 view scores)
```

Auto-selection currently requires best-view visual cosine >= 0.58 and model-score margin >= 0.035. These starting thresholds are **uncalibrated**. Otherwise the user chooses from the top three. Scores are actual outputs, not confidence percentages. If the encoder cannot load, a visibly identified OpenCV-only fallback still ranks actual view signatures but always requires confirmation. A missing/mismatched index disables retrieval and gives build instructions while direct Library access remains available.

The debug drawer reports actual query latency, candidates, best rendered view, encoder mode/fallback reason, hand landmarks, pinch distance, raycast hit, selected mesh, explosion, and relative depth. Its FPS counter measures scene timer/render cadence, not an independent benchmark.

## Geometry and hierarchy

Source GLBs are retained unchanged. Trimesh applies source graph transforms and optional metadata orientation, centers the combined bounds, and scales the largest dimension to 3 scene units. Each mesh cache stores vertices relative to its component center, triangle indices, normals, optional UV/color arrays, and a texture image. Stable part IDs derive from source names. Original source nodes remain parent groups; mesh leaves carry geometry.

Single-mesh assets can use connected-component splits. These labels are explicitly geometric. Heart/lung meshes carry source anatomical names; no semantic grouping is invented for other objects. The PartField importer constructs nested parents from aligned agglomerative face-label outputs, without claiming semantic labels.

VTK draws real meshes using three lights, Phong shading, textures/base colors, and available transparency. Full GLTF PBR extensions, transmission, skeletal animation, and physical material accuracy are not implemented. Highlighting uses selected mesh edges. Live shadow mapping is not included.

## Interaction and coordinates

The webcam is mirrored once before both tracking and display. The renderer letterboxes that frame; fingertip coordinates map through the same letterbox to a VTK cell raycast. Hand points receive time-based low-pass smoothing. Pinch thresholds normalize thumb-index distance to palm scale, with separate enter/exit thresholds and temporal confirmation. Hand loss releases manipulation; identity ownership prevents another hand silently taking over an existing grab.

Point dwell selects. Pinch starts a locked grab. X/Y uses a camera-facing world plane; relative depth uses logarithmic palm-scale change, clamped to +/-1.8 scene units. Wrist rotation twists the selected mesh/group around the view axis. This is **not metric depth**: foreshortening and articulation can change the estimate. Empty-space pinch orbits the object. Two open hands or two pinches control continuous explosion. One sustained palm resets; stationary sustained pinch toggles isolation.

Explosion vectors accumulate at branching hierarchy levels, use bounding centers/radii, allow metadata axis overrides, and apply bounded sphere-based spacing. This reduces overlaps but is not a collision solver. User-pulled offsets remain until reset; near-origin releases snap back. Isolation hides other meshes and adjusts camera fit; Parts allows selecting whole parent assemblies or hidden meshes.

## Materialization

The reveal starts near the detected paper center, uses its in-plane edge angle, and follows that approximate anchor briefly while growing toward a centered exploration view. The camera image dims during the transition. It is not calibrated 6DoF tracking: there is no camera calibration, solved metric pose, real-world occlusion, or persistent AR anchoring. A file/direct-library load materializes at the scene center. Reduced motion removes grow/easing effects.

## Remaining work and limits

- Complete physical paper/gesture trials and an end-to-end rehearsal using real drawings. Native startup, rendering and shutdown have been exercised.
- Calibrate against real drawings; correct recognition is not guaranteed by a populated index.
- Tune gestures for camera distance, lighting, handedness jitter, occlusion, and two-hand transitions.
- Measured timings and renderer cadence on the current machine are in `VALIDATION_REPORT.md`; no measured minimum hardware requirement is established.
- The four non-anatomical assets have limited groups; richer licensed assemblies would improve structural depth.
- PartField: "Optional experimental adapter implemented but not validated or required by the competition MVP."
- DepthART: "Investigated as potential future work; not integrated into the current prototype."
- Actual screenshots are in `docs/evidence/`. No installer executable, production packaging, video recording, cloud service or deployment has been built.
