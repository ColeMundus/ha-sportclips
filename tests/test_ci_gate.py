import pytest

from scripts.check_ci import accepted


@pytest.mark.parametrize(
    ("private", "results", "expected"),
    [
        (True, {"checks": "success", "hassfest": "success", "hacs": "skipped"}, True),
        (False, {"checks": "success", "hassfest": "success", "hacs": "skipped"}, False),
        (False, {"checks": "success", "hassfest": "success", "hacs": "success"}, True),
        (True, {"checks": "skipped", "hassfest": "success", "hacs": "skipped"}, False),
        (True, {"checks": "failure", "hassfest": "success", "hacs": "skipped"}, False),
        (
            True,
            {"checks": "success", "hassfest": "cancelled", "hacs": "skipped"},
            False,
        ),
        (True, {}, False),
    ],
)
def test_required_gate(private, results, expected):
    assert accepted(private, results) is expected
