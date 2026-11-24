import pytest

from scripts.check_ci import accepted


@pytest.mark.parametrize(
    ("private", "results", "expected"),
    [
        (
            True,
            {
                "actionlint": "success",
                "checks": "success",
                "hassfest": "success",
                "hacs": "skipped",
            },
            True,
        ),
        (
            False,
            {
                "actionlint": "success",
                "checks": "success",
                "hassfest": "success",
                "hacs": "skipped",
            },
            False,
        ),
        (
            False,
            {
                "actionlint": "success",
                "checks": "success",
                "hassfest": "success",
                "hacs": "success",
            },
            True,
        ),
        (
            True,
            {
                "actionlint": "success",
                "checks": "skipped",
                "hassfest": "success",
                "hacs": "skipped",
            },
            False,
        ),
        (
            True,
            {
                "actionlint": "success",
                "checks": "failure",
                "hassfest": "success",
                "hacs": "skipped",
            },
            False,
        ),
        (
            True,
            {
                "actionlint": "success",
                "checks": "success",
                "hassfest": "cancelled",
                "hacs": "skipped",
            },
            False,
        ),
        (True, {}, False),
        (False, {"checks": "success", "hassfest": "success", "hacs": "success"}, False),
        (
            False,
            {
                "actionlint": "failure",
                "checks": "success",
                "hassfest": "success",
                "hacs": "success",
            },
            False,
        ),
        (
            False,
            {
                "actionlint": "skipped",
                "checks": "success",
                "hassfest": "success",
                "hacs": "success",
            },
            False,
        ),
        (
            False,
            {
                "actionlint": "cancelled",
                "checks": "success",
                "hassfest": "success",
                "hacs": "success",
            },
            False,
        ),
    ],
)
def test_required_gate(private, results, expected):
    assert accepted(private, results) is expected
