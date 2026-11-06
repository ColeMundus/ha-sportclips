"""Native setup can discover salons near Home Assistant without a text search."""

import pytest

from tests.test_flow_errors import begin, configure
from tests.test_metadata import STORE, envelope


@pytest.mark.parametrize("data", [{}, {"search": ""}, {"search": "   "}])
async def test_blank_search_uses_home_coordinates(hass, http, data):
    hass.config.latitude = 35.25
    hass.config.longitude = -90.5
    result = await begin(hass)
    assert not http.requests  # Opening setup does not send home coordinates.
    http.post(payload=envelope(STORE))
    result = await configure(hass, result, data)
    assert result["step_id"] == "salon"
    assert len(http.requests) == 1
    method, path, _, body = http.requests[0]
    assert method == "POST" and path.endswith("/metadata")
    assert body["data"]["mapArea"]["centerLat"] == 35.25
    assert body["data"]["mapArea"]["centerLon"] == -90.5
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize(
    "payload,error",
    [({}, "cannot_connect"), (envelope(), "no_salons")],
)
async def test_home_discovery_error_allows_manual_search(hass, http, payload, error):
    from tests.test_flow_errors import SEARCH

    http.post(payload=payload)
    result = await configure(hass, await begin(hass), {})
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    http.get(payload=SEARCH)
    result = await configure(hass, result, {"search": "Elsewhere"})
    assert result["step_id"] == "location"
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_invalid_home_coordinates_do_not_send_http(hass, http):
    hass.config.latitude = float("nan")
    result = await configure(hass, await begin(hass), {})
    assert result["errors"] == {"base": "invalid_home_location"}
    assert not http.requests
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_home_discovery_honors_cooldown_after_reopen(hass, http):
    http.post(status=429, headers={"Retry-After": "300"})
    for _ in range(2):
        result = await configure(hass, await begin(hass), {})
        assert result["errors"] == {"base": "cannot_connect"}
        hass.config_entries.flow.async_abort(result["flow_id"])
    assert len(http.requests) == 1


async def test_zero_coordinates_are_valid(hass, http):
    hass.config.latitude = 0
    hass.config.longitude = 0
    http.post(payload=envelope(STORE))
    result = await configure(hass, await begin(hass), {})
    assert result["step_id"] == "salon"
    hass.config_entries.flow.async_abort(result["flow_id"])
