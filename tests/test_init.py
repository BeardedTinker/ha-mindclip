"""Tests for the MindClip integration lifecycle."""

from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip.api import (
    DeviceStatus,
    OpenTodoCount,
    Recording,
    RecordingCollection,
    RecordingSummary,
)
from custom_components.mindclip.const import (
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
)

DEVICE_ID = "MINDCLIP-TEST-001"


async def test_setup_and_unload_entry(hass) -> None:
    """The integration loads its platforms and removes their states on unload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MindClip ST-001",
        data={
            CONF_API_TOKEN: "token",
            CONF_API_SECRET: "secret",
            CONF_DEVICE_ID: DEVICE_ID,
        },
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_open_todo_count",
            AsyncMock(return_value=OpenTodoCount(count=3, truncated=False)),
        ),
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=True)),
        ),
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_recordings",
            AsyncMock(
                return_value=RecordingCollection(
                    total=1,
                    latest=Recording("recording-one", "Planning", 1000, 2),
                    latest_transcribed=Recording("recording-one", "Planning", 1000, 2),
                    truncated=False,
                )
            ),
        ),
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_summary",
            AsyncMock(return_value=RecordingSummary("recording-one", "Short summary")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    todo_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_open_todo_count"
    )
    charging_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DEVICE_ID}_charging"
    )
    assert todo_entity_id is not None
    assert charging_entity_id is not None
    todo_state = hass.states.get(todo_entity_id)
    charging_state = hass.states.get(charging_entity_id)
    assert todo_state is not None
    assert charging_state is not None
    assert todo_state.state == "3"
    assert charging_state.state == "on"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(todo_entity_id) is None
    assert hass.states.get(charging_entity_id) is None
