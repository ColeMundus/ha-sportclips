"""Anonymous Sport Clips wait monitoring."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import RequestGate, SportClipsClient
from .const import DOMAIN
from .coordinator import SportClipsCoordinator
from .models import Salon

type SportClipsConfigEntry = ConfigEntry[SportClipsCoordinator]
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SportClipsConfigEntry) -> bool:
    """Load one salon using HA's session and shared runtime state."""
    gate = hass.data.setdefault(DOMAIN, {}).setdefault("gate", RequestGate())
    coordinator = SportClipsCoordinator(
        hass,
        entry,
        SportClipsClient(async_get_clientsession(hass), gate),
        Salon(**entry.data),
        poll_seconds=int(entry.options.get("polling_interval", 2)) * 60,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    loaded_options = dict(entry.options)

    async def async_options_updated(
        hass: HomeAssistant, updated_entry: SportClipsConfigEntry
    ) -> None:
        """Only an actual options change requires a new coordinator."""
        if dict(updated_entry.options) != loaded_options:
            await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SportClipsConfigEntry) -> bool:
    """Unload entities; leave the shared HA session open."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
