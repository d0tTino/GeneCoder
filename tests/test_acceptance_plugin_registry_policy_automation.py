from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from genecoder.plugin_runtime.descriptors import PluginLifecycleState
from genecoder.plugin_supply_chain import service as supply_chain

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "data" / "acceptance"
ACCEPTANCE_ARTIFACT_PATH = ROOT / "artifacts" / "acceptance" / "plugin-registry-policy-runtime.json"


class RecordingInstaller:
    def __init__(self) -> None:
        self.installed_targets: list[str] = []

    def install(self, target: str) -> None:
        self.installed_targets.append(target)


def _emit_acceptance_artifact(payload: dict) -> None:
    ACCEPTANCE_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_ARTIFACT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_signed_and_unsigned_registry_policy_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package_path = tmp_path / "fixture-plugin.whl"
    package_path.write_bytes(b"fixture-wheel-payload")

    unsigned_registry = yaml.safe_load((FIXTURE_DIR / "plugin_registry_unsigned.yaml").read_text(encoding="utf-8"))
    unsigned_registry["packages"][0]["spec"] = package_path.as_uri()

    signed_registry = yaml.safe_load((FIXTURE_DIR / "plugin_registry_signed.yaml").read_text(encoding="utf-8"))
    signed_registry["packages"][0]["spec"] = package_path.as_uri()

    unsigned_registry_path = tmp_path / "unsigned-registry.yaml"
    signed_registry_path = tmp_path / "signed-registry.yaml"
    unsigned_registry_path.write_text(yaml.safe_dump(unsigned_registry), encoding="utf-8")
    signed_registry_path.write_text(yaml.safe_dump(signed_registry), encoding="utf-8")

    with pytest.raises(ValueError, match="Signed metadata and checksum are required"):
        supply_chain.install_registry_plugins(
            unsigned_registry_path,
            offline=False,
            allow_network=False,
            yaml_module=yaml,
            installer=RecordingInstaller(),
        )

    monkeypatch.setattr(supply_chain, "_verify_payload", lambda *_args, **_kwargs: None)
    installer = RecordingInstaller()
    descriptors = supply_chain.install_registry_plugins(
        signed_registry_path,
        offline=False,
        allow_network=False,
        yaml_module=yaml,
        installer=installer,
    )

    assert len(descriptors) == 1
    assert descriptors[0].state == PluginLifecycleState.LOADED
    assert descriptors[0].signature is not None
    assert installer.installed_targets

    policy_registry = yaml.safe_load((FIXTURE_DIR / "plugin_registry_policy_reject.yaml").read_text(encoding="utf-8"))
    policy_registry["packages"][0]["spec"] = package_path.as_uri()
    policy_registry_path = tmp_path / "policy-registry.yaml"
    policy_registry_path.write_text(yaml.safe_dump(policy_registry), encoding="utf-8")

    with pytest.raises(ValueError, match="Disallowed license"):
        supply_chain.install_registry_plugins(
            policy_registry_path,
            offline=False,
            allow_network=False,
            yaml_module=yaml,
            installer=RecordingInstaller(),
        )

    missing_provenance = {
        "packages": [
            {
                "spec": package_path.as_uri(),
                "package": "fixture-plugin",
                "version": "1.0.0",
                "license": "MIT",
                "checksum": "deadbeef",
                "signature": "ZHVtbXk=",
                "provenance_channel": "stable",
            }
        ]
    }
    missing_provenance_path = tmp_path / "missing-provenance.yaml"
    missing_provenance_path.write_text(yaml.safe_dump(missing_provenance), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing provenance_publisher"):
        supply_chain.install_registry_plugins(
            missing_provenance_path,
            offline=False,
            allow_network=False,
            yaml_module=yaml,
            installer=RecordingInstaller(),
        )

    _emit_acceptance_artifact(
        {
            "suite": "plugin_registry_policy_automation",
            "passed": True,
            "evidence": {
                "unsigned_entries_hard_fail": True,
                "signed_entries_install_and_load": True,
                "policy_rejection_reason_disallowed_license": True,
                "policy_rejection_reason_missing_provenance": True,
            },
            "installed_specs": [d.source for d in descriptors],
            "lifecycle_states": [d.state.value for d in descriptors],
        }
    )
