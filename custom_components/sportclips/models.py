"""Validated public geographic identities and immutable provider snapshots."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def text(value: Any) -> str:
    """Require a nonempty bounded public identifier or label."""
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("invalid text")
    return value


def coordinate(value: Any, limit: int) -> float:
    """Reject booleans, strings, infinities and out-of-range coordinates."""
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or abs(value) > limit
    ):
        raise ValueError("invalid coordinate")
    return float(value)


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        text(self.name)
        coordinate(self.latitude, 90)
        coordinate(self.longitude, 180)


@dataclass(frozen=True)
class Salon:
    id: str
    short_name: str
    name: str
    latitude: float
    longitude: float
    time_zone: str

    def __post_init__(self) -> None:
        text(self.id)
        text(self.short_name)
        text(self.name)
        coordinate(self.latitude, 90)
        coordinate(self.longitude, 180)
        # Database validation belongs to the client's async timezone resolver.
        text(self.time_zone)


@dataclass(frozen=True)
class Snapshot:
    wait_minutes: float | None
    status: str | None
    generated_at: datetime
    fetched_at: datetime
