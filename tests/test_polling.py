"""Polling configuration through real HA forms, lifecycle and HTTP."""

import json
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import patch

import probatio
import pytest
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from tests.test_flow_errors import SEARCH, begin, configure
from tests.test_ha import setup_entry
from tests.test_metadata import STORE, envelope
from tests.test_validation import SALON


@pytest.mark.parametrize("minutes", [0, 61, 1.5, "3", True])
async def test_setup_rejects_invalid_interval(hass, http, minutes):
    http.get(payload=SEARCH)
    http.post(payload=envelope(STORE))
    result = await configure(hass, await begin(hass), {"search": "Example"})
    result = await configure(hass, result, {"location": "0"})
    with pytest.raises(probatio.Invalid):
        result["data_schema"]({"salon": SALON.id, "polling_interval": minutes})
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_early_timer_rearms_for_poll_floor(hass, http, freezer):
    """Core's rounded timer must not turn a one-minute poll into two minutes."""
    freezer.move_to("2026-11-05T12:00:00.900000+00:00")
    start = dt_util.utcnow()
    with patch("homeassistant.helpers.update_coordinator.randint", return_value=50_000):
        entry = await setup_entry(hass, http, options={"polling_interval": 1})
    coordinator = entry.runtime_data
    early = start.replace(microsecond=50_000) + timedelta(seconds=60)
    assert (early - start).total_seconds() == 59.15
    assert (
        coordinator._unsub_refresh.__self__.when() - hass.loop.time()
        == pytest.approx(59.15)
    )
    http.post(payload=envelope(dict(STORE, displayDetails={"waitTimeAsNumber": 9})))
    freezer.move_to(early)
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 1
    assert coordinator.last_update_success
    # There must be no read even one microsecond before the strict floor.
    freezer.move_to(start + timedelta(seconds=60, microseconds=-1))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 1
    freezer.move_to(start + timedelta(seconds=60))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2
    assert sorted(s.state for s in hass.states.async_all("sensor")) == ["9"]
    assert hass.states.async_all("binary_sensor")[0].state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_rearmed_timer_cancels_on_unload(hass, http, freezer):
    freezer.move_to("2026-11-05T12:00:00.900000+00:00")
    start = dt_util.utcnow()
    with patch("homeassistant.helpers.update_coordinator.randint", return_value=50_000):
        entry = await setup_entry(hass, http, options={"polling_interval": 1})
    coordinator = entry.runtime_data
    freezer.move_to(start.replace(microsecond=50_000) + timedelta(seconds=60))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator._unsub_refresh is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._unsub_refresh is None
    # A callback already queued at retirement must not rearm either.
    await coordinator._handle_refresh_interval()
    assert coordinator._unsub_refresh is None
    freezer.move_to(start + timedelta(seconds=60))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 1


async def test_scheduled_retry_after_rearms_at_exact_cooldown(hass, http, freezer):
    freezer.move_to("2026-11-05T12:00:00.900000+00:00")
    start = dt_util.utcnow()
    with patch("homeassistant.helpers.update_coordinator.randint", return_value=50_000):
        entry = await setup_entry(hass, http, options={"polling_interval": 1})
    http.post(status=429, headers={"Retry-After": "900"})
    freezer.move_to(start + timedelta(seconds=60))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2
    assert not entry.runtime_data.last_update_success
    # The next ordinary timer must rearm once for the full remaining cooldown.
    freezer.move_to(start.replace(microsecond=50_000) + timedelta(seconds=120))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2
    deadline = start + timedelta(seconds=960)
    freezer.move_to(deadline - timedelta(microseconds=1))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 2
    http.post(payload=envelope(STORE))
    freezer.move_to(deadline)
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 3
    assert entry.runtime_data.last_update_success
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("minutes", [None, 1, 7, 60])
async def test_configured_schedule_manual_reload_and_shutdown(
    hass, http, freezer, minutes
):
    freezer.move_to("2026-11-05T12:00:00.900000+00:00")
    start = dt_util.utcnow()
    options = {} if minutes is None else {"polling_interval": minutes}
    with patch("homeassistant.helpers.update_coordinator.randint", return_value=50_000):
        entry = await setup_entry(hass, http, options=options)
    seconds = (minutes or 2) * 60
    assert entry.runtime_data.update_interval == timedelta(seconds=seconds)
    for count, wait in [(2, 9), (3, 13)]:
        # Fire Core's actual rounded timer, then the exact not-before deadline.
        deadline = start + timedelta(seconds=seconds * (count - 1))
        early = deadline.replace(microsecond=50_000)
        freezer.move_to(early)
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(http.requests) == count - 1
        freezer.move_to(deadline - timedelta(microseconds=1))
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(http.requests) == count - 1
        http.post(
            payload=envelope(dict(STORE, displayDetails={"waitTimeAsNumber": wait}))
        )
        freezer.move_to(deadline)
        async_fire_time_changed_exact(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(http.requests) == count
        assert sorted(s.state for s in hass.states.async_all("sensor")) == [str(wait)]
        assert hass.states.async_all("binary_sensor")[0].state == "on"
        if count == 2:
            await entry.runtime_data.async_refresh()
            with patch(
                "homeassistant.helpers.update_coordinator.randint", return_value=50_000
            ):
                assert await hass.config_entries.async_reload(entry.entry_id)
            assert len(http.requests) == count
    assert await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(start + timedelta(seconds=seconds * 3))
    async_fire_time_changed_exact(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(http.requests) == 3


async def set_interval(hass, entry, minutes):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"polling_interval": minutes}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_changed_options_reload_once_and_cleanup(hass, http):
    entry = await setup_entry(hass, http)
    original = entry.runtime_data
    await set_interval(hass, entry, 7)
    replacement = entry.runtime_data
    assert replacement is not original
    assert original._shutdown_requested
    assert replacement.update_interval == timedelta(minutes=7)
    assert len(http.requests) == 1
    await set_interval(hass, entry, 7)
    assert entry.runtime_data is replacement
    # Data-only writes also invoke HA update listeners; do not reload on them.
    hass.config_entries.async_update_entry(
        entry, data=dict(entry.data, name="Renamed Salon")
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data is replacement
    assert len(entry.update_listeners) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert len(entry.update_listeners) == 0
    await set_interval(hass, entry, 5)
    assert not hasattr(entry, "runtime_data")
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.update_interval == timedelta(minutes=5)
    assert len(entry.update_listeners) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert len(entry.update_listeners) == 0


@pytest.mark.parametrize("before,after", [(2, 7), (7, 1)])
async def test_options_cannot_shorten_request_deadline(
    hass, http, freezer, before, after
):
    entry = await setup_entry(hass, http, options={"polling_interval": before})
    identity = entry.entry_id, entry.unique_id, dict(entry.data)
    freezer.tick(timedelta(seconds=30))
    await set_interval(hass, entry, after)
    freezer.tick(timedelta(seconds=max(before, after) * 60 - 31))
    await entry.runtime_data.async_refresh()
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert len(http.requests) == 1
    freezer.tick(timedelta(seconds=2))
    http.post(payload=envelope(STORE))
    await entry.runtime_data.async_refresh()
    assert len(http.requests) == 2
    assert (entry.entry_id, entry.unique_id, dict(entry.data)) == identity
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("retry_after", [180, 900])
async def test_options_preserve_error_cooldown(hass, http, freezer, retry_after):
    from homeassistant.config_entries import ConfigEntryState

    entry = await setup_entry(hass, http, options={"polling_interval": 7})
    freezer.tick(timedelta(seconds=421))
    http.post(status=429, headers={"Retry-After": str(retry_after)})
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
    await set_interval(hass, entry, 1)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    http.post(payload=envelope(STORE))
    deadline = max(420, retry_after)
    freezer.tick(timedelta(seconds=deadline - 1))
    assert not await hass.config_entries.async_reload(entry.entry_id)
    assert len(http.requests) == 2
    freezer.tick(timedelta(seconds=2))
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert len(http.requests) == 3
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_updates_existing_entry(hass, http):
    entry = await setup_entry(hass, http)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    json.dumps(fields)
    assert fields[0]["name"] == "polling_interval"
    assert fields[0]["default"] == 2
    for invalid in [0, 61, 1.5, True, "3"]:
        with pytest.raises(probatio.Invalid):
            result["data_schema"]({"polling_interval": invalid})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"polling_interval": 7.0}
    )
    assert result["type"] == "create_entry"
    assert entry.options == {"polling_interval": 7}
    assert type(entry.options["polling_interval"]) is int
    assert entry.data == asdict(SALON)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert fields[0]["default"] == 7
    hass.config_entries.options.async_abort(result["flow_id"])
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("minutes", [None, 1, 7, 60])
async def test_setup_polling_form_and_persistence(hass, http, minutes):
    http.get(payload=SEARCH)
    http.post(payload=envelope(STORE))
    http.post(payload=envelope(STORE))
    result = await configure(hass, await begin(hass), {"search": "Example"})
    result = await configure(hass, result, {"location": "0"})
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    json.dumps(fields)
    field = next(f for f in fields if f["name"] == "polling_interval")
    assert field["default"] == 2
    assert field["selector"]["number"] == {
        "min": 1,
        "max": 60,
        "step": 1,
        "mode": "box",
        "unit_of_measurement": "min",
    }
    data = {"salon": SALON.id}
    if minutes is not None:
        data["polling_interval"] = minutes
    result = await configure(hass, result, data)
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.data == asdict(SALON)
    assert entry.options == {"polling_interval": minutes or 2}
    assert entry.unique_id == SALON.id
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
