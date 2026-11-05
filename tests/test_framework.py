"""Exercise compatibility lane version guards without replacing framework imports."""

from importlib.metadata import PackageNotFoundError

import pytest

from scripts.check_framework import check_framework

EXPECTED = {
    "homeassistant": "2026.11.0",
    "pytest-homeassistant": "2026.11.0",
    "aiohttp": "3.14.5",
    "probatio": "0.13.0",
}


def metadata(values):
    def get_version(package):
        if package not in values:
            raise PackageNotFoundError(package)
        return values[package]

    return get_version


def test_framework_versions():
    assert check_framework(EXPECTED, metadata(EXPECTED)) == EXPECTED


@pytest.mark.parametrize("package", ["homeassistant", "pytest-homeassistant"])
def test_framework_rejects_wrong_pin(package):
    with pytest.raises(AssertionError):
        check_framework(EXPECTED, metadata({**EXPECTED, package: "wrong"}))


def test_framework_rejects_overlapping_harnesses():
    with pytest.raises(AssertionError, match="second harness"):
        check_framework(
            EXPECTED,
            metadata({**EXPECTED, "pytest-homeassistant-custom-component": "0.13.371"}),
        )
