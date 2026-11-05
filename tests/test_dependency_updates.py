"""Keep the exact Core/harness pair together in proposed updates."""

from pathlib import Path

import yaml


def test_dependabot_groups_framework_pair():
    config = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/dependabot.yml").read_text()
    )
    update = next(
        item for item in config["updates"] if item["package-ecosystem"] == "uv"
    )
    assert set(
        update.get("groups", {}).get("home-assistant", {}).get("patterns", [])
    ) == {
        "homeassistant",
        "pytest-homeassistant-custom-component",
        "pytest-homeassistant",
    }
