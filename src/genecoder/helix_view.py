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

# Default colors used for nucleotide spheres in the helix view.
DEFAULT_COLORS: dict[str, int] = {
    "A": 0xFF5555,
    "C": 0x5555FF,
    "G": 0x55FF55,
    "T": 0xFFFF55,
}

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
    bases.push(seq[i]);

}


const colors = %(COLOR_MAP)s;
const group = new THREE.Group();
const radius = 0.1;
const height = 0.4;
for (let i = 0; i < bases.length; i++) {
    const geometry = new THREE.SphereGeometry(radius, 16, 16);
    const material = new THREE.MeshPhongMaterial({ color: colors[bases[i]] || 0xffffff });
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
let highlighted = null;
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
        if (highlighted && highlighted !== hit.object) {
            highlighted.material.emissive.set(0x000000);
        }
        highlighted = hit.object;
        highlighted.material.emissive.set(0x333333);
    } else {
        tooltip.style.display = 'none';
        if (highlighted) {
            highlighted.material.emissive.set(0x000000);
            highlighted = null;
        }
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
    group.rotation.z += 0.01;

    controls.update();
    renderer.render(scene, camera);
}
animate();
</script>
"""

def _make_helix_html(
    dna_sequence: str,
    *,
    animate: bool = True,
    zoom: float = 1.0,
    length: int | None = None,
    colors: dict[str, int] | None = None,
) -> str:
    """Return HTML for the helix viewer.

    Parameters
    ----------
    dna_sequence:
        Base sequence used for rendering.
    animate:
        Whether to animate rotation of the helix.
    zoom:
        Camera zoom level.
    length:
        Optional length of the rendered helix. The sequence is repeated as
        needed.
    colors:
        Optional mapping of nucleotide to hex color value or string.
    """
    if length is not None:
        repeats = (length + len(dna_sequence) - 1) // len(dna_sequence)
        dna_sequence = (dna_sequence * repeats)[:length]

    color_map = DEFAULT_COLORS.copy()
    if colors:
        for base, col in colors.items():
            if isinstance(col, str):
                col = int(col.lstrip("#").removeprefix("0x"), 16)
            color_map[base.upper()] = col

    colors_js = "{ " + ", ".join(f"{b}: 0x{v:06x}" for b, v in color_map.items()) + " }"

    return HELIX_TEMPLATE % {
        "THREE_JS_URL": THREE_JS_URL,
        "ORBIT_JS_URL": ORBIT_JS_URL,
        "DNA_SEQ": dna_sequence,
        "COLOR_MAP": colors_js,
        "ANIMATE": "true" if animate else "false",
        "ZOOM": zoom,
    }


def show_helix(
    dna_sequence: str = "ACGT",
    *,
    animate: bool = True,
    zoom: float = 1.0,
    length: int | None = None,
    colors: dict[str, int] | None = None,
) -> ft.WebView:
    """Return a ``WebView`` displaying a DNA helix scene with controls.

    Parameters
    ----------
    dna_sequence:
        Base sequence used for rendering.
    animate:
        Whether to animate rotation of the helix.
    zoom:
        Camera zoom level.
    length:
        Optional length of the rendered helix. The sequence is repeated as
        needed.
    colors:
        Mapping of nucleotide to hex color value or string.
    """
    helix_html = _make_helix_html(
        dna_sequence,
        animate=animate,
        zoom=zoom,
        length=length,
        colors=colors,
    )

    data_url = "data:text/html," + quote(helix_html)

    return ft.WebView(url=data_url, width=600, height=400)
