"""Native estimated wait and independent provider store status."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SportClipsConfigEntry
from .client import STATES
from .coordinator import SportClipsCoordinator

DESCRIPTIONS = (
    SensorEntityDescription(
        key="wait",
        translation_key="wait",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATES.values()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SportClipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Register both entities against the single polling coordinator."""
    async_add_entities(
        SportClipsSensor(entry.runtime_data, description)
        for description in DESCRIPTIONS
    )


class SportClipsSensor(CoordinatorEntity[SportClipsCoordinator], SensorEntity):
    """Expose cached values without network I/O."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SportClipsCoordinator, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.salon.id}_{description.key}"
        label = "Estimated wait" if description.key == "wait" else "Store status"
        self._attr_name = f"Sport Clips {coordinator.salon.name} {label}"
        self._object_id = f"sports_clips_{coordinator.salon.name} {label}"

    @property
    def suggested_object_id(self) -> str:
        """Prefix default IDs without replacing existing registry identities."""
        return self._object_id

    @property
    def icon(self) -> str | None:
        """Represent the provider's store status without changing its enum type."""
        if self.entity_description.key != "status":
            return super().icon
        if not self.available:
            return "mdi:door"
        status = self.coordinator.data.status
        if status == "open":
            return "mdi:door-open"
        if status in (
            "lineup_opens_soon",
            "opens_soon",
            "closed_until_next_day",
            "closed",
        ):
            return "mdi:door-closed"
        return "mdi:door"

    @property
    def native_value(self) -> float | str | None:
        """Use provider values, never derive zero from absence."""
        snapshot = self.coordinator.data
        return (
            snapshot.wait_minutes
            if self.entity_description.key == "wait"
            else snapshot.status
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Response generation and local fetch time are not source freshness."""
        return {
            "response_generated_at": self.coordinator.data.generated_at.isoformat(),
            "fetched_at": self.coordinator.data.fetched_at.isoformat(),
        }
