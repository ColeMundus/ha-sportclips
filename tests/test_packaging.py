import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.package import build

ROOT = Path(__file__).resolve().parents[1]


def test_manual_package_is_deterministic_self_contained_and_importable(
    tmp_path, monkeypatch
):
    archive = build(ROOT, tmp_path / "a")
    second = build(ROOT, tmp_path / "b")
    assert archive.read_bytes() == second.read_bytes()
    assert (
        archive.with_suffix(".zip.sha256").read_text().split()[0]
        == hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert names == sorted(set(names))
        assert "custom_components/sportclips/LICENSE" in names
        assert "custom_components/sportclips/translations/en.json" in names
        assert "custom_components/sportclips/brand/icon.png" in names
        assert not any("tests" in name or "__pycache__" in name for name in names)
        package.extractall(tmp_path / "extract")
    # Import runtime solely from the extracted component in a clean subprocess.
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import custom_components.sportclips.config_flow; "
            "import custom_components.sportclips.sensor; "
            "import custom_components.sportclips.binary_sensor",
        ],
        cwd=tmp_path / "extract",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_package_rejects_component_license_drift(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(
        ROOT / "custom_components",
        source / "custom_components",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(ROOT / "pyproject.toml", source)
    shutil.copy(ROOT / "LICENSE", source)
    (source / "custom_components/sportclips/LICENSE").write_text("Incorrect license")

    with pytest.raises(ValueError, match="license differs"):
        build(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "damage", ["missing", "version", "symlink", "unexpected", "translation"]
)
def test_invalid_package_source_rejected(tmp_path, damage):
    source = tmp_path / "source"
    shutil.copytree(
        ROOT / "custom_components",
        source / "custom_components",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(ROOT / "pyproject.toml", source)
    shutil.copy(ROOT / "LICENSE", source)
    component = source / "custom_components/sportclips"
    if damage == "missing":
        (component / "client.py").unlink()
    elif damage == "version":
        manifest = json.loads((component / "manifest.json").read_text())
        manifest["version"] = "9.0.0"
        (component / "manifest.json").write_text(json.dumps(manifest))
    elif damage == "symlink":
        (component / "client.py").unlink()
        (component / "client.py").symlink_to(
            ROOT / "custom_components/sportclips/client.py"
        )
    elif damage == "unexpected":
        (component / "capture.json").write_text("{}")
    else:
        (component / "translations/en.json").write_text("{}")
    with pytest.raises(ValueError):
        build(source, tmp_path / "out")
