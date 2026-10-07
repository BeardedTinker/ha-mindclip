"""Event platform for MindClip."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MindClipConfigEntry
from .entity import MindClipEntity
from .todo_store import PendingTodo

EVENT_TYPE_CREATED = "created"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MindClipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MindClip To-Do event entity."""
    async_add_entities([MindClipTodoEventEntity(entry)])


class MindClipTodoEventEntity(MindClipEntity, EventEntity):
    """Emit one event for each newly discovered MindClip To-Do."""

    _attr_translation_key = "new_todo"
    _attr_icon = "mdi:clipboard-text-clock-outline"
    _attr_event_types: ClassVar[list[str]] = [EVENT_TYPE_CREATED]

    def __init__(self, entry: MindClipConfigEntry) -> None:
        """Initialize the To-Do event entity."""
        super().__init__(entry, entry.runtime_data.coordinator, "new_todo")
        self._emitted_uids: set[str] = set()

    async def async_added_to_hass(self) -> None:
        """Emit discoveries from the initial refresh after entity registration."""
        await super().async_added_to_hass()
        self._emit_new_todos()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Emit events for discoveries from the latest coordinator refresh."""
        self._emit_new_todos()
        super()._handle_coordinator_update()

    @callback
    def _emit_new_todos(self) -> None:
        """Emit each discovery at most once for this entity instance."""
        for item in self.coordinator.data.new_todos:
            if item.uid in self._emitted_uids:
                continue
            self._trigger_event(EVENT_TYPE_CREATED, _event_attributes(item))
            self._emitted_uids.add(item.uid)
            self.async_write_ha_state()


def _event_attributes(item: PendingTodo) -> dict[str, str | None]:
    """Return bounded attributes for one newly discovered To-Do."""
    return {
        "uid": item.uid,
        "title": item.title,
        "created_at": _timestamp_to_iso(item.created_time),
        "reminder_at": (
            _timestamp_to_iso(item.reminder_time)
            if item.reminder_time is not None
            else None
        ),
    }


def _timestamp_to_iso(timestamp: int) -> str:
    """Convert a SwitchBot millisecond timestamp to UTC ISO 8601."""
    return datetime.fromtimestamp(timestamp / 1000, UTC).isoformat()
