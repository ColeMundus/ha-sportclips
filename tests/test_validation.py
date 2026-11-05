from copy import deepcopy

import aiohttp
import pytest

from custom_components.sportclips.client import ProviderError, SportClipsClient
from custom_components.sportclips.models import Salon
from tests.test_metadata import STORE, envelope

SALON = Salon("synthetic-store", "XX001", "Example Salon", 35, -90, "America/Chicago")


@pytest.mark.parametrize(
    ("state", "wait", "expected"),
    [
        (10, 18, 18),
        (10, 0, 0),
        (10, None, None),
        (40, 0, None),
        (50, 8, None),
        (60, 9, None),
        (999, 12, None),
        (20, 4, None),
        (10, -1, None),
        (10, True, None),
        (10, "3", None),
        (10, float("inf"), None),
    ],
)
async def test_wait_semantics(http, state, wait, expected):
    item = deepcopy(STORE)
    item["waitInfo"]["storeState"] = state
    item["displayDetails"]["waitTimeAsNumber"] = wait
    http.post(payload=envelope(item))
    async with aiohttp.ClientSession() as session:
        result = await SportClipsClient(session).wait(SALON)
    assert result.wait_minutes == expected
    assert result.status == (
        "open"
        if state == 10
        else {
            20: "lineup_opens_soon",
            40: "closed_until_next_day",
            50: "closed",
            60: "offline",
        }.get(state)
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"response": []},
        envelope(),
        dict(envelope(STORE), generatedAt="nonsense"),
        dict(envelope(STORE), generatedAt="2026-11-05T21:00:00"),
        {"response": {"storeWaitTimes": [None]}},
    ],
)
async def test_invalid_or_missing_selected_response_is_provider_error(http, data):
    http.post(payload=data)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError):
            await SportClipsClient(session).wait(SALON)


@pytest.mark.parametrize(
    "item",
    [
        None,
        {},
        {"placeName": "", "latitude": 35, "longitude": -90},
        {"placeName": "Example", "latitude": 91, "longitude": -90},
        {"placeName": "Example", "latitude": True, "longitude": -90},
    ],
)
async def test_invalid_search_rejected(http, item):
    http.get(payload={"response": {"searchedLocations": [item]}})
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError):
            await SportClipsClient(session).search("Example")
