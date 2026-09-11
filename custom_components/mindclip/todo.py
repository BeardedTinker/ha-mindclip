"""To-do platform for MindClip."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MindClipConfigEntry
from .entity import MindClipEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MindClipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the pending MindClip To-do list."""
    async_add_entities([MindClipTodoListEntity(entry)])


class MindClipTodoListEntity(MindClipEntity, TodoListEntity):
    """Represent newly discovered To-Dos awaiting local acknowledgement."""

    _attr_translation_key = "pending_todos"
    _attr_icon = "mdi:clipboard-check-outline"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, entry: MindClipConfigEntry) -> None:
        """Initialize the pending To-do list."""
        super().__init__(entry, entry.runtime_data.coordinator, "pending_todos")

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return pending items from coordinator memory."""
        return [
            TodoItem(
                uid=item.uid,
                summary=item.title,
                status=TodoItemStatus.NEEDS_ACTION,
                due=(
                    datetime.fromtimestamp(item.reminder_time / 1000, UTC)
                    if item.reminder_time is not None
                    else None
                ),
            )
            for item in self.coordinator.data.pending_todos
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Treat completion as local acknowledgement."""
        if item.uid is None or item.status != TodoItemStatus.COMPLETED:
            raise HomeAssistantError(
                "MindClip pending To-Dos can only be acknowledged as completed"
            )
        await self.coordinator.async_acknowledge_todo(item.uid)
