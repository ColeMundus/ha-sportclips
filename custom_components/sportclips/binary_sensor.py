"""Native Open/Closed store status from the shared provider snapshot."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SportClipsConfigEntry
from .const import DOMAIN
from .coordinator import SportClipsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SportClipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Use the existing coordinator without another refresh."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.data['id']}_status"
    )
    device_info = None
    if entity_id is not None and (record := registry.async_get(entity_id)) is not None:
        # Core can reassign an unloaded foreign record during entity registration.
        if record.config_entry_id != entry.entry_id:
            return
        if (
            record.device_id is not None
            and (device := dr.async_get(hass).async_get(record.device_id)) is not None
        ):
            # The platform otherwise passes device_id=None and clears the
            # association we migrated, even though the registry record exists.
            device_info = DeviceInfo(identifiers=device.identifiers)
            if isinstance(device, dr.DeviceEntry):
                device_info["connections"] = device.connections
    async_add_entities([SportClipsOpening(entry.runtime_data, device_info)])


class SportClipsOpening(CoordinatorEntity[SportClipsCoordinator], BinarySensorEntity):
    """Only a provider-confirmed open store is on."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_translation_key = "status"

    def __init__(
        self, coordinator: SportClipsCoordinator, device_info: DeviceInfo | None = None
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{coordinator.salon.id}_status"
        self._attr_name = f"Sport Clips {coordinator.salon.name} Store status"
        self._object_id = f"sports_clips_{coordinator.salon.name} Store status"

    @property
    def suggested_object_id(self) -> str:
        """Keep the established object name in the new native domain."""
        return self._object_id

    @property
    def is_on(self) -> bool | None:
        """Offline and unrecognized codes do not mean closed."""
        status = self.coordinator.data.status
        if status == "open":
            return True
        if status in (
            "lineup_opens_soon",
            "opens_soon",
            "closed_until_next_day",
            "closed",
        ):
            return False
        return None

    @property
    def icon(self) -> str:
        """Door icons reflect known status, not a stale failed snapshot."""
        if not self.available or self.is_on is None:
            return "mdi:door"
        return "mdi:door-open" if self.is_on else "mdi:door-closed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Retain provider detail without exposing a duplicate enum sensor."""
        return {
            "provider_status": self.coordinator.data.status,
            "response_generated_at": self.coordinator.data.generated_at.isoformat(),
            "fetched_at": self.coordinator.data.fetched_at.isoformat(),
        }
