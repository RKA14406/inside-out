from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.vision.retrieval import SketchRetriever

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "model_manifest.json"

app = FastAPI(title="InsideOut CV Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = SketchRetriever()
with MANIFEST.open("r", encoding="utf-8") as stream:
    library = json.load(stream)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "insideout-cv", "indexedViews": len(retriever.index), "models": len(library)}


@app.get("/api/library")
def get_library() -> list[dict[str, object]]:
    return library


@app.post("/api/retrieve")
async def retrieve(file: UploadFile = File(...)) -> dict[str, object]:
    payload = await file.read()
    result = retriever.retrieve(payload)
    lookup = {item["id"]: item for item in library}
    result["model"] = lookup[result["match"]]
    result["candidates"] = [
        {**candidate, "name": lookup[candidate["model_id"]]["name"]}
        for candidate in result["candidates"]
    ]
    return result
