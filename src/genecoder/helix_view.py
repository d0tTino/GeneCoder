"""Minimal 3D DNA helix visualization using Three.js and Flet."""

from __future__ import annotations

import flet as ft
from urllib.parse import quote

# Flet <0.29 removed ``HtmlElement``. Provide a minimal fallback for tests.
if not hasattr(ft, "HtmlElement"):
    class _HtmlElement:
        """Lightweight stand-in for :class:`flet.HtmlElement`."""

        def __init__(self, *, content: str, width: int = 0, height: int = 0) -> None:
            self.content = content
            self.width = width
            self.height = height

    ft.HtmlElement = _HtmlElement  # type: ignore[attr-defined]

HELIX_HTML = """
<div id='helix-container' style='position:relative;width:100%;height:100%'></div>
<div id='tooltip' style='position:absolute;display:none;padding:2px;background:#fff;border:1px solid #333;font-size:12px'></div>
<script type='module'>
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.150.1/examples/jsm/controls/OrbitControls.js';

const container = document.getElementById('helix-container');
const tooltip = document.getElementById('tooltip');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
camera.position.set(2, 2, 5);
controls.update();

const text = 'GeneCoder';
const bytes = new TextEncoder().encode(text);
const bases = [];
const bits = [];
for (const byte of bytes) {
    for (let shift = 6; shift >= 0; shift -= 2) {
        const val = (byte >> shift) & 3;
        const base = ['A', 'C', 'G', 'T'][val];
        bases.push(base);
        bits.push(`${byte.toString(16).padStart(2,'0')}[${val.toString(2).padStart(2,'0')}]`);
    }
}

const colors = { A: 0xff5555, C: 0x5555ff, G: 0x55ff55, T: 0xffff55 };
const group = new THREE.Group();
const radius = 0.1;
const height = 0.4;
for (let i = 0; i < bases.length; i++) {
    const geometry = new THREE.SphereGeometry(radius, 16, 16);
    const material = new THREE.MeshBasicMaterial({ color: colors[bases[i]] });
    const mesh = new THREE.Mesh(geometry, material);
    const angle = i * 0.3;
    mesh.position.set(Math.cos(angle), Math.sin(angle), i * height);
    mesh.userData = { info: bits[i] };
    group.add(mesh);
}
scene.add(group);

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
function onMouseMove(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hit = raycaster.intersectObjects(group.children)[0];
    if (hit) {
        tooltip.style.display = 'block';
        tooltip.style.left = `${event.clientX + 5}px`;
        tooltip.style.top = `${event.clientY + 5}px`;
        tooltip.textContent = hit.object.userData.info;
    } else {
        tooltip.style.display = 'none';
    }
}
renderer.domElement.addEventListener('mousemove', onMouseMove);

window.addEventListener('resize', () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
});

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
animate();
</script>
"""

def show_helix() -> ft.WebView:
    """Return a ``WebView`` displaying a DNA helix scene with controls."""
    data_url = "data:text/html," + quote(HELIX_HTML)
    return ft.WebView(url=data_url, width=600, height=400)
