export type Mode = 'capture' | 'materialize' | 'explore';

export type Candidate = {
  model_id: string;
  name: string;
  score: number;
  view: string;
};

export type RetrievalResult = {
  match: string;
  confidence: number;
  bestView: string;
  candidates: Candidate[];
  embeddingMs: number;
  paper: { detected: boolean; confidence: number; quad: number[][] | null };
  queryPreview?: string;
  model: ModelMeta;
};

export type ModelMeta = {
  id: string;
  name: string;
  category: string;
  partCount: number;
  license: string;
  source: string;
  explode: { mode: string; spread: number };
};

export type HandInput = {
  x: number;
  y: number;
  pinch: boolean;
  handCount: number;
  spread: number;
  openPalm: boolean;
  wristAngle: number;
};

export type ViewerStatus = {
  selectedPart: string;
  hoveredPart: string;
  meshCount: number;
  hierarchyDepth: number;
  explosion: number;
  gesture: string;
  pinchDistance: number;
  depth: number;
  fps: number;
};
