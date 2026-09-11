"""Sensor platform for the MindClip integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MindClipConfigEntry
from .coordinator import MindClipData
from .entity import MindClipEntity


@dataclass(frozen=True, kw_only=True)
class MindClipSensorEntityDescription(SensorEntityDescription):
    """Describe a MindClip sensor."""

    value_fn: Callable[[MindClipData], StateType]
    health_fn: Callable[[MindClipData], bool]


SENSOR_DESCRIPTIONS = (
    MindClipSensorEntityDescription(
        key="open_todo_count",
        translation_key="open_todo_count",
        icon="mdi:format-list-checks",
        value_fn=lambda data: data.open_todo_count,
        health_fn=lambda data: not data.todos_truncated,
    ),
    MindClipSensorEntityDescription(
        key="recording_count",
        translation_key="recording_count",
        icon="mdi:microphone",
        value_fn=lambda data: data.recording_count,
        health_fn=lambda data: data.recordings_healthy,
    ),
    MindClipSensorEntityDescription(
        key="latest_recording_title",
        translation_key="latest_recording_title",
        icon="mdi:text-box-outline",
        value_fn=lambda data: data.latest_recording_title,
        health_fn=lambda data: data.recordings_healthy,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MindClipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MindClip sensors."""
    async_add_entities(
        MindClipSensor(entry, description) for description in SENSOR_DESCRIPTIONS
    )
    async_add_entities([MindClipSummarySensor(entry)])


class MindClipSensor(MindClipEntity, SensorEntity):
    """Represent a MindClip sensor."""

    entity_description: MindClipSensorEntityDescription

    def __init__(
        self,
        entry: MindClipConfigEntry,
        description: MindClipSensorEntityDescription,
    ) -> None:
        """Initialize a MindClip sensor."""
        super().__init__(entry, entry.runtime_data.coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether this sensor's source endpoint is healthy."""
        return super().available and self.entity_description.health_fn(
            self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the privacy-minimized sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class MindClipSummarySensor(MindClipEntity, SensorEntity):
    """Represent the latest recording summary."""

    _attr_translation_key = "latest_summary"
    _attr_icon = "mdi:text-box-search-outline"

    def __init__(self, entry: MindClipConfigEntry) -> None:
        """Initialize the latest summary sensor."""
        super().__init__(entry, entry.runtime_data.coordinator, "latest_summary")

    @property
    def available(self) -> bool:
        """Return whether the summary endpoint is healthy."""
        return super().available and self.coordinator.data.summary_healthy

    @property
    def native_value(self) -> StateType:
        """Return the recording ID associated with the latest summary."""
        summary = self.coordinator.data.latest_summary
        return summary.recording_id if summary is not None else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return only the conservatively capped summary text."""
        summary = self.coordinator.data.latest_summary
        if summary is None or summary.short_text is None:
            return None
        return {"summary": summary.short_text}
