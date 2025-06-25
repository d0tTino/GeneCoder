"""Minimal 3D DNA helix visualization using Three.js and Flet."""

from __future__ import annotations

import flet as ft
import flet_webview
from urllib.parse import quote
import base64
import pkgutil
import logging
from pathlib import Path

# Flet <0.29 removed ``HtmlElement``. Provide a minimal fallback for tests.
if not hasattr(ft, "HtmlElement"):

    class _HtmlElement:
        """Lightweight stand-in for :class:`flet.HtmlElement`."""

        def __init__(self, *, content: str, width: int = 0, height: int = 0) -> None:
            self.content: str = content
            self.width: int = width
            self.height: int = height

    ft.HtmlElement = _HtmlElement

logger = logging.getLogger(__name__)

THREE_JS_URL: str = ""
ORBIT_JS_URL: str = ""
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

CDN_THREE_JS_URL = (
    "https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.module.min.js"
)
CDN_ORBIT_JS_URL = (
    "https://cdn.jsdelivr.net/npm/three@0.150.1/examples/jsm/controls/OrbitControls.js"
)

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
const showPulses = %(PULSE)s;
const pulseSpeed = %(PULSE_SPEED)s;
const fps = %(FPS)s;
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
let last = 0;
function animate(now) {
    requestAnimationFrame(animate);
    if (now - last < 1000 / fps) return;
    last = now;
    if (animateHelix) {
        group.rotation.z += 0.01;
    }
    if (showPulses) {
        offset += 0.05 * pulseSpeed;
        group.children.forEach((m, i) => {
            const s = 1 + 0.3 * Math.sin(offset - i * 0.5);
            m.scale.set(s, s, s);
        });
    } else {
        group.children.forEach((m) => m.scale.set(1, 1, 1));
    }

    controls.update();
    renderer.render(scene, camera);
}
requestAnimationFrame(animate);
</script>
"""

def _make_helix_html(
    dna_sequence: str,
    *,
    length: int | None = None,
    colors: dict[str, int] | None = None,
    animate: bool = True,
    zoom: float = 1.0,
    pulse: bool = False,
    pulse_speed: float = 2.0,
    fps: float = 60.0,
    three_js_url: str = THREE_JS_URL,
    orbit_js_url: str = ORBIT_JS_URL,
) -> str:
    """Return HTML for the helix viewer.

    Parameters
    ----------
    dna_sequence:
        Base sequence used for rendering.
    length:
        Optional length of the rendered helix. The sequence is repeated as
        needed.
    colors:
        Optional mapping of nucleotide to hex color value or string.
    pulse:
        Enable pulsing animation of the helix segments.
    pulse_speed:
        Speed multiplier for the pulse animation.
    fps:
        Frames per second for rendering. Lower values reduce CPU usage.
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
        "THREE_JS_URL": three_js_url,
        "ORBIT_JS_URL": orbit_js_url,
        "DNA_SEQ": dna_sequence,
        "COLOR_MAP": colors_js,
        "ANIMATE": "true" if animate else "false",
        "ZOOM": zoom,
        "PULSE": "true" if pulse else "false",
        "PULSE_SPEED": pulse_speed,
        "FPS": fps,
    }


def show_helix(
    dna_sequence: str = "ACGT",
    *,
    length: int | None = None,
    colors: dict[str, int] | None = None,
    animate: bool = True,
    zoom: float = 1.0,
    pulse: bool = False,
    pulse_speed: float = 2.0,
    fps: float = 60.0,
) -> flet_webview.WebView:
    """Return a ``WebView`` displaying a DNA helix scene with controls.

    Parameters
    ----------
    dna_sequence:
        Base sequence used for rendering.
    length:
        Optional length of the rendered helix. The sequence is repeated as
        needed.
    colors:
        Mapping of nucleotide to hex color value or string.
    pulse:
        Enable pulsing animation of the helix segments.
    pulse_speed:
        Speed multiplier for the pulse animation.
    fps:
        Frames per second for rendering. Lower values reduce CPU usage.
    """
    three_url: str = THREE_JS_URL
    orbit_url: str = ORBIT_JS_URL
    if not three_url:
        logger.error("THREE_JS_URL missing; falling back to CDN")
        three_url = CDN_THREE_JS_URL
    if not orbit_url:
        logger.error("ORBIT_JS_URL missing; falling back to CDN")
        orbit_url = CDN_ORBIT_JS_URL

    helix_html: str = _make_helix_html(
        dna_sequence,
        length=length,
        colors=colors,
        animate=animate,
        zoom=zoom,
        pulse=pulse,
        pulse_speed=pulse_speed,
        fps=fps,
        three_js_url=three_url,
        orbit_js_url=orbit_url,
    )

    data_url: str = "data:text/html," + quote(helix_html)

    return flet_webview.WebView(url=data_url, width=600, height=400)


def show_helix_ui(
    dna_sequence: str = "ACGT",
    *,
    animate: bool = True,
    zoom: float = 1.0,
    colors: dict[str, int] | None = None,
    show_gc: bool = True,
    show_runs: bool = True,
    pulse: bool = False,
    pulse_speed: float = 2.0,
    fps: float = 60.0,
) -> flet_webview.WebView:
    """Return a ``WebView`` pointing at the React helix frontend.

    Parameters enable GC colouring, homopolymer highlighting and optional
    pulse animations via the corresponding query arguments. The ``fps``
    argument controls the maximum frames per second.
    """
    base_dir = Path(__file__).resolve().parent.parent / "web" / "helix-ui"
    helix_path = base_dir / "dist" / "index.html"
    if not helix_path.is_file():
        helix_path = base_dir / "index.html"

    params = [
        f"seq={quote(dna_sequence)}",
        f"animate={'true' if animate else 'false'}",
        f"zoom={zoom}",
        f"gc={'true' if show_gc else 'false'}",
        f"runs={'true' if show_runs else 'false'}",
        f"pulse={'true' if pulse else 'false'}",
        f"pulse_speed={pulse_speed}",
        f"fps={fps}",
    ]
    if colors:
        color_str = ",".join(f"{b}:#{v:06x}" for b, v in colors.items())
        params.append(f"colors={quote(color_str)}")

    query = "?" + "&".join(params)
    return flet_webview.WebView(url=helix_path.as_uri() + query, width=600, height=400)
