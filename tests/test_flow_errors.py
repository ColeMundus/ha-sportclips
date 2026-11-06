from dataclasses import asdict

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.test_metadata import STORE, envelope
from tests.test_validation import SALON

SEARCH = {
    "response": {
        "searchedLocations": [
            {"placeName": "Example", "latitude": 35, "longitude": -90}
        ]
    }
}


async def begin(hass):
    return await hass.config_entries.flow.async_init(
        "sportclips", context={"source": "user"}
    )


async def configure(hass, result, data):
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_oversized_search_rejected_without_http(hass, http):
    result = await configure(hass, await begin(hass), {"search": "x" * 129})
    assert result["errors"] == {"base": "invalid_search"}
    assert len(http.requests) == 0
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize(
    "payload,error",
    [({}, "cannot_connect"), ({"response": {"searchedLocations": []}}, "no_locations")],
)
async def test_search_error_then_recovery_and_cancel(hass, http, payload, error):
    http.get(payload=payload)
    result = await configure(hass, await begin(hass), {"search": "Example"})
    assert result["errors"] == {"base": error}
    http.get(payload=SEARCH)
    result = await configure(hass, result, {"search": "Example"})
    assert result["step_id"] == "location"
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert hass.config_entries.async_entries("sportclips") == []


async def test_empty_salon_and_error_recovery(hass, http):
    http.get(payload=SEARCH)
    result = await configure(hass, await begin(hass), {"search": "Example"})
    http.post(payload=envelope())
    result = await configure(hass, result, {"location": "0"})
    assert result["errors"] == {"base": "no_salons"}
    http.post(payload={})
    result = await configure(hass, result, {"location": "0"})
    assert result["errors"] == {"base": "cannot_connect"}
    http.post(payload=envelope(STORE))
    result = await configure(hass, result, {"location": "0"})
    assert result["step_id"] == "salon"
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_duplicate_stable_salon(hass, http):
    entry = MockConfigEntry(domain="sportclips", unique_id=SALON.id, data=asdict(SALON))
    entry.add_to_hass(hass)
    http.get(payload=SEARCH)
    http.post(payload=envelope(STORE))
    result = await configure(hass, await begin(hass), {"search": "Example"})
    result = await configure(hass, result, {"location": "0"})
    result = await configure(hass, result, {"salon": SALON.id})
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries("sportclips")) == 1


async def test_rate_limit_survives_flow_reopen(hass, http):
    http.get(status=429, headers={"Retry-After": "300"})
    result = await configure(hass, await begin(hass), {"search": "Example"})
    assert result["errors"] == {"base": "cannot_connect"}
    hass.config_entries.flow.async_abort(result["flow_id"])
    result = await configure(hass, await begin(hass), {"search": "Elsewhere"})
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(http.requests) == 1
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_concurrent_duplicate_flow_creates_one_entry(hass, http):
    import asyncio

    flows = []
    for _ in range(2):
        http.get(payload=SEARCH)
        http.post(payload=envelope(STORE))
        result = await configure(hass, await begin(hass), {"search": "Example"})
        flows.append(await configure(hass, result, {"location": "0"}))
    http.post(payload=envelope(STORE))
    results = await asyncio.gather(
        *(configure(hass, result, {"salon": SALON.id}) for result in flows)
    )
    assert sorted(result["type"] for result in results) == ["abort", "create_entry"]
    assert len(hass.config_entries.async_entries("sportclips")) == 1
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = hass.config_entries.async_entries("sportclips")[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
