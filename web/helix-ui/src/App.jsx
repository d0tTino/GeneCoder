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
  const gcRatio = seq.split('').filter((b) => b === 'G' || b === 'C').length / seq.length;
  const [showGC, setShowGC] = useState(params.get('gc') !== 'false');
  const [showRuns, setShowRuns] = useState(params.get('runs') !== 'false');
  const [showGCBars, setShowGCBars] = useState(params.get('gc_bars') === 'true');
  const [showRunBars, setShowRunBars] = useState(params.get('run_bars') === 'true');
  const [showPulses, setShowPulses] = useState(params.get('pulse') === 'true');
  const [pulseSpeed] = useState(parseFloat(params.get('pulse_speed') || '2'));
  const [showGauge, setShowGauge] = useState(params.get('gauge') !== 'false');
  const [flashErrors, setFlashErrors] = useState(params.get('flash') === 'true');

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
    const runs = new Array(bases.length).fill(1);
    for (let i = 1; i < bases.length; i++) {
      runs[i] = bases[i] === bases[i - 1] ? runs[i - 1] + 1 : 1;
    }
    const radius = 0.1;
    const h = 0.4;
    bases.forEach((b, i) => {
      const geom = new THREE.SphereGeometry(radius, 16, 16);
      let color = colors[b] || 0xffffff;
      if (showGC) {
        color = b === 'G' || b === 'C' ? 0x8888ff : 0xffffaa;
      }
      const mat = new THREE.MeshPhongMaterial({ color });
      const mesh = new THREE.Mesh(geom, mat);
      const angle = i * 0.3;
      mesh.position.set(Math.cos(angle), Math.sin(angle), i * h);
      if (showRuns && runs[i] >= 3) {
        mesh.material.emissive = new THREE.Color(0xff0000);
        mesh.material.emissiveIntensity = Math.min((runs[i] - 2) / 4, 1);
      }
      group.add(mesh);
    });
    scene.add(group);

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 5, 5);
    scene.add(light);

    const ctx = metricsRef.current.getContext('2d');
    const bw = metricsRef.current.width / bases.length;
    for (let i = 0; i < bases.length; i++) {
      if (showGCBars) {
        ctx.fillStyle = bases[i] === 'G' || bases[i] === 'C' ? '#88f' : '#ddd';
        ctx.fillRect(i * bw, 0, bw, 14);
      }
      if (showRunBars) {
        const intensity = Math.min(runs[i] / 6, 1);
        ctx.fillStyle = `rgba(255,0,0,${intensity})`;
        ctx.fillRect(i * bw, 16, bw, 14);
      }
    }
    if (showGauge) {
      ctx.fillStyle = '#ddd';
      ctx.fillRect(0, 28, metricsRef.current.width, 2);
      ctx.fillStyle = '#88f';
      ctx.fillRect(0, 28, metricsRef.current.width * gcRatio, 2);
    }

    let frameId;
    let pulsePhase = 0;
    let flashPhase = 0;
    const loop = () => {
      controls.update();
      if (animate) group.rotation.z += 0.01;
      if (showPulses) {
        pulsePhase += 0.05 * pulseSpeed;
        group.children.forEach((mesh, i) => {
          const scale = 1 + 0.3 * Math.sin(pulsePhase - i * 0.5);
          mesh.scale.set(scale, scale, scale);
        });
      } else {
        group.children.forEach((mesh) => mesh.scale.set(1, 1, 1));
      }
      if (flashErrors) {
        flashPhase += 0.1;
        group.children.forEach((mesh, i) => {
          const intensity = 0.5 + 0.5 * Math.sin(flashPhase - i * 0.3);
          mesh.material.emissive = new THREE.Color(0xff00ff);
          mesh.material.emissiveIntensity = intensity;
        });
      }
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(frameId);
      renderer.dispose();
    };
  }, [seq, animate, zoom, colors, showGC, showRuns, showGCBars, showRunBars, showPulses, pulseSpeed, showGauge, flashErrors]);

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
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showGCBars} onChange={(e) => setShowGCBars(e.target.checked)} /> GC Bars
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showRunBars} onChange={(e) => setShowRunBars(e.target.checked)} /> Run Bars
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showPulses} onChange={(e) => setShowPulses(e.target.checked)} /> Pulse
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={showGauge} onChange={(e) => setShowGauge(e.target.checked)} /> Gauge
        </label>
        <label style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={flashErrors} onChange={(e) => setFlashErrors(e.target.checked)} /> Errors
        </label>
        {showGauge && (
          <div style={{ marginTop: 4 }}>
            <div style={{ width: 100, height: 6, background: '#eee' }}>
              <div style={{ width: `${gcRatio * 100}%`, height: '100%', background: '#88f' }} />
            </div>
            <div style={{ fontSize: 10 }}>{Math.round(gcRatio * 100)}% GC</div>
          </div>
        )}
      </div>
      <div ref={mount} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
