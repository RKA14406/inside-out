# InsideOut validation report

Validation date: 2026-09-12. This report distinguishes live physical-camera observations, replay of retained physical captures, generated negative checks, and native software interaction tests.

## Retrieval root cause and fix

The original failure had four measurable causes:

1. A single paper crop and binary query discarded colour and useful visual context.
2. Hand sketches were compared mainly with shaded 3D renders, producing a sketch/render domain gap.
3. Every class could select its own best ROI, so the reported margin compared scores from different crops.
4. When a strong page ROI was uncertain, a lower-priority center/background crop could still accept Car.

The active pipeline proposes at most three page/drawing/poster/fallback ROIs and produces RGB, grayscale, cleaned line, and edge queries. It compares every class on the same ROI against render, sketch, and real-prototype banks. Line/edge comparisons use 90% OpenCLIP cosine and 10% normalized shape similarity; RGB/render matching remains pure OpenCLIP. A strong non-fallback ROI owns the decision, so uncertainty rejects instead of falling through to background. Acceptance requires score ≥0.78 and Top-1 margin ≥0.040.

## Retained physical-capture regression

The four images below came from real physical drawings. Car and Earth calibration crops are retained under `evaluation/competition_sketches/`; their original full camera frames remain under `evaluation/competition_frames/` and `docs/evidence/sketch_debug/`.

| Physical frame replayed through full ROI pipeline | Selected ROI | Top-1 | Score | Top-2 | Margin | CPU total | Result |
|---|---|---|---:|---|---:|---:|---|
| Heart | drawing-region | Heart | 0.9705 | Earth | 0.2342 | 606.2 ms | Accepted, correct |
| Car | drawing-region | Car | 1.0000 | Earth | 0.2286 | 369.7 ms | Accepted, correct |
| Earth capture 1 | page/rectangle | Earth | 0.8971 | Heart | 0.1411 | 371.3 ms | Accepted, correct |
| Earth capture 2 | page/rectangle | Earth | 0.8712 | Heart | 0.1313 | 532.8 ms | Accepted, correct |

Average CPU total was 470.0 ms (min 369.7, max 606.2). Preprocessing averaged 197.3 ms, embedding 271.1 ms, and search 1.47 ms. These images contributed prototype variants, so these are calibration/non-regression results rather than held-out accuracy.

### Live physical observations

- Fresh Car camera capture before the final prototype-index rebuild: Car 0.8236, Earth 0.7545, Heart 0.7335; margin 0.0690; CUDA retrieval 784.8 ms; accepted.
- One Earth camera capture before the final rebuild: Earth 0.8365, Heart 0.7615, Car 0.6920; margin 0.0750; accepted.
- A later partial Earth page exposed the fallback bug: the primary page was uncertain and a center/background crop accepted Car. This directly motivated the primary-ROI ownership fix.
- Device control was stopped before a new live-camera run with the final 237-vector index. The saved physical frames pass the final code, but final live recapture is not claimed.

## Historical Heart failure

On the original physical Heart crop, the old six-class bank scored Car 0.7877 and Heart 0.6559. The active cropped regression scores Heart 1.0000, Earth 0.7395, and Car 0.6815. The exact Heart crop is a prototype reference, so 1.0000 proves non-regression only.

## Negative regression

`scripts/validate_negatives.py` uses generated software inputs only:

| Input | Top score / diagnostic | Result |
|---|---|---|
| Blank | No visible drawing | Rejected before ranking |
| Plain circle | Plain circle is insufficient for Earth | Rejected before ranking |
| Scribble | Earth 0.6940; margin 0.0265 | Rejected |
| Text | Earth 0.7323; margin 0.0678 | Rejected by 0.78 score gate |

Reference-render smoke also observed non-competition Bottle at a maximum 0.7454 and rejected it under the calibrated score gate. These are software checks, not physical negative trials.

## Native runtime validation

Command:

```powershell
.\.venv-desktop\Scripts\python.exe scripts\validate_runtime.py --device cpu --models human_heart toy_car earth
```

Result: exit code 0, no unhandled exceptions.

- Native startup reached the first VTK frame in 2.231 s and CPU OpenCLIP readiness in 10.492 s.
- Heart: 14/14 runtime parts loaded, raycast, isolated, moved/rotated independently, exploded, hid/restored, and reset.
- Car: 11/11 assemblies passed the same checks.
- Earth: 4/4 layers passed the same checks.
- Mouse orbit, zoom, Shift-drag, release handling, image-file retrieval, missing-model/embedding/weights behavior, camera selection replay, hand-loss release, and CUDA-unavailable CPU fallback passed.
- Heart model load: average 51.34 ms (41.31–72.35, n=6).
- Car model load: average 53.58 ms (47.91–57.67, n=3); renderer average 61.64 FPS (54.55–62.91, n=16).
- Earth model load: average 8.20 ms (7.37–9.21, n=3); renderer average 62.08 FPS (60.49–62.57, n=14).
- Single-ROI CPU retrieval smoke: average 225.18 ms (197.13–259.85, n=22).

Evidence is in `evaluation/runtime/`, `evaluation/frame_evaluation/`, and `docs/evidence/`.

## Active index

- OpenCLIP model: ViT-B-32
- Pretrained identity: laion2b_s34b_b79k
- Dimension: 512
- Vectors: 237, L2-normalized
- Car: 81; Heart: 75; Earth: 81
- Banks: render 36; sketch 165; real prototype 36
- Shape vectors: normalized 384-D diagnostic/hybrid features

## Asset validation

| Object | Runtime parts | Triangles | Native interaction result |
|---|---:|---:|---|
| Heart | 14 | 164,119 | All tested successfully |
| CarConcept Car | 11 | 213,229 | All tested successfully |
| Procedural Earth fallback | 4 | 7,050 | All tested successfully |

CarConcept retains its original 11,778,688-byte GLB. The runtime copy excludes `InteriorSteeringEmblem`, omits textures, and groups 109 imported geometry instances into 11 source-supported assemblies. Earth Core V.1 was not downloaded because the official Sketchfab download required a logged-in account; the documented CC0 procedural fallback is used.

## Remaining weaknesses

- Final live-camera Heart/Car/Earth recapture after the last index rebuild is pending.
- Physical bad-drawing rejection after the final score threshold is pending.
- Detailed drawings and photo/poster coverage are not scientifically validated.
- Current real calibration set is too small for a general accuracy percentage.
- Repeated physical hand-gesture success rates remain unfilled; software state replay does not prove physical smoothness.
- CPU startup is dominated by the 605 MB OpenCLIP model load; start the app before judging.
