import json
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
)

from tests.test_metadata import STORE, envelope
from tests.test_validation import SALON


async def test_flow_setup_states_unload(hass, http):
    http.get(
        payload={
            "response": {
                "searchedLocations": [
                    {"placeName": "Example, State", "latitude": 35, "longitude": -90}
                ]
            }
        }
    )
    http.post(payload=envelope(STORE))
    http.post(payload=envelope(STORE))
    result = await hass.config_entries.flow.async_init(
        "sportclips", context={"source": "user"}
    )
    assert result["step_id"] == "user"
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert [field["name"] for field in fields] == ["search"]
    json.dumps(fields)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search": "Example"}
    )
    assert result["step_id"] == "location"
    json.dumps(
        probatio.to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"location": "0"}
    )
    assert result["step_id"] == "salon"
    json.dumps(
        probatio.to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"salon": "synthetic-store"}
    )
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.unique_id == "synthetic-store"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    wait_id = registry.async_get_entity_id(
        "sensor", "sportclips", "synthetic-store_wait"
    )
    status_id = registry.async_get_entity_id(
        "binary_sensor", "sportclips", "synthetic-store_status"
    )
    assert hass.states.get(wait_id).state == "0"
    assert hass.states.get(wait_id).attributes["unit_of_measurement"] == "min"
    assert "state_class" not in hass.states.get(wait_id).attributes
    assert hass.states.get(status_id).state == "on"
    assert len(http.requests) == 3
    session = entry.runtime_data.client.session
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not session.closed


async def setup_entry(hass, http, store=STORE, options=None):
    http.post(payload=envelope(store))
    entry = MockConfigEntry(
        domain="sportclips",
        title="Example Salon",
        unique_id=store["uid"],
        data=dict(asdict(SALON), id=store["uid"]),
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_pacing_failure_reload_and_recovery(hass, http, freezer):
    entry = await setup_entry(hass, http)
    first = entry.runtime_data
    await first.async_refresh()
    assert len(http.requests) == 1  # manual refresh cannot accelerate polling
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert len(http.requests) == 1  # reload cannot bypass polling floor
    coordinator = entry.runtime_data
    freezer.tick(timedelta(seconds=121))
    http.post(status=429, headers={"Retry-After": "600"})
    await coordinator.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    await coordinator.async_refresh()
    assert await hass.config_entries.async_reload(entry.entry_id) is False
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert len(http.requests) == 2
    freezer.tick(timedelta(seconds=601))
    http.post(payload=envelope(dict(STORE, displayDetails={"waitTimeAsNumber": 12})))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert sorted(s.state for s in hass.states.async_all("sensor")) == ["12"]
    assert hass.states.async_all("binary_sensor")[0].state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_scheduled_shared_poll_and_shutdown(hass, http, freezer):
    freezer.move_to("2026-11-05T12:00:00.900000+00:00")
    start = dt_util.utcnow()
    with patch("homeassistant.helpers.update_coordinator.randint", return_value=50_000):
        entry = await setup_entry(hass, http)
    http.post(
        payload=envelope(dict(STORE, waitInfo={"storeState": 40}, displayDetails={}))
    )
    freezer.move_to(start.replace(microsecond=50_000) + timedelta(seconds=120))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 1
    freezer.move_to(start + timedelta(seconds=120))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2
    assert sorted(s.state for s in hass.states.async_all("sensor")) == ["unknown"]
    assert hass.states.async_all("binary_sensor")[0].state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(start + timedelta(seconds=240))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2


async def test_failed_first_refresh_and_unload_failure(hass, http):
    http.post(status=503)
    entry = MockConfigEntry(domain="sportclips", unique_id=SALON.id, data=asdict(SALON))
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_registry_identity_preserved_on_reload(hass, http):
    entry = await setup_entry(hass, http)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", "sportclips", "synthetic-store_wait"
    )
    registry.async_update_entity(entity_id, name="My wait")
    with patch.object(
        hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=False)
    ):
        from custom_components.sportclips import async_unload_entry

        assert not await async_unload_entry(hass, entry)
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert registry.async_get(entity_id).name == "My wait"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("minutes", [None, 7])
async def test_inflight_retirement_cannot_publish_to_replacement(
    hass, http, freezer, minutes
):
    import asyncio

    options = {} if minutes is None else {"polling_interval": minutes}
    entry = await setup_entry(hass, http, options=options)
    old = entry.runtime_data
    seconds = (minutes or 2) * 60
    freezer.tick(timedelta(seconds=seconds + 1))
    started, release = asyncio.Event(), asyncio.Event()

    async def blocked():
        started.set()
        await release.wait()
        return envelope(dict(STORE, displayDetails={"waitTimeAsNumber": 999}))

    http.post(payload=blocked)
    refresh = asyncio.create_task(old.async_refresh())
    await started.wait()
    queued = asyncio.create_task(old.async_refresh())
    await asyncio.sleep(0)
    assert await hass.config_entries.async_unload(entry.entry_id)
    http.post(payload=envelope(dict(STORE, displayDetails={"waitTimeAsNumber": 7})))
    replacement = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    release.set()
    await asyncio.gather(refresh, queued)
    assert not await replacement
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert len(http.requests) == 2  # retired queued read and replacement must not poll
    assert old.data.wait_minutes == 0  # blocked response was not published
    freezer.tick(timedelta(seconds=seconds - 1))
    assert not await hass.config_entries.async_reload(entry.entry_id)
    assert len(http.requests) == 2
    freezer.tick(timedelta(seconds=2))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 3
    assert entry.runtime_data is not old
    assert sorted(s.state for s in hass.states.async_all("sensor")) == ["7"]
    assert hass.states.async_all("binary_sensor")[0].state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_multiple_entries_and_concurrent_refreshes(hass, http, freezer):
    import asyncio

    first = await setup_entry(hass, http)
    second_store = dict(
        STORE,
        uid="other",
        storeUid="other",
        storeName="Other Salon",
        displayDetails={"waitTimeAsNumber": 23},
    )
    second = await setup_entry(hass, http, second_store)
    assert len(hass.states.async_all("sensor")) == 2
    assert len(hass.states.async_all("binary_sensor")) == 2
    assert second.runtime_data.data.wait_minutes == 23
    assert first.runtime_data.data.wait_minutes == 0
    freezer.tick(timedelta(seconds=121))
    http.post(payload=envelope(dict(STORE, displayDetails={"waitTimeAsNumber": 5})))
    await asyncio.gather(
        first.runtime_data.async_refresh(), first.runtime_data.async_refresh()
    )
    assert len(http.requests) == 3
    assert second.runtime_data.data.wait_minutes == 23
    assert await hass.config_entries.async_unload(first.entry_id)
    assert await hass.config_entries.async_unload(second.entry_id)


async def test_sensitive_transport_context_not_in_debug_logs(
    hass, http, freezer, caplog
):
    import logging

    entry = await setup_entry(hass, http)
    freezer.tick(timedelta(seconds=121))
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="custom_components.sportclips")
    with patch.object(
        entry.runtime_data.client.session,
        "request",
        side_effect=TimeoutError("PRIVATE_CANARY"),
    ):
        await entry.runtime_data.async_refresh()
    assert "PRIVATE_CANARY" not in caplog.text
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_extreme_retry_after_is_unavailable_and_survives_reload(
    hass, http, freezer
):
    entry = await setup_entry(hass, http)
    freezer.tick(timedelta(seconds=121))
    http.post(status=429, headers={"Retry-After": "999999999999999999999999999"})
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    assert not await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert len(http.requests) == 2


async def test_retired_entry_waiting_for_host_gate_does_not_send_http(
    hass, http, freezer
):
    import asyncio

    first = await setup_entry(hass, http)
    second = await setup_entry(hass, http, dict(STORE, uid="other", storeUid="other"))
    freezer.tick(timedelta(seconds=121))
    started, release = asyncio.Event(), asyncio.Event()

    async def blocked():
        started.set()
        await release.wait()
        return envelope(STORE)

    http.post(payload=blocked)
    reading = asyncio.create_task(first.runtime_data.async_refresh())
    await started.wait()
    queued = asyncio.create_task(second.runtime_data.async_refresh())
    await asyncio.sleep(0)
    assert second.runtime_data.poll.lock.locked()
    assert await hass.config_entries.async_unload(second.entry_id)
    release.set()
    await asyncio.gather(reading, queued)
    assert len(http.requests) == 3
    assert await hass.config_entries.async_unload(first.entry_id)
