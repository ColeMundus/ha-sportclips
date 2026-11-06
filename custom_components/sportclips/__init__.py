"""Anonymous Sport Clips wait monitoring."""

from homeassistant.components.homeassistant.exposed_entities import KNOWN_ASSISTANTS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import RequestGate, SportClipsClient
from .const import DOMAIN
from .coordinator import SportClipsCoordinator
from .models import Salon

type SportClipsConfigEntry = ConfigEntry[SportClipsCoordinator]
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


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
    _migrate_status_registry(hass, entry)
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


def _migrate_status_registry(hass: HomeAssistant, entry: SportClipsConfigEntry) -> None:
    """Replace the enum through public APIs before either platform is loaded.

    Core forbids changing an entity ID's domain. Create the replacement first,
    copy cross-domain user settings, then remove only this entry's old status.
    Sensor-specific options/device-class overrides cannot apply to a boolean.
    """
    registry = er.async_get(hass)
    unique_id = f"{entry.data['id']}_status"
    old_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    if old_id is None:
        return
    old = registry.async_get(old_id)
    if old is None or old.config_entry_id != entry.entry_id:
        return
    new_id = registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    if new_id is None:
        new = registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            unique_id,
            config_entry=entry,
            config_subentry_id=old.config_subentry_id,
            suggested_object_id=old_id.split(".", 1)[1],
            device_id=old.device_id,
            disabled_by=old.disabled_by,
            hidden_by=old.hidden_by,
            original_device_class="opening",
            original_name=old.original_name,
            has_entity_name=old.has_entity_name,
        )
        registry.async_update_entity(
            new.entity_id,
            # Core can apply the new-entities preference despite disabled_by=None.
            # This replaces an existing entity, so restore its enabled setting.
            disabled_by=old.disabled_by,
            hidden_by=old.hidden_by,
            name=old.name,
            icon=old.icon,
            area_id=old.area_id,
            aliases=old.aliases,
            labels=old.labels,
            categories=old.categories,
        )
        # Preserve domain-independent options through Core's public API, not
        # sensor formatting/precision or stale binary-sensor-specific settings.
        for domain, options in old.options.items():
            if domain not in ("sensor", "binary_sensor"):
                registry.async_update_entity_options(new.entity_id, domain, options)
        # An enum status is not default-exposed; an Opening binary sensor is.
        # Preserve explicit choices and freeze the old non-exposure default,
        # including assistants with options but no stored should_expose flag.
        for assistant in KNOWN_ASSISTANTS:
            assistant_options = dict(old.options.get(assistant, {}))
            assistant_options.setdefault("should_expose", False)
            registry.async_update_entity_options(
                new.entity_id, assistant, assistant_options
            )
    elif (
        existing := registry.async_get(new_id)
    ) is None or existing.config_entry_id != entry.entry_id:
        # Never claim or delete another entry's identity.
        return
    registry.async_remove(old_id)


async def async_unload_entry(hass: HomeAssistant, entry: SportClipsConfigEntry) -> bool:
    """Unload entities; leave the shared HA session open."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
