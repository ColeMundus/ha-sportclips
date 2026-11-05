"""Build a deterministic manual-install archive, never publish it."""

import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

FILES = (
    "LICENSE",
    "__init__.py",
    "brand/NOTICE.md",
    "brand/icon.png",
    "client.py",
    "config_flow.py",
    "const.py",
    "coordinator.py",
    "manifest.json",
    "models.py",
    "sensor.py",
    "strings.json",
    "translations/en.json",
)
PREFIX = "custom_components/sportclips"


def build(root: Path, output: Path) -> Path:
    """Fail closed on missing, unreviewed or symlinked runtime files."""
    component = root / PREFIX
    actual = set()
    for path in component.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks are not allowed")
        relative = path.relative_to(component)
        if "__pycache__" in relative.parts:
            continue
        if path.is_file():
            actual.add(relative.as_posix())
    if actual != set(FILES):
        raise ValueError("runtime allowlist differs")
    if any(parent.is_symlink() for parent in (component, component.parent)):
        raise ValueError("symlinked component root")
    manifest = json.loads((component / "manifest.json").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    if manifest["domain"] != "sportclips" or manifest["version"] != project["version"]:
        raise ValueError("domain/version mismatch")
    strings = json.loads((component / "strings.json").read_text())
    if json.loads((component / "translations/en.json").read_text()) != strings:
        raise ValueError("English translation differs")
    from PIL import Image

    with Image.open(component / "brand/icon.png") as icon:
        if icon.format != "PNG" or icon.size != (256, 256):
            raise ValueError("invalid icon")
        icon.verify()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"sportclips-{manifest['version']}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for relative in sorted(FILES):
            name = f"{PREFIX}/{relative}"
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, (component / relative).read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parents[1], Path("dist")))
