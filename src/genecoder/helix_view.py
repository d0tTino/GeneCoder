"""Minimal 3D DNA helix visualization using Three.js and Flet."""

from __future__ import annotations

import flet as ft
from urllib.parse import quote
import base64
import pkgutil

# Flet <0.29 removed ``HtmlElement``. Provide a minimal fallback for tests.
if not hasattr(ft, "HtmlElement"):

    class _HtmlElement:
        """Lightweight stand-in for :class:`flet.HtmlElement`."""

        def __init__(self, *, content: str, width: int = 0, height: int = 0) -> None:
            self.content = content
            self.width = width
            self.height = height

    ft.HtmlElement = _HtmlElement

THREE_JS_URL = ""
ORBIT_JS_URL = ""
try:
    three_data = pkgutil.get_data("genecoder", "static/three.min.js")
    orbit_data = pkgutil.get_data("genecoder", "static/OrbitControls.min.js")
    if three_data:
        THREE_JS_URL = (
            "data:application/javascript;base64,"
            + base64.b64encode(three_data).decode()
        )
    if orbit_data:
        ORBIT_JS_URL = (
            "data:application/javascript;base64,"
            + base64.b64encode(orbit_data).decode()
        )
except FileNotFoundError:
    pass

HELIX_TEMPLATE = """
<div id='helix-container' style='position:relative;width:100%%;height:100%%'></div>
<div id='tooltip' style='position:absolute;display:none;padding:2px;background:#fff;border:1px solid #333;font-size:12px;pointer-events:none'></div>
<canvas id='metrics-overlay' style='position:absolute;top:0;left:0;pointer-events:none;opacity:0.6'></canvas>
<script type='module'>
import * as THREE from '%(THREE_JS_URL)s';
import { OrbitControls } from '%(ORBIT_JS_URL)s';

const container = document.getElementById('helix-container');
const tooltip = document.getElementById('tooltip');
const metricsCanvas = document.getElementById('metrics-overlay');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(2 * %(ZOOM)s, 2 * %(ZOOM)s, 5 * %(ZOOM)s);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);
metricsCanvas.width = container.clientWidth;
metricsCanvas.height = 30;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.update();

const seq = '%(DNA_SEQ)s';
const animateHelix = %(ANIMATE)s;
const bases = [];
for (let i = 0; i < seq.length; i++) {
    const base = seq[i];
    bases.push(base);
}


const colors = { A: 0xff5555, C: 0x5555ff, G: 0x55ff55, T: 0xffff55 };
const group = new THREE.Group();
const radius = 0.1;
const height = 0.4;
for (let i = 0; i < bases.length; i++) {
    const geometry = new THREE.SphereGeometry(radius, 16, 16);
    const material = new THREE.MeshBasicMaterial({ color: colors[bases[i]] || 0xffffff });
    const mesh = new THREE.Mesh(geometry, material);
    const angle = i * 0.3;
    mesh.position.set(Math.cos(angle), Math.sin(angle), i * height);
    mesh.userData = { info: `${bases[i]} (${i})` };
    group.add(mesh);
}
scene.add(group);

const ctx = metricsCanvas.getContext('2d');
const barWidth = metricsCanvas.width / bases.length;
const runs = new Array(bases.length).fill(1);
for (let i = 0; i < bases.length; i++) {
    if (i > 0 && bases[i] === bases[i - 1]) {
        runs[i] = runs[i - 1] + 1;
    }
    const gcColor = bases[i] === 'G' || bases[i] === 'C' ? '#88f' : '#ddd';
    ctx.fillStyle = gcColor;
    ctx.fillRect(i * barWidth, 0, barWidth, 14);
}
for (let i = 0; i < bases.length; i++) {
    const intensity = Math.min(runs[i] / 6, 1);
    ctx.fillStyle = `rgba(255,0,0,${intensity})`;
    ctx.fillRect(i * barWidth, 16, barWidth, 14);
}

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
    metricsCanvas.width = container.clientWidth;
});

let offset = 0;
function animate() {
    requestAnimationFrame(animate);
    if (animateHelix) {
        offset += 0.05;
        for (let i = 0; i < group.children.length; i++) {
            const mesh = group.children[i];
            const angle = i * 0.3 + offset;
            mesh.position.set(Math.cos(angle), Math.sin(angle), i * height);
        }
    }
    controls.update();
    renderer.render(scene, camera);
}
animate();
</script>
"""

def _make_helix_html(dna_sequence: str, animate: bool, zoom: float) -> str:
    return HELIX_TEMPLATE % {
        "THREE_JS_URL": THREE_JS_URL,
        "ORBIT_JS_URL": ORBIT_JS_URL,
        "DNA_SEQ": dna_sequence,
        "ANIMATE": "true" if animate else "false",
        "ZOOM": zoom,
    }


def show_helix(dna_sequence: str = "ACGT", *, animate: bool = True, zoom: float = 1.0) -> ft.WebView:
    """Return a ``WebView`` displaying a DNA helix scene with controls."""
    helix_html = _make_helix_html(dna_sequence, animate, zoom)
    data_url = "data:text/html," + quote(helix_html)

    return ft.WebView(url=data_url, width=600, height=400)
