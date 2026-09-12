# Competition retrieval and hand-control blocker report

Date: 2026-09-11. Scope: Car, Heart, Earth only. This report distinguishes software checks, one-sample physical evidence, and still-unperformed physical validation.

## Root cause

The wrong-Car behavior had two reproduced causes:

1. `InsideOutWindow.capture()` previously used the complete camera frame whenever `paper` was absent. A prior real room capture therefore reached OpenCLIP and ranked Car first (Car 0.757, Lantern 0.728, Antique Camera 0.692). Current webcam capture requires a detected quadrilateral and visibly rejects otherwise.
2. The real Heart card contained a finger shadow, torn edges, and paper defects. Old preprocessing kept spatially distant components, so the heart occupied a small part of the 224 × 224 query. On the manually rectified real card the old six-class path scored Car 0.787677 and Heart 0.655949. The current central stroke-component focus produces the image in `docs/evidence/sketch_debug/physical-heart-processed.png`.

There was also a genuine domain gap: paper line drawings were compared mainly with shaded/contour 3D renders. The active bank now contains sketch-style grayscale, edge, line, and silhouette representations.

## Retrieval change and measured sample

Only `toy_car`, `human_heart`, and `earth` participate. Twelve rendered viewpoints per class produce four representations each, totaling **144 competition reference embeddings**. The original full library remains available.

Current real Heart result:

| Class | Best cosine | Final score | Best query variant | Best reference |
|---|---:|---:|---|---|
| Heart | 0.853584 | 0.804305 | rotate −8° | silhouette, azimuth 240°, elevation 15° |
| Earth | 0.802105 | 0.752187 | rotate −8° | line, azimuth 30°, elevation −15° |
| Car | 0.806287 | 0.749224 | rotate +8° | line, azimuth 210°, elevation −15° |

Top margin was 0.052118, so Heart was accepted. Retrieval microtimings after the encoder was loaded: preprocessing 24.384 ms, embedding 19.723 ms, search 1.142 ms, total 45.263 ms. This is one physical drawing and must not be quoted as 100% accuracy.

An ablation on this same sample shows the two fixes contribute differently. New preprocessing with the old shaded/contour bank changed the order to Heart 0.6975 versus Car 0.6877, but the 0.0098 margin would remain uncertain. Adding the sketch-style bank raised Heart to 0.8043 and the margin to 0.0521, crossing the unchanged conservative decision rule. Thus sketch-style references improved separation on this sample; broader benefit remains unverified until Car/Earth and more Heart drawings are collected.

The original four-corner detector rejected the Heart card because the hand hid its left boundary and the torn top edge broke polygon approximation. A bounded Lab-color/minimum-area-rectangle fallback now detects that exact captured frame. Offline replay produces a valid quad, rectified crop, and final query; the normal dark room frame remains undetected. After restarting the actual Camera 1 application, a live Heart capture was accepted and opened Heart with scores Heart 0.8069, Earth 0.7412, Car 0.7212.

## Earth

Source: NASA Visualization Technology Applications and Development (VTAD), [NASA Earth 3D Model](https://science.nasa.gov/resource/earth-3d-model/). Terms: [NASA Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/). Original GLB size: 12,916,400 bytes. SHA-256: `05a5aea99db8ab472487a06debc3b5d0b2cae7636a1a6b9ecfa40b7d1722ba23`.

It loads as four selectable geometric/material mesh groups. Runtime render, raycast, independent movement/rotation, explosion, isolation, hide/show, and reset checks passed. These meshes are not semantic continents or internal geological layers.

## Hand-control change

Camera capture no longer waits for MediaPipe or paper processing. Separate workers keep only the newest frame. Requesting 640 × 480 avoids the webcam’s low-rate larger mode and matches the actual CV input width.

All 21 landmarks use a One Euro filter (`min_cutoff=1.15`, `beta=0.32`, derivative cutoff `1.0`). Pinch retains 0.28 enter / 0.43 release hysteresis and 80 ms confirmation. Interaction states are `IDLE → HOVER → PINCH_CONFIRMED → DRAGGING → release`, plus locked `TWO_HAND_EXPLODE`, `WAIT_RELEASE`, and `RESET`. During drag, new poses do not reinterpret the action. Translation, orbit, wrist rotation, depth, and explosion use centralized dead zones, sensitivities, and per-update clamps. Two-hand explosion records a baseline and filters distance before applying a bounded sensitivity curve. Gesture isolation is disabled in competition mode; UI/mouse isolation remains.

Live measurements:

| Run | Camera FPS | MediaPipe FPS | Renderer FPS | Visible landmark updates |
|---|---:|---:|---:|---:|
| Post-threading mixed run | 22.31 avg (8.66–31.38) | 20.90 (14.78–26.59) | 59.33 (46.56–63.41) | one brief interval at 6.96 FPS |
| Final no-hand run | 29.05 (27.00–30.23) | 29.18 (25.48–30.58) | 58.98 (44.57–63.51) | no visible hand |

The first visible-hand interval confirms that landmarks reached the application, but no repeated physical gesture sequence was performed. Smoothness and reliability therefore remain unverified.

## Required physical release gate

1. Add 5–10 real drawings per class under `evaluation/competition_sketches/`; include unrelated scribbles under `unknown/`.
2. Run `python scripts/evaluate_competition_retrieval.py evaluation/competition_sketches` and inspect every old/new score.
3. Restart the application, then perform the requested Heart, Car, Earth, and bad-drawing end-to-end sequences. Keeping the page near the center remains the most reliable setup.
4. Fill ten attempts for each core gesture in `evaluation/competition_gesture_test_template.csv`, including false triggers and notes.
5. If hand trials fail, use the verified mouse/buttons fallback rather than changing constants without measurements.

Current status: **DRAWING DEMO READY: NO. HAND DEMO READY: NO. OVERALL DEMO READY: NO.**
