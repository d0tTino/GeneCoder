"""Minimal 3D DNA helix visualization using Three.js and Flet."""

from __future__ import annotations

import flet as ft

HELIX_HTML = """
<div id='helix-container' style='width:100%; height:100%;'></div>
<script type='module'>
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.module.js';
const container = document.getElementById('helix-container');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

const points = [];
for (let i = 0; i < 50; i++) {
    const t = i * 0.2;
    points.push(new THREE.Vector3(Math.cos(t), Math.sin(t), i * 0.1));
}
const geometry = new THREE.BufferGeometry().setFromPoints(points);
const material = new THREE.LineBasicMaterial({ color: 0x0077ff });
const helix = new THREE.Line(geometry, material);
scene.add(helix);

camera.position.z = 5;
function animate() {
    requestAnimationFrame(animate);
    helix.rotation.z += 0.01;
    renderer.render(scene, camera);
}
animate();
</script>
"""

def show_helix() -> ft.HtmlElement:
    """Return an ``HtmlElement`` displaying a basic DNA helix scene."""
    return ft.HtmlElement(content=HELIX_HTML, width=600, height=400)
