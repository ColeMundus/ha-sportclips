"""Reject a mismatched or overlapping Home Assistant test environment."""

import os
import sys
from importlib.metadata import PackageNotFoundError, version


def check_framework(expected, get_version=version):
    """Check exact pins and ensure only the selected harness is installed."""
    actual = {package: get_version(package) for package in expected}
    assert actual == expected, (actual, expected)
    harnesses = {"pytest-homeassistant", "pytest-homeassistant-custom-component"}
    for other in harnesses - expected.keys():
        try:
            get_version(other)
        except PackageNotFoundError:
            continue
        raise AssertionError(f"Unexpected second harness: {other}")
    return actual


if __name__ == "__main__":
    assert sys.version_info[:3] == (3, 14, 7)
    print(
        check_framework(
            {
                "homeassistant": os.environ["CORE"],
                os.environ["HARNESS"]: os.environ["HARNESS_VERSION"],
                "aiohttp": os.environ["AIOHTTP"],
                "probatio": "0.13.0",
            }
        )
    )
