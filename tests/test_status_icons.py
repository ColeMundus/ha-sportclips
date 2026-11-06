"""Native Opening boolean, detailed provider status and shared wait snapshot."""

from datetime import timedelta

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.sportclips.client import STATES
from tests.test_ha import setup_entry
from tests.test_metadata import STORE, envelope


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (10, "on"),
        (20, "off"),
        (30, "off"),
        (40, "off"),
        (50, "off"),
        (60, "unknown"),
        (999, "unknown"),
    ],
)
async def test_native_opening_status(hass, http, code, expected):
    await setup_entry(hass, http, dict(STORE, waitInfo={"storeState": code}))
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "binary_sensor", "sportclips", "synthetic-store_status"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.state == expected
    assert state.attributes["device_class"] == "opening"
    assert "options" not in state.attributes
    assert state.attributes["provider_status"] == STATES.get(code)
    assert state.attributes["icon"] == (
        "mdi:door-open"
        if expected == "on"
        else "mdi:door-closed"
        if expected == "off"
        else "mdi:door"
    )
    assert (
        registry.async_get_entity_id("sensor", "sportclips", "synthetic-store_status")
        is None
    )
    assert hass.states.get(
        "sensor.sports_clips_example_salon_estimated_wait"
    ).state == ("0" if code == 10 else "unknown")
    assert len(http.requests) == 1


async def test_unavailable_and_recovery(hass, http, freezer):
    entry = await setup_entry(hass, http)
    freezer.tick(timedelta(seconds=121))
    http.post(status=503)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("binary_sensor.sports_clips_example_salon_store_status")
    assert state.state == "unavailable"
    assert state.attributes["device_class"] == "opening"
    assert state.attributes["icon"] == "mdi:door"
    assert (
        hass.states.get("sensor.sports_clips_example_salon_estimated_wait").state
        == "unavailable"
    )
    freezer.tick(timedelta(seconds=121))
    http.post(payload=envelope(dict(STORE, waitInfo={"storeState": 40})))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(state.entity_id).state == "off"
    assert hass.states.get(state.entity_id).attributes["icon"] == "mdi:door-closed"
    assert len(http.requests) == 3
