"""Fail-closed aggregate gate with an explicit private HACS skip."""

import json
import os


def accepted(private: bool, results: dict[str, str]) -> bool:
    """Every required job must succeed; only private HACS may skip."""
    return (
        results.get("checks") == "success"
        and results.get("hassfest") == "success"
        and results.get("hacs") == ("skipped" if private else "success")
    )


if __name__ == "__main__":
    jobs = json.loads(os.environ["NEEDS"])
    results = {key: value["result"] for key, value in jobs.items()}
    raise SystemExit(0 if accepted(os.environ["PRIVATE"] == "true", results) else 1)
