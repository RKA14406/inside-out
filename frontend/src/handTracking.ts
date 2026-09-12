import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';
import type { HandInput } from './types';

const WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm';
const MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

const distance = (a: any, b: any) => Math.hypot(a.x - b.x, a.y - b.y, (a.z ?? 0) - (b.z ?? 0));

function classify(hands: any[]): HandInput {
  const hand = hands[0] ?? [];
  const palm = Math.max(distance(hand[0], hand[9]), 0.001);
  const pinchDistance = hand.length ? distance(hand[4], hand[8]) / palm : 1;
  const pinch = pinchDistance < 0.48;
  const tips = [8, 12, 16, 20];
  const extended = tips.filter((tip) => distance(hand[tip], hand[0]) > distance(hand[tip - 2], hand[0]) * 1.1).length;
  const openPalm = extended >= 4 && !pinch;
  const spread = hands.length > 1 ? Math.min(1, Math.max(0, distance(hands[0][8], hands[1][8]) / 0.9)) : 0;
  const wristAngle = hand.length ? Math.atan2(hand[5].y - hand[17].y, hand[5].x - hand[17].x) : 0;
  return { x: hand.length ? 1 - hand[8].x : 0.5, y: hand.length ? hand[8].y : 0.5, pinch, handCount: hands.length, spread, openPalm, wristAngle };
}

export async function startHandTracking(video: HTMLVideoElement, onInput: (input: HandInput, landmarks: any[]) => void, onState: (state: 'loading' | 'ready' | 'unavailable') => void) {
  let stopped = false;
  let frame = 0;
  try {
    onState('loading');
    const vision = await FilesetResolver.forVisionTasks(WASM);
    const tracker = await HandLandmarker.createFromOptions(vision, { baseOptions: { modelAssetPath: MODEL, delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2, minHandDetectionConfidence: 0.55, minHandPresenceConfidence: 0.55, minTrackingConfidence: 0.55 });
    onState('ready');
    const loop = () => {
      if (stopped) return;
      if (video.readyState >= 2) {
        const result = tracker.detectForVideo(video, performance.now());
        const hands = result.landmarks ?? [];
        onInput(classify(hands), hands);
      }
      frame = requestAnimationFrame(loop);
    };
    loop();
  } catch { onState('unavailable'); }
  return () => { stopped = true; cancelAnimationFrame(frame); };
}
