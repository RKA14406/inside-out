import { useCallback, useEffect, useRef, useState } from 'react';
import { InsideOutViewer } from './InsideOutViewer';
import { startHandTracking } from './handTracking';
import type { HandInput, Mode, RetrievalResult, ViewerStatus } from './types';
import './styles.css';

const samples = [
  { id: 'heart', label: 'heart', accent: 'coral' },
  { id: 'engine', label: 'engine', accent: 'blue' },
  { id: 'camera', label: 'camera', accent: 'gold' },
  { id: 'cell', label: 'cell', accent: 'mint' },
];

function sampleBlob(kind: string): Promise<Blob> {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas'); canvas.width = 420; canvas.height = 420;
    const ctx = canvas.getContext('2d')!; ctx.fillStyle = '#fbfaf3'; ctx.fillRect(0, 0, 420, 420); ctx.strokeStyle = '#161b20'; ctx.fillStyle = '#161b20'; ctx.lineWidth = 11; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (kind === 'heart') { ctx.beginPath(); ctx.moveTo(210, 352); ctx.bezierCurveTo(64, 244, 94, 92, 180, 144); ctx.bezierCurveTo(208, 78, 294, 78, 246, 144); ctx.bezierCurveTo(334, 92, 364, 244, 210, 352); ctx.stroke(); ctx.beginPath(); ctx.moveTo(210, 148); ctx.lineTo(210, 310); ctx.moveTo(208, 200); ctx.lineTo(145, 148); ctx.moveTo(212, 228); ctx.lineTo(280, 162); ctx.stroke(); }
    if (kind === 'engine') { ctx.strokeRect(72, 72, 276, 276); ctx.beginPath(); ctx.arc(210, 210, 84, 0, Math.PI * 2); ctx.stroke(); ctx.beginPath(); ctx.arc(210, 210, 20, 0, Math.PI * 2); ctx.fill(); for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; ctx.moveTo(210 + Math.cos(a) * 26, 210 + Math.sin(a) * 26); ctx.lineTo(210 + Math.cos(a) * 70, 210 + Math.sin(a) * 70); } ctx.stroke(); }
    if (kind === 'camera') { ctx.strokeRect(58, 126, 304, 180); ctx.strokeRect(130, 92, 150, 34); ctx.beginPath(); ctx.arc(210, 216, 70, 0, Math.PI * 2); ctx.stroke(); ctx.beginPath(); ctx.arc(210, 216, 22, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.arc(320, 158, 12, 0, Math.PI * 2); ctx.fill(); }
    if (kind === 'cell') { ctx.beginPath(); ctx.ellipse(210, 210, 145, 124, -0.12, 0, Math.PI * 2); ctx.stroke(); ctx.beginPath(); ctx.ellipse(205, 214, 52, 48, 0, 0, Math.PI * 2); ctx.stroke(); [[124,162],[295,164],[126,278],[295,268],[214,112]].forEach(([x,y]) => { ctx.beginPath(); ctx.arc(x,y,16,0,Math.PI*2); ctx.fill(); }); }
    canvas.toBlob((blob) => resolve(blob!), 'image/png');
  });
}

export default function App() {
  const [mode, setMode] = useState<Mode>('capture');
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const [status, setStatus] = useState<ViewerStatus>({ selectedPart: '', hoveredPart: '', meshCount: 0, hierarchyDepth: 0, explosion: 0, gesture: 'waiting', pinchDistance: 0, depth: 0, fps: 60 });
  const [debug, setDebug] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [handState, setHandState] = useState<'loading' | 'ready' | 'unavailable'>('loading');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewerRef = useRef<InsideOutViewer | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const materializeTimer = useRef<number | null>(null);

  useEffect(() => { navigator.mediaDevices?.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }, audio: false }).then((stream) => { streamRef.current = stream; if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); } setCameraReady(true); }).catch(() => setCameraError('Camera unavailable — use a sample drawing or upload an image.')); return () => streamRef.current?.getTracks().forEach((track) => track.stop()); }, []);

  useEffect(() => { const onKey = (event: KeyboardEvent) => { if (event.key.toLowerCase() === 'd') setDebug((value) => !value); if (event.key === 'Escape') viewerRef.current?.reset(); }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, []);

  useEffect(() => { if (mode === 'explore' || mode === 'materialize') { if (canvasRef.current && !viewerRef.current) viewerRef.current = new InsideOutViewer(canvasRef.current, (next) => setStatus((current) => ({ ...current, ...next }))); if (viewerRef.current && result) viewerRef.current.load(result.match); return () => { viewerRef.current?.dispose(); viewerRef.current = null; }; } }, [mode, result]);

  useEffect(() => { if (!videoRef.current || mode === 'capture') return; let stop: (() => void) | undefined; startHandTracking(videoRef.current, (input, landmarks) => { const gesture = input.openPalm ? 'open palm / reset' : input.handCount > 1 ? 'two-hand spread' : input.pinch ? 'pinch + move' : 'point / hover'; viewerRef.current?.setHandState(input); setStatus((current) => ({ ...current, gesture, pinchDistance: input.pinch ? 0.3 : 0.7, depth: Number((1 - input.y).toFixed(2)) })); drawLandmarks(landmarks); }, setHandState).then((cleanup) => { stop = cleanup; }); return () => stop?.(); }, [mode]);

  const drawLandmarks = (landmarks: any[]) => { const overlay = document.querySelector<HTMLCanvasElement>('#hand-overlay'); if (!overlay) return; const ctx = overlay.getContext('2d')!; ctx.clearRect(0, 0, overlay.width, overlay.height); ctx.fillStyle = '#f6c85f'; landmarks.forEach((hand) => hand.forEach((point: any) => { ctx.beginPath(); ctx.arc((1 - point.x) * overlay.width, point.y * overlay.height, 3, 0, Math.PI * 2); ctx.fill(); })); };

  const submitImage = useCallback(async (blob: Blob) => { setProcessing(true); setError(''); const form = new FormData(); form.append('file', blob, 'insideout-sketch.png'); try { const response = await fetch('/api/retrieve', { method: 'POST', body: form }); if (!response.ok) throw new Error('Retrieval service unavailable'); const data = await response.json() as RetrievalResult; setResult(data); setMode('materialize'); if (materializeTimer.current) window.clearTimeout(materializeTimer.current); materializeTimer.current = window.setTimeout(() => setMode('explore'), 1800); } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not analyze this drawing'); } finally { setProcessing(false); } }, []);

  const capture = () => { if (!videoRef.current || !cameraReady) return; const snap = document.createElement('canvas'); snap.width = videoRef.current.videoWidth || 960; snap.height = videoRef.current.videoHeight || 540; snap.getContext('2d')!.drawImage(videoRef.current, 0, 0, snap.width, snap.height); snap.toBlob((blob) => blob && submitImage(blob), 'image/jpeg', 0.92); };
  const upload = (event: React.ChangeEvent<HTMLInputElement>) => { const file = event.target.files?.[0]; if (file) submitImage(file); };

  return <main className="app-shell">
    <header className="topbar"><div className="wordmark"><span className="mark">◎</span><span>INSIDE<span className="accent-text">OUT</span></span></div><div className="mode-track"><span className={mode === 'capture' ? 'active' : ''}>01 draw</span><i></i><span className={mode !== 'capture' ? 'active' : ''}>02 explore</span></div><button className="debug-button" onClick={() => setDebug(!debug)} aria-pressed={debug}>D / DEBUG</button></header>
    {mode === 'capture' ? <section className="capture-layout">
      <div className="capture-copy"><p className="eyebrow">A HAND-CONTROLLED 3D STUDY</p><h1>Draw it.<br /><em>Open it.</em></h1><p className="intro">InsideOut turns a line drawing into an explorable object. Put your sketch in view, then let your hands pull it apart.</p><div className="capture-actions"><button className="primary-action" onClick={capture} disabled={!cameraReady || processing}><span className="rec-dot"></span>{processing ? 'Reading the sketch…' : 'Capture drawing'}</button><label className="upload-action">Upload image<input type="file" accept="image/*" onChange={upload} /></label></div><div className="fallback-note">{cameraError || 'Works with pen, pencil, or marker on ordinary paper.'}</div>{error && <p className="error-note" role="alert">{error}</p>}</div>
      <div className="camera-stage"><video ref={videoRef} className="camera-feed" muted playsInline /><div className="paper-guide"><span className="corner tl"></span><span className="corner tr"></span><span className="corner bl"></span><span className="corner br"></span><div className="scan-line"></div><span className="scan-label">{cameraReady ? 'LOOKING FOR A SKETCH' : 'CAMERA STANDBY'}</span></div><div className="camera-footer"><span><b className={cameraReady ? 'status-live' : ''}></b>{cameraReady ? 'camera live' : 'camera fallback'}</span><span>hold drawing inside frame</span></div></div>
      <aside className="sample-rail"><p className="eyebrow">TRY A STUDY</p><p className="rail-copy">No drawing handy? Use one of the original line studies.</p>{samples.map((sample) => <button key={sample.id} className="sample-button" onClick={() => sampleBlob(sample.id).then(submitImage)}><span className={`sample-icon ${sample.accent}`}>{sample.id === 'heart' ? '♡' : sample.id === 'engine' ? '◉' : sample.id === 'camera' ? '▣' : '◌'}</span><span>{sample.label}</span><span className="arrow">↗</span></button>)}<div className="library-count"><strong>06</strong><span>indexed forms<br />in local library</span></div></aside>
    </section> : <section className="explore-layout"><div className="explore-canvas-wrap"><canvas ref={canvasRef} className="viewer-canvas" /><video ref={videoRef} className="camera-underlay" muted playsInline /><canvas id="hand-overlay" className="hand-overlay" width="640" height="480" /><div className="materialize-copy">{mode === 'materialize' ? <><span className="eyebrow">VISUAL MATCH FOUND</span><strong>materializing<br /><em>{result?.model.name}</em></strong></> : <><span className="eyebrow">EXPLORATION MODE</span><strong>the student's<br /><em>hands are the mouse</em></strong></>}</div><div className="gesture-pill"><span className={handState === 'ready' ? 'pulse' : ''}></span>{handState === 'ready' ? status.gesture : 'mouse fallback active'}</div><button className="reset-button" onClick={() => viewerRef.current?.reset()}>↺ reassemble</button></div><aside className="explore-rail"><div><p className="eyebrow">MATCHED OBJECT</p><h2>{result?.model.name}</h2><p className="category">{result?.model.category} / local visual index</p></div><div className="match-score"><span>similarity</span><strong>{Math.round((result?.confidence ?? 0) * 100)}<small>%</small></strong><div className="score-bar"><i style={{ width: `${(result?.confidence ?? 0) * 100}%` }}></i></div><span className="score-meta">best angle {result?.bestView} · {result?.embeddingMs} ms</span></div><div className="part-readout"><span className="eyebrow">SELECTED PART</span><strong>{status.selectedPart || 'point at a part'}</strong><p>{status.selectedPart ? 'Pinch and move to pull it from the assembly.' : 'Two hands spread the structure. Open palm reassembles.'}</p></div><div className="gesture-list"><div><b>POINT</b><span>hover / select</span></div><div><b>PINCH</b><span>grab / pull</span></div><div><b>SPREAD</b><span>explode structure</span></div><div><b>OPEN PALM</b><span>reset assembly</span></div></div><button className="new-drawing" onClick={() => { setMode('capture'); setResult(null); }}>← draw another</button></aside></section>}
    {debug && <aside className="debug-panel"><div><b>LIVE CV / RENDER TRACE</b><span>press D to hide</span></div><pre>{JSON.stringify({ fps: status.fps, gesture: status.gesture, hands: handState, selectedMesh: status.selectedPart || null, meshCount: status.meshCount, hierarchyDepth: status.hierarchyDepth, explosion: Number(status.explosion.toFixed(2)), depth: status.depth, topCandidates: result?.candidates.map((item) => `${item.name} ${item.score.toFixed(2)}`) ?? [] }, null, 2)}</pre></aside>}
  </main>;
}
