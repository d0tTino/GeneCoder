import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const DEFAULT_COLORS = {
  A: 0xff5555,
  C: 0x5555ff,
  G: 0x55ff55,
  T: 0xffff55,
};

function parseColors(param) {
  if (!param) return null;
  const map = {};
  param.split(',').forEach((p) => {
    const [b, c] = p.split(':');
    if (b && c) {
      const hex = c.startsWith('#') ? c.slice(1) : c.replace(/^0x/, '');
      map[b.toUpperCase()] = parseInt(hex, 16);
    }
  });
  return map;
}

export default function App() {
  const mount = useRef(null);
  const metricsRef = useRef(null);
  const params = new URLSearchParams(window.location.search);

  const [animate, setAnimate] = useState(params.get('animate') !== 'false');
  const [zoom] = useState(parseFloat(params.get('zoom') || '1'));
  const seq = params.get('seq') || 'ACGT';
  const [showGC, setShowGC] = useState(params.get('gc') !== 'false');
  const [showRuns, setShowRuns] = useState(params.get('runs') !== 'false');

  const colorParam = params.get('colors');
  const colors = { ...DEFAULT_COLORS, ...(parseColors(colorParam) || {}) };

  useEffect(() => {
    const width = mount.current.clientWidth;
    const height = mount.current.clientHeight;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(2 * zoom, 2 * zoom, 5 * zoom);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mount.current.appendChild(renderer.domElement);

    metricsRef.current.width = width;
    metricsRef.current.height = 30;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    const group = new THREE.Group();
    const bases = seq.split('');
    const radius = 0.1;
    const h = 0.4;
    bases.forEach((b, i) => {
      const geom = new THREE.SphereGeometry(radius, 16, 16);
      const mat = new THREE.MeshPhongMaterial({ color: colors[b] || 0xffffff });
      const mesh = new THREE.Mesh(geom, mat);
      const angle = i * 0.3;
      mesh.position.set(Math.cos(angle), Math.sin(angle), i * h);
      group.add(mesh);
    });
    scene.add(group);

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 5, 5);
    scene.add(light);

    const ctx = metricsRef.current.getContext('2d');
    const bw = metricsRef.current.width / bases.length;
    const runs = new Array(bases.length).fill(1);
    for (let i = 0; i < bases.length; i++) {
      if (i > 0 && bases[i] === bases[i - 1]) runs[i] = runs[i - 1] + 1;
      if (showGC) {
        ctx.fillStyle = bases[i] === 'G' || bases[i] === 'C' ? '#88f' : '#ddd';
        ctx.fillRect(i * bw, 0, bw, 14);
      }
    }
    for (let i = 0; i < bases.length; i++) {
      if (showRuns) {
        const intensity = Math.min(runs[i] / 6, 1);
        ctx.fillStyle = `rgba(255,0,0,${intensity})`;
        ctx.fillRect(i * bw, 16, bw, 14);
      }
    }

    let frameId;
    const loop = () => {
      controls.update();
      if (animate) group.rotation.z += 0.01;
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(frameId);
      renderer.dispose();
    };
  }, [seq, animate, zoom, colors, showGC, showRuns]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <canvas
        ref={metricsRef}
        style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', opacity: 0.6 }}
      />
      <div
        style={{ position: 'absolute', top: 10, left: 10, zIndex: 1, background: '#fff', padding: 4, borderRadius: 4 }}
      >
        <label>
          <input type="checkbox" checked={animate} onChange={(e) => setAnimate(e.target.checked)} /> Animate
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showGC} onChange={(e) => setShowGC(e.target.checked)} /> GC
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showRuns} onChange={(e) => setShowRuns(e.target.checked)} /> Runs
        </label>
      </div>
      <div ref={mount} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
