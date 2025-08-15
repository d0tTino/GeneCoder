import base64
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path
from importlib import invalidate_caches
from importlib.metadata import EntryPoint

import pytest

import genecoder.plugin_manager as plugins
from genecoder.core import run_pipeline


def _build_wheel(
    src_pkg: Path,
    dist_name: str,
    module_name: str,
    group: str,
    ep_name: str,
    wheel_dir: Path,
) -> Path:
    version = "0.1.0"
    filename = f"{dist_name.replace('-', '_')}-{version}-py3-none-any.whl"
    wheel_path = wheel_dir / filename
    dist_info = f"{dist_name.replace('-', '_')}-{version}.dist-info"
    records: list[tuple[str, str, int]] = []
    wheel_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path, "w") as zf:
        for file in src_pkg.rglob("*"):
            if file.is_file():
                arc = f"{module_name}/{file.relative_to(src_pkg)}"
                zf.write(file, arc)
                data = file.read_bytes()
                digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
                records.append((arc, digest, len(data)))
        metadata = f"Metadata-Version: 2.1\nName: {dist_name}\nVersion: {version}\n"
        zf.writestr(f"{dist_info}/METADATA", metadata)
        digest = base64.urlsafe_b64encode(hashlib.sha256(metadata.encode()).digest()).decode().rstrip("=")
        records.append((f"{dist_info}/METADATA", digest, len(metadata)))
        wheel_txt = "Wheel-Version: 1.0\nGenerator: genecoder-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        zf.writestr(f"{dist_info}/WHEEL", wheel_txt)
        digest = base64.urlsafe_b64encode(hashlib.sha256(wheel_txt.encode()).digest()).decode().rstrip("=")
        records.append((f"{dist_info}/WHEEL", digest, len(wheel_txt)))
        ep_txt = f"[{group}]\n{ep_name} = {module_name}\n"
        zf.writestr(f"{dist_info}/entry_points.txt", ep_txt)
        digest = base64.urlsafe_b64encode(hashlib.sha256(ep_txt.encode()).digest()).decode().rstrip("=")
        records.append((f"{dist_info}/entry_points.txt", digest, len(ep_txt)))
        record_lines = [f"{p},sha256={d},{s}" for p, d, s in records]
        record_lines.append(f"{dist_info}/RECORD,,")
        zf.writestr(f"{dist_info}/RECORD", "\n".join(record_lines) + "\n")
    return wheel_path


def _install_example_plugins(target: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "plugins-examples"
    specs = [
        ("example_codec", "genecoder-example-codec", "example_codec", "genecoder.plugins"),
        ("example_fec", "genecoder-example-fec", "example_fec", "genecoder.fec"),
        ("example_simulator", "genecoder-example-simulator", "example_simulator", "genecoder.simulators"),
    ]
    for pkg_dir, dist_name, module_name, group in specs:
        wheel = _build_wheel(
            root / pkg_dir / module_name,
            dist_name,
            module_name,
            group,
            "example",
            target,
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "-q",
                str(wheel),
                "--target",
                str(target),
            ]
        )


def test_plugin_pipeline_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site = tmp_path / "site"
    _install_example_plugins(site)
    monkeypatch.syspath_prepend(str(site))
    invalidate_caches()
    plugins._initialized = False
    input_path = tmp_path / "in.bin"
    data = b"hello world"
    input_path.write_bytes(data)
    output_path = tmp_path / "out.bin"
    decoded, metrics = run_pipeline(
        "example", "example", "example", str(input_path), str(output_path)
    )
    assert decoded == data
    assert output_path.read_bytes() == data
    assert metrics["decode_success_rate"] == 1.0


def test_plugin_pipeline_missing(tmp_path: Path) -> None:
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    plugins._initialized = False
    input_path = tmp_path / "in.bin"
    input_path.write_bytes(b"data")
    with pytest.raises(ValueError, match="Unknown codec"):
        run_pipeline("missing", None, None, str(input_path), str(tmp_path / "out.bin"))


def test_malformed_plugin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad_plugin.py"
    bad.write_text(
        "def register(register_codec):\n    register_codec('bad', object())\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    ep = EntryPoint(name="bad", value="bad_plugin", group="genecoder.plugins")
    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda *, group=None: [ep] if group == "genecoder.plugins" else [],
    )
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()
    with pytest.raises(TypeError):
        plugins.load_plugins()
