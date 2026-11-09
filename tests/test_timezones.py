"""Exercise cold timezone reads, not just prewarmed ZoneInfo caches."""

import threading
from dataclasses import asdict, replace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo, _common

import aiohttp
import aiozoneinfo
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sportclips.client import ProviderError, SportClipsClient
from custom_components.sportclips.models import Location
from tests.test_metadata import STORE, envelope
from tests.test_validation import SALON


@pytest.mark.parametrize("path", ["discovery", "setup"])
async def test_cold_timezone_reads_stay_off_event_loop(hass, http, path):
    zone = "Pacific/Chatham"
    ZoneInfo.clear_cache()
    aiozoneinfo.CachedZoneInfo.clear_cache()
    loop_thread = threading.get_ident()
    reads = []
    load_data = _common.load_data

    def guarded_load_data(file):
        reads.append(threading.get_ident())
        assert threading.get_ident() != loop_thread, "timezone read blocks event loop"
        return load_data(file)

    http.post(payload=envelope(dict(STORE, timeZone=zone)))
    with patch("zoneinfo._common.load_data", side_effect=guarded_load_data):
        if path == "discovery":
            async with aiohttp.ClientSession() as session:
                salons = await SportClipsClient(session).discover(
                    Location("Example", 35, -90)
                )
            assert salons[0].time_zone == zone
        else:
            entry = MockConfigEntry(
                domain="sportclips",
                unique_id=SALON.id,
                data=dict(asdict(SALON), time_zone=zone),
            )
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done(wait_background_tasks=True)
            assert entry.state is ConfigEntryState.LOADED
            assert await hass.config_entries.async_unload(entry.entry_id)
    assert reads, "test must exercise a cold timezone database read"


@pytest.mark.parametrize("zone", ["Invalid/Timezone", "/invalid/absolute/path"])
@pytest.mark.parametrize("path", ["discovery", "wait"])
async def test_invalid_timezone_is_sanitized(http, zone, path):
    if path == "discovery":
        http.post(payload=envelope(dict(STORE, timeZone=zone)))
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session)
        with pytest.raises(ProviderError, match="^invalid_response$"):
            if path == "discovery":
                await client.discover(Location("Example", 35, -90))
            else:
                await client.wait(replace(SALON, time_zone=zone))
    assert len(http.requests) == (1 if path == "discovery" else 0)


async def test_repeated_polls_reuse_resolved_timezone(http, freezer):
    freezer.move_to("2026-11-06T00:30:00Z")
    for _ in range(3):
        http.post(payload=envelope(STORE))
    resolver = AsyncMock(wraps=dt_util.async_get_time_zone)
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session)
        with patch(
            "custom_components.sportclips.client.dt_util.async_get_time_zone", resolver
        ):
            salons = await client.discover(Location("Example", 35, -90))
            await client.wait(salons[0])
            await client.wait(salons[0])
    resolver.assert_awaited_once_with("America/Chicago")
    assert [request[2]["scheduleFromDate"] for request in http.requests] == [
        "2026-11-06",
        "2026-11-05",
        "2026-11-05",
    ]
