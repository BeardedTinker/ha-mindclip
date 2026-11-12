"""Binary sensor platform for the MindClip integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MindClipConfigEntry
from .coordinator import MindClipData
from .entity import MindClipEntity


@dataclass(frozen=True, kw_only=True)
class MindClipBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a MindClip binary sensor."""

    value_fn: Callable[[MindClipData], bool | None]


BINARY_SENSOR_DESCRIPTIONS = (
    MindClipBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda data: data.charging,
    ),
    MindClipBinarySensorEntityDescription(
        key="recording",
        translation_key="recording",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: data.recording,
    ),
    MindClipBinarySensorEntityDescription(
        key="uploading",
        translation_key="uploading",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: data.uploading,
    ),
    MindClipBinarySensorEntityDescription(
        key="untransferred_files",
        translation_key="untransferred_files",
        icon="mdi:file-upload-outline",
        value_fn=lambda data: data.has_untransferred_files,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MindClipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MindClip binary sensors."""
    async_add_entities(
        MindClipBinarySensor(entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class MindClipBinarySensor(MindClipEntity, BinarySensorEntity):
    """Represent a MindClip binary status."""

    entity_description: MindClipBinarySensorEntityDescription

    def __init__(
        self,
        entry: MindClipConfigEntry,
        description: MindClipBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(entry, entry.runtime_data.coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether device status is healthy."""
        return super().available and self.coordinator.data.device_status_healthy

    @property
    def is_on(self) -> bool | None:
        """Return the binary status."""
        return self.entity_description.value_fn(self.coordinator.data)
