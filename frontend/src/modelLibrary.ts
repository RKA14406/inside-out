import * as THREE from 'three';

type PartSpec = {
  id: string;
  name: string;
  level: number;
  position: [number, number, number];
  color: number;
  build: () => THREE.Object3D;
};

const material = (color: number, metalness = 0.15) => new THREE.MeshStandardMaterial({
  color, roughness: 0.32, metalness, emissive: new THREE.Color(color).multiplyScalar(0.05),
});

const mesh = (geometry: THREE.BufferGeometry, color: number, metalness = 0.15) => new THREE.Mesh(geometry, material(color, metalness));
const sphere = (size: number, color: number) => mesh(new THREE.SphereGeometry(size, 28, 20), color);
const box = (size: [number, number, number], color: number, metalness = 0.15) => mesh(new THREE.BoxGeometry(...size), color, metalness);
const cylinder = (radius: number, height: number, color: number, rotation = false) => {
  const item = mesh(new THREE.CylinderGeometry(radius, radius * 0.92, height, 28), color, 0.5);
  if (rotation) item.rotation.z = Math.PI / 2;
  return item;
};
const torus = (radius: number, tube: number, color: number) => mesh(new THREE.TorusGeometry(radius, tube, 16, 48), color, 0.55);

function part(spec: PartSpec): THREE.Group {
  const group = new THREE.Group();
  group.name = spec.name;
  group.position.set(...spec.position);
  group.userData = { partId: spec.id, partName: spec.name, level: spec.level, basePosition: group.position.clone() };
  group.add(spec.build());
  return group;
}

function specsFor(id: string): PartSpec[] {
  const cyan = 0x5ee7d2;
  const coral = 0xff6b52;
  const gold = 0xf6c85f;
  const blue = 0x4e8dff;
  const cream = 0xe8e5d6;
  const violet = 0xb78cff;
  if (id === 'heart_001') return [
    { id: 'heart-body', name: 'Heart wall', level: 1, position: [0, 0, 0], color: coral, build: () => { const g = new THREE.Group(); const a = sphere(0.82, coral); a.scale.set(1.05, 1.12, 0.74); a.position.x = -0.42; const b = sphere(0.82, coral); b.scale.set(1.05, 1.12, 0.74); b.position.x = 0.42; g.add(a, b); return g; } },
    { id: 'left-ventricle', name: 'Left ventricle', level: 2, position: [-0.38, -0.2, 0.44], color: 0xff9a7c, build: () => { const m = sphere(0.47, 0xff9a7c); m.scale.set(0.82, 1.15, 0.7); return m; } },
    { id: 'right-ventricle', name: 'Right ventricle', level: 2, position: [0.38, -0.2, 0.44], color: 0xff8065, build: () => { const m = sphere(0.47, 0xff8065); m.scale.set(0.82, 1.15, 0.7); return m; } },
    { id: 'aorta', name: 'Aorta', level: 1, position: [-0.32, 1.04, 0], color: gold, build: () => cylinder(0.18, 0.86, gold) },
    { id: 'pulmonary-artery', name: 'Pulmonary artery', level: 1, position: [0.33, 1.04, 0.08], color: blue, build: () => cylinder(0.15, 0.74, blue) },
    { id: 'septum', name: 'Septum', level: 2, position: [0, 0.02, 0.73], color: cream, build: () => box([0.08, 1.42, 0.08], cream) },
    { id: 'mitral-valve', name: 'Mitral valve', level: 2, position: [-0.38, -0.02, 0.9], color: violet, build: () => torus(0.2, 0.045, violet) },
    { id: 'tricuspid-valve', name: 'Tricuspid valve', level: 2, position: [0.38, -0.02, 0.9], color: violet, build: () => torus(0.2, 0.045, violet) },
  ];
  if (id === 'engine_001') return [
    { id: 'engine-case', name: 'Engine case', level: 1, position: [0, 0, 0], color: blue, build: () => cylinder(1.24, 0.55, blue) },
    { id: 'crankshaft', name: 'Crankshaft', level: 1, position: [0, 0, 0.52], color: gold, build: () => cylinder(0.22, 1.7, gold) },
    ...Array.from({ length: 6 }, (_, i) => ({ id: `piston-${i + 1}`, name: `Piston ${i + 1}`, level: 2, position: [Math.cos(i * Math.PI / 3) * 0.8, Math.sin(i * Math.PI / 3) * 0.8, 0.45] as [number, number, number], color: i % 2 ? coral : cyan, build: () => { const g = new THREE.Group(); const p = cylinder(0.17, 0.72, i % 2 ? coral : cyan); p.rotation.x = Math.PI / 2; g.add(p); return g; } })),
  ];
  if (id === 'camera_001') return [
    { id: 'camera-body', name: 'Camera body', level: 1, position: [0, 0, 0], color: blue, build: () => box([2.6, 1.5, 0.82], blue, 0.45) },
    { id: 'lens-barrel', name: 'Lens barrel', level: 1, position: [0, -0.03, 0.7], color: cream, build: () => cylinder(0.7, 0.65, cream) },
    { id: 'lens-glass', name: 'Optical glass', level: 2, position: [0, -0.03, 1.07], color: cyan, build: () => cylinder(0.48, 0.12, cyan) },
    { id: 'viewfinder', name: 'Viewfinder', level: 2, position: [-0.62, 0.9, 0], color: gold, build: () => box([0.46, 0.28, 0.5], gold) },
    { id: 'shutter', name: 'Shutter button', level: 2, position: [0.72, 0.85, 0], color: coral, build: () => sphere(0.13, coral) },
    { id: 'film-door', name: 'Film door', level: 2, position: [0, 0, -0.48], color: violet, build: () => box([1.55, 0.9, 0.07], violet) },
  ];
  if (id === 'telescope_001') return [
    { id: 'tube', name: 'Optical tube', level: 1, position: [0, 0.55, 0], color: cream, build: () => { const m = cylinder(0.45, 2.7, cream, true); return m; } },
    { id: 'front-lens', name: 'Front lens', level: 2, position: [1.38, 0.55, 0], color: cyan, build: () => { const m = cylinder(0.37, 0.14, cyan, true); return m; } },
    { id: 'mount', name: 'Azimuth mount', level: 1, position: [0, -0.35, 0], color: blue, build: () => cylinder(0.42, 0.52, blue) },
    { id: 'tripod', name: 'Tripod', level: 1, position: [0, -1.22, 0], color: gold, build: () => { const g = new THREE.Group(); [[-0.62, -0.7], [0.62, -0.7], [0, 0.72]].forEach(([x, z]) => { const m = cylinder(0.09, 1.6, gold); m.rotation.z = x * 0.5; m.rotation.x = z * 0.35; m.position.set(x * 0.55, 0, z * 0.2); g.add(m); }); return g; } },
    { id: 'focus-wheel', name: 'Focus wheel', level: 2, position: [0, 0.08, 0.52], color: coral, build: () => torus(0.18, 0.07, coral) },
  ];
  if (id === 'cell_001') return [
    { id: 'membrane', name: 'Cell membrane', level: 1, position: [0, 0, 0], color: cyan, build: () => { const m = new THREE.Mesh(new THREE.SphereGeometry(1.35, 32, 24), new THREE.MeshStandardMaterial({ color: cyan, transparent: true, opacity: 0.3, roughness: 0.22 })); m.scale.set(1.25, 0.92, 0.74); return m; } },
    { id: 'nucleus', name: 'Nucleus', level: 1, position: [0, 0, 0.12], color: violet, build: () => { const m = sphere(0.62, violet); m.scale.set(1.05, 0.9, 0.75); return m; } },
    { id: 'mitochondria-1', name: 'Mitochondrion A', level: 2, position: [-0.82, 0.42, 0.15], color: gold, build: () => { const m = sphere(0.2, gold); m.scale.set(1.5, 0.7, 0.7); return m; } },
    { id: 'mitochondria-2', name: 'Mitochondrion B', level: 2, position: [0.85, -0.38, 0.14], color: gold, build: () => { const m = sphere(0.2, gold); m.scale.set(1.5, 0.7, 0.7); return m; } },
    { id: 'ribosome-1', name: 'Ribosome A', level: 2, position: [-0.9, -0.4, 0.3], color: coral, build: () => sphere(0.13, coral) },
    { id: 'ribosome-2', name: 'Ribosome B', level: 2, position: [0.74, 0.55, 0.35], color: coral, build: () => sphere(0.13, coral) },
    { id: 'golgi', name: 'Golgi apparatus', level: 2, position: [0.58, 0.08, 0.65], color: blue, build: () => torus(0.32, 0.1, blue) },
  ];
  return [
    { id: 'satellite-body', name: 'Satellite bus', level: 1, position: [0, 0, 0], color: cream, build: () => box([0.9, 1.3, 0.9], cream, 0.4) },
    { id: 'solar-left', name: 'Left solar panel', level: 1, position: [-1.34, 0, 0], color: blue, build: () => box([1.1, 0.12, 0.82], blue, 0.35) },
    { id: 'solar-right', name: 'Right solar panel', level: 1, position: [1.34, 0, 0], color: blue, build: () => box([1.1, 0.12, 0.82], blue, 0.35) },
    { id: 'antenna', name: 'High-gain antenna', level: 1, position: [0, 1.2, 0], color: gold, build: () => { const m = cylinder(0.07, 1.0, gold); m.rotation.z = Math.PI / 2; return m; } },
    { id: 'camera-eye', name: 'Earth-observation camera', level: 2, position: [0, 0, 0.58], color: cyan, build: () => sphere(0.22, cyan) },
    { id: 'mast', name: 'Instrument mast', level: 2, position: [0, -1.05, 0], color: coral, build: () => cylinder(0.08, 0.7, coral) },
  ];
}

export function buildModel(id: string): THREE.Group {
  const root = new THREE.Group();
  root.name = id;
  const parts = specsFor(id);
  parts.forEach((spec) => root.add(part(spec)));
  return root;
}
