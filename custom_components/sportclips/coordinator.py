"""One shared, paced snapshot for both salon entities."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ProviderError, SportClipsClient, cooldown_deadline
from .const import DOMAIN, POLL_SECONDS
from .models import Salon, Snapshot

_LOGGER = logging.getLogger(__name__)


@dataclass
class PollState:
    """Keep salon pacing across reloads, with no stale fallback on failure."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_attempt: datetime = field(
        default_factory=lambda: datetime.min.replace(tzinfo=UTC)
    )
    snapshot: Snapshot | None = None
    failures: int = 0


class SportClipsCoordinator(DataUpdateCoordinator[Snapshot]):
    """Publish only complete snapshots; guard manual refresh and reload."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SportClipsClient,
        salon: Salon,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_SECONDS),
            always_update=False,
        )
        self.client = client
        self.salon = salon
        self.poll: PollState = (
            hass.data.setdefault(DOMAIN, {})
            .setdefault("polls", {})
            .setdefault(salon.id, PollState())
        )

    async def _async_update_data(self) -> Snapshot:
        async with self.poll.lock:
            if self._shutdown_requested:
                raise UpdateFailed("retired")
            if datetime.now(UTC) < self.poll.next_attempt:
                if self.poll.failures == 0 and self.poll.snapshot is not None:
                    return self.poll.snapshot
                raise UpdateFailed("cooldown")
            # An old cached success cannot be reused if this attempt retires.
            self.poll.snapshot = None
            try:
                snapshot = await self.client.wait(self.salon)
            except ProviderError as error:
                self.poll.failures += 1
                delay = max(
                    error.retry_after,
                    min(3600, POLL_SECONDS * 2 ** min(self.poll.failures - 1, 5)),
                )
                self.poll.next_attempt = cooldown_deadline(delay)
                raise UpdateFailed(str(error)) from None
            # Pacing belongs to the request, not to publication by this runtime.
            self.poll.next_attempt = cooldown_deadline(POLL_SECONDS)
            if self._shutdown_requested:
                raise UpdateFailed("retired")
            self.poll.failures = 0
            self.poll.snapshot = snapshot
            return snapshot
