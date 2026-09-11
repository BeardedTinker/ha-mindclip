"""Base entity for the MindClip integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MindClipConfigEntry
from .const import DOMAIN
from .coordinator import MindClipCoordinator


class MindClipEntity(CoordinatorEntity[MindClipCoordinator]):
    """Base class for MindClip entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MindClipConfigEntry,
        coordinator: MindClipCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize a MindClip entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="SwitchBot",
            model="AI MindClip",
            name=entry.title,
        )
