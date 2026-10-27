import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import "./molecule.css";

const ATOM_RADIUS = 0.4;
const BOND_RADIUS = 0.12;
const BOND_ORDER_OFFSET = 0.16;

function buildMolecule(container, atoms, bonds) {
  const group = new THREE.Group();
  const atomMeshes = [];

  for (const atom of atoms) {
    const geo = new THREE.SphereGeometry(ATOM_RADIUS, 24, 24);
    const mat = new THREE.MeshStandardMaterial({ color: atom.color, roughness: 0.4, metalness: 0.1 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(atom.x, atom.y, atom.z);
    group.add(mesh);
    atomMeshes.push(mesh);
  }

  for (const bond of bonds) {
    const a = atoms[bond.a];
    const b = atoms[bond.b];
    if (!a || !b) continue;
    const start = new THREE.Vector3(a.x, a.y, a.z);
    const end = new THREE.Vector3(b.x, b.y, b.z);
    const order = bond.order || 1;
    const offsets = [];
    for (let i = 0; i < order; i++) {
      offsets.push((i - (order - 1) / 2) * BOND_ORDER_OFFSET);
    }
    for (const off of offsets) {
      group.add(makeBond(start, end, off));
    }
  }
  container.add(group);
  return group;
}

function makeBond(start, end, offset) {
  const dir = new THREE.Vector3().subVectors(end, start);
  const length = dir.length();
  const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);

  const geo = new THREE.CylinderGeometry(BOND_RADIUS, BOND_RADIUS, length, 12);
  const mat = new THREE.MeshStandardMaterial({ color: "#999999", roughness: 0.5 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.copy(mid);

  // Orient the cylinder along `dir`.
  const axis = dir.clone().normalize();
  const up = new THREE.Vector3(0, 1, 0);
  const quat = new THREE.Quaternion().setFromUnitVectors(up, axis);
  mesh.setRotationFromQuaternion(quat);

  // Perpendicular offset for multiple bonds.
  if (offset) {
    const perp = new THREE.Vector3(-axis.z, 0, axis.x).normalize();
    if (perp.length() < 0.001) perp.set(1, 0, 0);
    mesh.position.addScaledVector(perp, offset);
  }
  return mesh;
}

export default function MoleculeViewer({ atoms, bonds, spin = false }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !atoms || atoms.length === 0) return;

    const width = mount.clientWidth;
    const height = mount.clientHeight || 400;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(6, 4, 8);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(10, 10, 10);
    scene.add(light);

    const molecule = buildMolecule(scene, atoms, bonds);

    // Center the molecule.
    const box = new THREE.Box3().setFromObject(molecule);
    const center = box.getCenter(new THREE.Vector3());
    molecule.position.sub(center);
    const size = box.getSize(new THREE.Vector3()).length();
    const dist = Math.max(size * 1.8, 5);
    camera.position.set(dist, dist * 0.6, dist);
    camera.lookAt(0, 0, 0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      if (spin) molecule.rotation.y += 0.005;
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [atoms, bonds, spin]);

  return <div ref={mountRef} className="molecule-viewer" />;
}
