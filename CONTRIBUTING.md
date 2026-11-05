# Contributing

Use uv and Python 3.14.7. The lock pins separate compatibility lanes:
Core 2026.10.0 / pytest-homeassistant-custom-component 0.13.371 (minimum),
and Core 2026.11.0 / official pytest-homeassistant 2026.11.0 (latest tested).
The default environment selects minimum. Never install both harnesses together.

```sh
uv sync --locked
uv pip check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python -m pytest --cov=custom_components.sportclips --cov-branch --cov-report=term-missing --cov-fail-under=95
uv run --locked python scripts/package.py
```

To run the latest lane in a separate environment:

```sh
export UV_PROJECT_ENVIRONMENT="$PWD/.venv-latest"
uv sync --locked --no-default-groups --group dev --group latest
uv pip check
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync python -m pytest --cov=custom_components.sportclips --cov-branch --cov-report=term-missing --cov-fail-under=95
```

Use `--no-sync` after selecting this lane: a default `uv run` would restore minimum.
The test bootstrap maps legacy helper imports to the official harness only after
its bootstrap; no Home Assistant modules are replaced. Respx auto-loading is
disabled so the official harness can install Core's HTTPX alias first.

Tests use synthetic loopback HTTP responses and the real Home Assistant
flow/lifecycle/state harness. External connections are blocked. Write a failing
behavior test before changing code. Do not include real locations, configuration,
credentials or provider captures in tests or bug reports. Include Core/integration
versions, reproduction steps and sanitized errors when reporting a bug.

The package command builds a deterministic manual-install ZIP and SHA256 file in
`dist/`. Extract it at the HA configuration root; it includes
`custom_components/sportclips/`. HACS instead downloads repository source using
the standard integration layout, without `zip_release`.

## Release preparation

CI validates Python checks, packaging, Actionlint and hassfest. HACS validation is
skipped while the repository is private; it must pass **without ignores** before
public distribution. CI never publishes releases, including on tag pushes.

1. Keep `pyproject.toml` and the integration manifest version identical; update the
   lock with `uv lock` and rerun checks. Use a beta version for a prerelease.
2. Review the exact commit, packaged files, artwork notice and test results. Obtain
   explicit approval before creating a release, changing visibility or installing
   into a live Home Assistant instance. Private development is not that approval.
3. Once public distribution is approved, ensure the repository has a description,
   topics, issues and a recognized license. Run the HACS validator and hassfest on
   the exact release commit, with no skipped or ignored public checks.
4. Create an immutable version tag at that tested commit and a matching GitHub
   release, marking beta releases as prereleases. Verify the remote tag's commit
   and release version. A tag alone is not a HACS release; no attached ZIP is needed.
5. Verify HACS custom-repository installation separately. Default-catalog inclusion
   is a later [HACS submission](https://www.hacs.xyz/docs/publish/include/), not an
   automatic consequence of publishing a release.
