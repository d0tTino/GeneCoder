import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import applyGlossary from './glossary.js';

const DEFAULT_COLORS = {
  A: 0xff5555,
  C: 0x5555ff,
  G: 0x55ff55,
  T: 0xffff55,
};

function complementSeq(s) {
  const map = { A: 'T', T: 'A', C: 'G', G: 'C' };
  return s
    .split('')
    .map((b) => map[b.toUpperCase()] || b)
    .join('');
}

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
  const seqParam = params.get('seq') || 'ACGT';
  const seq2Param = params.get('seq2');
  const [sequence, setSequence] = useState(seqParam);
  const [sequence2, setSequence2] = useState(seq2Param || complementSeq(seqParam));
  const wsUrl = params.get('ws');
  const gcRatio = sequence.split('').filter((b) => b === 'G' || b === 'C').length / sequence.length;
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
    applyGlossary();
  }, []);

  useEffect(() => {
    if (!wsUrl) return;
    const ws = new WebSocket(wsUrl);
    ws.addEventListener('message', (e) => {
      const chunk = e.data;
      setSequence((prev) => prev + chunk);
      if (!seq2Param) {
        setSequence2((prev) => prev + complementSeq(chunk));
      }
    });
    return () => ws.close();
  }, [wsUrl]);

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
    const bases = sequence.split('');
    const compBases = sequence2.split('');
    const len = Math.min(bases.length, compBases.length);
    const runs = new Array(bases.length).fill(1);
    for (let i = 1; i < bases.length; i++) {
      runs[i] = bases[i] === bases[i - 1] ? runs[i - 1] + 1 : 1;
    }
    const radius = 0.1;
    const h = 0.4;
    for (let i = 0; i < len; i++) {
      const angle = i * 0.3;

      const geom1 = new THREE.SphereGeometry(radius, 16, 16);
      let color1 = colors[bases[i]] || 0xffffff;
      if (showGC) {
        color1 = bases[i] === 'G' || bases[i] === 'C' ? 0x8888ff : 0xffffaa;
      }
      const mesh1 = new THREE.Mesh(geom1, new THREE.MeshPhongMaterial({ color: color1 }));
      mesh1.position.set(Math.cos(angle), Math.sin(angle), i * h);
      if (showRuns && runs[i] >= 3) {
        mesh1.material.emissive = new THREE.Color(0xff0000);
        mesh1.material.emissiveIntensity = Math.min((runs[i] - 2) / 4, 1);
      }
      group.add(mesh1);

      const geom2 = new THREE.SphereGeometry(radius, 16, 16);
      let color2 = colors[compBases[i]] || 0xffffff;
      if (showGC) {
        color2 = compBases[i] === 'G' || compBases[i] === 'C' ? 0x8888ff : 0xffffaa;
      }
      const mesh2 = new THREE.Mesh(geom2, new THREE.MeshPhongMaterial({ color: color2 }));
      mesh2.position.set(-Math.cos(angle), -Math.sin(angle), i * h);
      group.add(mesh2);

      const pts = [
        new THREE.Vector3(Math.cos(angle), Math.sin(angle), i * h),
        new THREE.Vector3(-Math.cos(angle), -Math.sin(angle), i * h)
      ];
      const lineGeom = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(lineGeom, new THREE.LineBasicMaterial({ color: 0xaaaaaa }));
      group.add(line);
    }
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
  }, [sequence, sequence2, animate, zoom, colors, showGC, showRuns, showGCBars, showRunBars, showPulses, pulseSpeed, showGauge, flashErrors]);

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
