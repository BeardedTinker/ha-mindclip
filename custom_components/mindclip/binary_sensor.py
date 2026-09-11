"""Binary sensor platform for the MindClip integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MindClipConfigEntry
from .entity import MindClipEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MindClipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MindClip charging sensor."""
    async_add_entities([MindClipChargingSensor(entry)])


class MindClipChargingSensor(MindClipEntity, BinarySensorEntity):
    """Represent the MindClip charging state."""

    _attr_translation_key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, entry: MindClipConfigEntry) -> None:
        """Initialize the charging sensor."""
        super().__init__(entry, entry.runtime_data.coordinator, "charging")

    @property
    def available(self) -> bool:
        """Return whether device status is healthy."""
        return super().available and self.coordinator.data.device_status_healthy

    @property
    def is_on(self) -> bool | None:
        """Return whether the MindClip is charging."""
        return self.coordinator.data.charging
