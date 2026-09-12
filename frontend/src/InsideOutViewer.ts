import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { buildModel } from './modelLibrary';
import type { HandInput, ViewerStatus } from './types';

type StatusCallback = (status: Partial<ViewerStatus>) => void;

export class InsideOutViewer {
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(33, 1, 0.1, 100);
  private renderer: THREE.WebGLRenderer;
  private controls: OrbitControls;
  private root = new THREE.Group();
  private parts: THREE.Group[] = [];
  private selected: THREE.Group | null = null;
  private hovered: THREE.Group | null = null;
  private exploded = 0;
  private lastTime = performance.now();
  private fps = 60;
  private pinching = false;
  private dragOffset = new THREE.Vector3();
  private status: StatusCallback;
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  private frame = 0;

  constructor(private canvas: HTMLCanvasElement, status: StatusCallback) {
    this.status = status;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.camera.position.set(0, 0.15, 7.5);
    this.scene.add(new THREE.HemisphereLight(0xd6f3ef, 0x0b0e12, 2.1));
    const key = new THREE.DirectionalLight(0xffffff, 3.5); key.position.set(-4, 5, 6); key.castShadow = true; this.scene.add(key);
    const rim = new THREE.PointLight(0x4e8dff, 8, 13); rim.position.set(4, 1, 4); this.scene.add(rim);
    const grid = new THREE.GridHelper(12, 24, 0x23303b, 0x172027); grid.position.y = -2.2; grid.rotation.x = 0; this.scene.add(grid);
    this.scene.add(this.root);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true; this.controls.enablePan = false; this.controls.enabled = true;
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerdown', this.onPointerDown);
    window.addEventListener('resize', this.resize);
    this.resize();
    this.animate();
  }

  load(modelId: string) {
    this.root.clear(); this.root.rotation.set(0, 0, 0); this.exploded = 0; this.selected = null;
    this.root.add(buildModel(modelId));
    const container = this.root.children[0] as THREE.Group;
    this.parts = container.children.filter((child): child is THREE.Group => child instanceof THREE.Group);
    const box = new THREE.Box3().setFromObject(this.root); const size = box.getSize(new THREE.Vector3());
    const scale = 3.45 / Math.max(size.x, size.y, size.z, 1); this.root.scale.setScalar(scale);
    this.root.position.set(0, 0.1, 0);
    this.emitStatus();
  }

  setHandState(input: HandInput) {
    this.pointer.set(input.x * 2 - 1, -(input.y * 2 - 1));
    const target = this.pick(this.pointer);
    this.setHovered(target);
    if (input.handCount > 1) this.setExplosion(input.spread);
    if (input.openPalm) this.reset();
    if (input.pinch && !this.pinching && target) {
      this.selected = target; this.pinching = true;
      const hit = this.worldPoint(this.pointer); if (hit) this.dragOffset.copy(target.position).sub(hit);
      this.emitStatus();
    }
    if (input.pinch && this.pinching && this.selected) {
      const hit = this.worldPoint(this.pointer);
      if (hit) this.selected.position.lerp(hit.clone().add(this.dragOffset), 0.28);
      this.emitStatus({ depth: Number((1 - input.y).toFixed(2)) });
    }
    if (!input.pinch && this.pinching) { this.pinching = false; this.snapSelected(); }
  }

  setExplosion(amount: number) {
    this.exploded = THREE.MathUtils.lerp(this.exploded, THREE.MathUtils.clamp(amount, 0, 1), 0.12);
    this.parts.forEach((part) => {
      const original = part.userData.basePosition as THREE.Vector3;
      const dir = original.clone().normalize(); if (dir.lengthSq() < 0.01) dir.set(0, 1, 0);
      const distance = (part.userData.level === 1 ? 1.15 : 1.55) * this.exploded;
      const target = original.clone().add(dir.normalize().multiplyScalar(distance));
      if (part !== this.selected || !this.pinching) part.position.lerp(target, 0.1);
    });
    this.emitStatus({ explosion: this.exploded });
  }

  reset() { this.exploded = 0; this.selected = null; this.parts.forEach((part) => part.position.copy(part.userData.basePosition)); this.emitStatus({ selectedPart: '' }); }

  dispose() { cancelAnimationFrame(this.frame); window.removeEventListener('resize', this.resize); this.canvas.removeEventListener('pointermove', this.onPointerMove); this.canvas.removeEventListener('pointerdown', this.onPointerDown); this.renderer.dispose(); this.controls.dispose(); }

  private animate = () => { this.frame = requestAnimationFrame(this.animate); const now = performance.now(); const delta = now - this.lastTime; this.lastTime = now; this.fps = Math.round(1000 / Math.max(delta, 1)); this.controls.update(); this.renderer.render(this.scene, this.camera); this.status({ fps: this.fps }); };
  private resize = () => { const rect = this.canvas.getBoundingClientRect(); if (!rect.width || !rect.height) return; this.camera.aspect = rect.width / rect.height; this.camera.updateProjectionMatrix(); this.renderer.setSize(rect.width, rect.height, false); };
  private pick(pointer: THREE.Vector2) { this.raycaster.setFromCamera(pointer, this.camera); const hits = this.raycaster.intersectObjects(this.parts, true); if (!hits.length) return null; let node: THREE.Object3D | null = hits[0].object; while (node && !node.userData.partId) node = node.parent; return node as THREE.Group | null; }
  private worldPoint(pointer: THREE.Vector2) { this.raycaster.setFromCamera(pointer, this.camera); const point = new THREE.Vector3(); return this.raycaster.ray.intersectPlane(this.plane, point) ? point : null; }
  private setHovered(group: THREE.Group | null) { if (this.hovered === group) return; if (this.hovered) this.tint(this.hovered, false); this.hovered = group; if (group) this.tint(group, true); this.emitStatus({ hoveredPart: group?.userData.partName ?? '' }); }
  private tint(group: THREE.Group, active: boolean) { group.traverse((node) => { const material = (node as THREE.Mesh).material as THREE.MeshStandardMaterial; if (material?.emissive) material.emissive.set(active ? 0x284f5d : new THREE.Color(material.color).multiplyScalar(0.05)); }); }
  private snapSelected() { if (!this.selected) return; const origin = this.selected.userData.basePosition as THREE.Vector3; if (this.selected.position.distanceTo(origin) < 0.48) this.selected.position.lerp(origin, 0.8); }
  private emitStatus(extra: Partial<ViewerStatus> = {}) { this.status({ selectedPart: this.selected?.userData.partName ?? '', hoveredPart: this.hovered?.userData.partName ?? '', meshCount: this.parts.length, hierarchyDepth: this.parts.length ? Math.max(...this.parts.map((part) => part.userData.level as number)) : 0, explosion: this.exploded, ...extra }); }
  private onPointerMove = (event: PointerEvent) => { const rect = this.canvas.getBoundingClientRect(); this.pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -(((event.clientY - rect.top) / rect.height) * 2 - 1)); this.setHovered(this.pick(this.pointer)); };
  private onPointerDown = () => { const target = this.pick(this.pointer); if (target) { this.selected = target; this.emitStatus(); } };
}
