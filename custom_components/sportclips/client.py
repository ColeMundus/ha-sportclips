"""Anonymous read-only Sport Clips transport; no personal/account endpoints."""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiohttp import ClientError, ClientSession, ClientTimeout

from .models import Location, Salon, Snapshot

BASE = "https://api.sportclipsinc.com/api/v1/store"
STATES = {
    10: "open",
    20: "lineup_opens_soon",
    30: "opens_soon",
    40: "closed_until_next_day",
    50: "closed",
    60: "offline",
}


class ProviderError(Exception):
    """A sanitized provider failure, never containing a raw response."""

    def __init__(self, category: str, retry_after: float = 120) -> None:
        super().__init__(category)
        self.retry_after = retry_after


@dataclass
class RequestGate:
    """HA-lifetime host-wide error cooldown, shared across flows and entries."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    not_before: datetime = field(
        default_factory=lambda: datetime.min.replace(tzinfo=UTC)
    )
    failures: int = 0


def retry_delay(value: str | None) -> float:
    """Parse delta seconds or an HTTP-date without trusting provider error text."""
    try:
        delay = float(value) if value is not None else 0.0
    except ValueError:
        try:
            delay = (
                parsedate_to_datetime(value or "") - datetime.now(UTC)
            ).total_seconds()
        except TypeError, ValueError, OverflowError:
            delay = 0.0
    return max(120, delay) if math.isfinite(delay) else 120


def cooldown_deadline(seconds: float) -> datetime:
    """Saturate unrepresentable provider delays instead of overflowing HA setup."""
    try:
        return datetime.now(UTC) + timedelta(seconds=seconds)
    except OverflowError:
        return datetime.max.replace(tzinfo=UTC)


class SportClipsClient:
    """Use the caller-owned HTTP session; never acquire personal credentials."""

    def __init__(self, session: ClientSession, gate: RequestGate | None = None) -> None:
        self.session = session
        self.gate = gate if gate is not None else RequestGate()

    async def _request(self, method: str, route: str, **kwargs: Any) -> dict[str, Any]:
        async with self.gate.lock:
            remaining = (self.gate.not_before - datetime.now(UTC)).total_seconds()
            if remaining > 0:
                raise ProviderError("cooldown", remaining)
            try:
                async with self.session.request(
                    method,
                    BASE + route,
                    timeout=ClientTimeout(total=20),
                    allow_redirects=False,
                    **kwargs,
                ) as response:
                    if response.status != 200:
                        raise ProviderError(
                            "access" if response.status in (401, 403) else "http_error",
                            retry_delay(response.headers.get("Retry-After")),
                        )
                    data = await response.json()
                    if not isinstance(data, dict):
                        raise ProviderError("invalid_response")
            except ClientError, TimeoutError:
                error = ProviderError("transport")
            except ValueError:
                error = ProviderError("invalid_response")
            except ProviderError as exc:
                error = exc
            else:
                self.gate.failures = 0
                return data
            self.gate.failures += 1
            delay = max(
                error.retry_after, min(3600, 120 * 2 ** min(self.gate.failures - 1, 5))
            )
            self.gate.not_before = cooldown_deadline(delay)
            raise ProviderError(str(error), delay) from None

    async def search(self, text: str) -> list[Location]:
        data = await self._request("GET", "/search", params={"searchText": text})
        try:
            return [
                Location(item["placeName"], item["latitude"], item["longitude"])
                for item in data["response"]["searchedLocations"]
            ]
        except KeyError, TypeError, ValueError:
            raise ProviderError("invalid_response") from None

    async def _metadata(
        self,
        latitude: float,
        longitude: float,
        width: float,
        store_id: str = "",
        time_zone: str = "UTC",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/metadata",
            params={
                "zoomLevel": "10",
                "storeId": store_id,
                "scheduleFromDate": datetime.now(ZoneInfo(time_zone))
                .date()
                .isoformat(),
            },
            json={
                "data": {
                    "mapArea": {
                        "centerLat": latitude,
                        "centerLon": longitude,
                        "width": width,
                        "height": width,
                    }
                }
            },
        )

    async def discover(self, location: Location) -> list[Salon]:
        data = await self._metadata(location.latitude, location.longitude, 0.8)
        try:
            return [
                Salon(
                    item["uid"],
                    item["shortName"],
                    item["storeName"],
                    item["latitude"],
                    item["longitude"],
                    item["timeZone"],
                )
                for item in data["response"]["storeWaitTimes"]
            ]
        except KeyError, TypeError, ValueError, ZoneInfoNotFoundError:
            raise ProviderError("invalid_response") from None

    async def wait(self, salon: Salon) -> Snapshot:
        data = await self._metadata(
            salon.latitude, salon.longitude, 0.01, salon.id, salon.time_zone
        )
        try:
            item = next(
                item
                for item in data["response"]["storeWaitTimes"]
                if item["uid"] == salon.id
            )
            state = item["waitInfo"]["storeState"]
            status = STATES.get(state) if type(state) is int else None
            wait = item.get("displayDetails", {}).get("waitTimeAsNumber")
            if (
                status != "open"
                or type(wait) not in (int, float)
                or not math.isfinite(wait)
                or wait < 0
            ):
                wait = None
            generated = datetime.fromisoformat(data["generatedAt"])
            if generated.utcoffset() is None:
                raise ValueError("undated response")
            return Snapshot(wait, status, generated, datetime.now(UTC))
        except KeyError, TypeError, ValueError, StopIteration, AttributeError:
            raise ProviderError("invalid_response") from None
