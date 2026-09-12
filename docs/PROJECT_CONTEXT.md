# Saved project context

Updated 2026-09-12.

## User direction

Project: **InsideOut**, a competition prototype in the AIO project folder.

Core idea: a student shows a physical hand-drawn object to a webcam; CV retrieves the closest object from a prepared local 3D library; the model materializes; hands select, pull, rotate, explode, isolate, hide, and reassemble its real components.

Latest instruction: **FINAL VALIDATION MODE**. The user explicitly authorizes launching and testing the current Python application, measuring performance, and fixing critical demo bugs. No new features, architecture/framework replacement, assets, PartField development, or DepthART integration. This supersedes the earlier build-only/no-testing restriction. Keep the native Python window.

Complete supplied brief:
`C:\Users\user\.codex\attachments\a974d60d-a871-4fb5-8986-c804b8bab763\pasted-text.txt`.

## Priorities and exclusions

1. Genuine sketch-to-rendered-model visual retrieval.
2. High-quality real part-aware geometry.
3. Hand selection and pinch manipulation.
4. Continuous exploded view and reassembly.
5. Paper-to-object reveal.
6. Relative-depth manipulation.
7. Extensible offline ingestion.

No fake scores, filename classification, fabricated anatomy, chatbot, tutor, quiz, voice assistant, accounts, dashboard, cloud requirement, or production deployment. A small curated real library is acceptable. Ambiguous retrieval must offer a candidate choice instead of pretending certainty.

## Current decisions

- Native Python 3.12 / PySide6 / VTK; OpenCV / MediaPipe / PyTorch / OpenCLIP.
- Seven library objects. Competition retrieval is restricted to Heart, Car, and Earth with 237 render/sketch/prototype reference vectors.
- Actual anatomy parts in heart/lungs; CarConcept is grouped into 11 source-supported assemblies; Earth uses a documented four-layer procedural fallback; simpler source/geometry groups remain for camera, lantern, and bottle.
- PartField and DepthART are future-work investigations only; neither is included in or required by the competition runtime.
- Native entry point: `insideout.py`; double-click `start_insideout.bat`.
- The native window has an **Input** selector for Camera 0–5. It can switch devices safely while running; indices follow OpenCV rather than guessed device names.
- Runtime manifest: `assets/desktop/manifest.json`. The unused legacy web frontend/backend and old browser manifest were removed from the competition repository.
- Runtime validation records evidence in `docs/VALIDATION_REPORT.md`, `docs/COMPETITION_BUILD_STATUS.md`, and `evaluation/`. Four retained physical frames pass the final code, but they are calibration/regression inputs and not a general accuracy dataset.
- Latest scoped native CPU validation passed startup, all 29 Heart/Car/Earth runtime parts, mouse/file/CPU fallbacks, and failure handling with no unhandled exceptions. Live Car and one live Earth capture passed before the final index rebuild; final live recapture and repeated physical hand trials remain pending.
- Preserve provenance: models come from external publishers; application implementation is AI-assisted. Do not label these as entirely original student-authored work.

## Competition documents

Keep the original PDFs unchanged:

- `AIO 2026 Instructions.pdf`
- `AIO 2026 Submission Guide.pdf`
- `AIO 2026 Submission.pdf`

Use those PDFs as authority for competition deadlines, limits, and submission steps. This implementation note does not establish a verified current deadline or submission status. Recheck the relevant document/organizer before answering a new submission question. Building does not authorize submission.

## Handoff references

`README.md` contains run/build instructions and controls. `ATTRIBUTION.md` records authors/licenses. `docs/TECHNICAL_FACTS.md` and `docs/VALIDATION_REPORT.md` contain current technical facts and evidence. Continue relevant validation autonomously; do not turn validation into new feature development.
