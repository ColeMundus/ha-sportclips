from datetime import UTC, datetime

import aiohttp

from custom_components.sportclips.client import SportClipsClient
from custom_components.sportclips.models import Location

STORE = {
    "uid": "synthetic-store",
    "storeUid": "synthetic-store",
    "shortName": "XX001",
    "storeName": "Example Salon",
    "latitude": 35.0,
    "longitude": -90.0,
    "timeZone": "America/Chicago",
    "waitInfo": {"storeState": 10, "waitTime": "00:00:00"},
    "displayDetails": {"waitTimeAsNumber": 0},
}


def envelope(*stores):
    return {
        "generatedAt": "2026-11-05T21:00:00Z",
        "response": {"storeWaitTimes": list(stores)},
    }


async def test_discover_then_read_selected_store_preserves_zero(http):
    http.post(payload=envelope(STORE))
    http.post(payload=envelope(dict(STORE, uid="other", storeUid="other"), STORE))
    async with aiohttp.ClientSession() as session:
        client = SportClipsClient(session)
        salons = await client.discover(Location("Example", 35.0, -90.0))
        snapshot = await client.wait(salons[0])
    assert snapshot.wait_minutes == 0
    assert snapshot.status == "open"
    assert snapshot.generated_at == datetime(2026, 11, 5, 21, tzinfo=UTC)
    assert salons[0].id == "synthetic-store"
    assert http.requests[0][3]["data"]["mapArea"]["width"] == 0.8
    assert http.requests[1][3]["data"]["mapArea"]["width"] == 0.01
    assert http.requests[1][2]["storeId"] == "synthetic-store"
