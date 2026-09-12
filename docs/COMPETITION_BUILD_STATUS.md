# Confirmed Implemented

- Competition retrieval is restricted to Heart, Car, and Earth.
- Camera and image-file input share a paper-optional, maximum-three-ROI engine.
- Primary ROI variants are RGB, grayscale, cleaned line art, and Canny edge.
- The 237-vector index contains render, sketch/edge, and real-sketch prototype banks.
- Every class is scored on the same ROI. A detected page/drawing/poster owns the decision; uncertainty cannot fall through to a background Car match.
- Acceptance requires score ≥0.78 and margin ≥0.040. Blank and plain-circle diagnostics reject before ranking.
- CarConcept provides 11 runtime assemblies; the Earth fallback provides four educational layers.
- `--cpu`, `--no-camera`, Open drawing, direct Library, mouse controls, debug drawer, and visible resource errors remain available.

# Confirmed Tested

- Native CPU validation exited successfully with no unhandled Python exceptions.
- All 14 Heart parts, 11 Car assemblies, and four Earth layers loaded/rendered, raycast, isolated, moved/rotated independently, exploded, hid/restored, and reset.
- Mouse orbit/zoom/part drag, image-file retrieval, CPU fallback, missing resources, and hand-loss release software replay passed.
- Four retained real physical frames pass the final CPU ROI/retrieval code: Heart 0.9705, Car 1.0000, Earth 0.8971 and 0.8712.
- A fresh live Car capture passed before the final index rebuild at 0.8236 with margin 0.069.
- A fresh live Earth capture passed before the final rebuild at 0.8365 with margin 0.075.
- Generated blank, plain-circle, scribble, and text negatives reject. These are software regressions, not physical trials.
- Car load averaged 53.58 ms and Earth 8.20 ms. Renderer cadence averaged 61.64 FPS for Car and 62.08 FPS for Earth in the latest CPU validation.

# Implemented but Unverified

- A final live-camera Heart/Car/Earth sequence after the 237-vector rebuild.
- A physical bad-drawing rejection after the calibrated 0.78 threshold.
- Detailed drawings, photos/posters, books, walls, and another-screen cases.
- Repeated physical gesture success/false-trigger measurements.

# Known Limitations

- The real calibration/regression set has only four frames and is not a general accuracy dataset.
- Car and Earth prototype scores can approach 1.0 on their exact calibration crop; this proves non-regression, not generalization.
- Full multi-ROI CPU retrieval over retained physical frames measured 370–606 ms after encoder loading.
- CPU OpenCLIP readiness measured 10.492 s in the latest clean integration run.
- Earth Core V.1 is not bundled because official download required an unavailable Sketchfab login. The documented lightweight procedural fallback is used.
- Earth colours and radii are illustrative; surface patches are not cartographically exact.
- CarConcept textures and the steering emblem are omitted; materials are simplified.

# Competition Fallbacks

1. Standard CPU: `C:\uni-20231\PROJECTS\AIO\start_insideout.bat --cpu`.
2. Camera-free CPU: `C:\uni-20231\PROJECTS\AIO\start_insideout.bat --cpu --no-camera`, then **Open drawing**.
3. If recognition rejects an input, use **Library** and clearly disclose that recognition was bypassed.
4. If hand tracking is poor, use mouse orbit/zoom/Shift-drag plus Parts, Explode, Isolate, Show all, and Reassemble.

# Future Work — NOT CURRENT MVP

PartField: "Investigated as potential future work; its experimental adapter was removed from the cleaned competition repository and is not required by the MVP."

DepthART: "Investigated as potential future work; not integrated into the current prototype."

Open-world recognition, additional categories, large training datasets, LLMs, voice, quizzes, and AR/VR are outside the current MVP.
