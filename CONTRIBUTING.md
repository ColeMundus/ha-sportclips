# Contributing

Use uv and Python 3.14.7. The lock pins Core 2026.10.0 and
pytest-homeassistant-custom-component 0.13.371 (aiohttp 3.14.4, probatio 0.13.0).

```sh
uv sync --locked
uv pip check
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python -m pytest --cov=custom_components.sportclips --cov-branch --cov-report=term-missing --cov-fail-under=95
uv run python scripts/package.py
```

Tests run real aiohttp against synthetic loopback responses and the actual Home
Assistant flow/lifecycle/state harness. External connects remain blocked. No account,
live location, service credential or Home Assistant installation is required by CI.
Write a failing behavior test at the HTTP or HA public boundary before implementation;
run red, implement the smallest slice, then run green. Do not replace HA with stubs.
Keep captures and research outside the product tree. Do not run live service tests
in routine CI or add real salon/location fixtures.

The package command builds a deterministic manual-install ZIP under `dist/`, with a
SHA256 file. It contains `custom_components/sportclips/...` for extraction at the HA
configuration root. This is not a HACS release asset. CI validates with hassfest;
HACS is deliberately skipped while the repository is private. Publication, release
creation, visibility changes and live HA installation require separate authorization.
