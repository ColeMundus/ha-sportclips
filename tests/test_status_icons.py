"""Store status remains an enum while its door icon follows provider state."""

from datetime import timedelta

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.sportclips.client import STATES
from tests.test_ha import setup_entry
from tests.test_metadata import STORE, envelope


async def test_open_store_uses_open_door(hass, http):
    await setup_entry(hass, http)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", "sportclips", "synthetic-store_status"
    )
    state = hass.states.get(entity_id)
    assert state.state == "open"
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["options"] == [
        "open",
        "lineup_opens_soon",
        "opens_soon",
        "closed_until_next_day",
        "closed",
        "offline",
    ]
    assert state.attributes["icon"] == "mdi:door-open"


@pytest.mark.parametrize(
    ("code", "expected_icon"),
    [
        (20, "mdi:door-closed"),
        (30, "mdi:door-closed"),
        (40, "mdi:door-closed"),
        (50, "mdi:door-closed"),
        (60, "mdi:door"),
        (999, "mdi:door"),
    ],
)
async def test_status_icon_tracks_provider_and_preserves_identity(
    hass, http, freezer, code, expected_icon
):
    entry = await setup_entry(hass, http)
    registry = er.async_get(hass)
    old_id = registry.async_get_entity_id(
        "sensor", "sportclips", "synthetic-store_status"
    )
    registry.async_update_entity(
        old_id, new_entity_id="sensor.my_store_status", name="My store status"
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=121))
    http.post(payload=envelope(dict(STORE, waitInfo={"storeState": code})))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.my_store_status")
    assert state.state == STATES.get(code, "unknown")
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["options"] == list(STATES.values())
    assert state.attributes["icon"] == expected_icon
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    record = registry.async_get("sensor.my_store_status")
    assert record.unique_id == "synthetic-store_status"
    assert record.name == "My store status"
    assert hass.states.get(old_id) is None
    assert hass.states.get("sensor.my_store_status").attributes["icon"] == expected_icon


async def test_unavailable_status_uses_neutral_door(hass, http, freezer):
    entry = await setup_entry(hass, http)
    freezer.tick(timedelta(seconds=121))
    http.post(status=503)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.sports_clips_example_salon_store_status")
    assert state.state == "unavailable"
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["options"] == list(STATES.values())
    assert state.attributes["icon"] == "mdi:door"
