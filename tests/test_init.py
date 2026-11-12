"""Tests for the MindClip integration lifecycle."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip.api import (
    DeviceStatus,
    FullRecordingSummary,
    OpenTodoCount,
    Recording,
    RecordingCollection,
    RecordingDetail,
    RecordingSummary,
    RecordingTranscript,
    Speaker,
    SummaryTodo,
)
from custom_components.mindclip.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_RECORDING_ID,
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
    SERVICE_GET_RECORDING,
    SERVICE_GET_SUMMARY,
    SERVICE_GET_TRANSCRIPT,
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
            AsyncMock(
                return_value=DeviceStatus(
                    battery=75,
                    charging=True,
                    recording=False,
                    uploading=False,
                    has_untransferred_files=False,
                )
            ),
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
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_recording_detail",
            AsyncMock(
                return_value=RecordingDetail(
                    recording_id="recording-one",
                    display_name="Planning",
                    recording_length=120,
                    file_size=2048,
                    device_id=DEVICE_ID,
                    transcription_status=2,
                    created_time=1000,
                    folder_id=3,
                    emoji="note",
                    is_system=False,
                )
            ),
        ) as detail_mock,
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_transcript",
            AsyncMock(
                return_value=RecordingTranscript(
                    recording_id="recording-one",
                    transcription_status=2,
                    transcription='{"segments":[]}',
                    speakers=(Speaker("spk_1", "Alice"),),
                )
            ),
        ),
        patch(
            "custom_components.mindclip.api.MindClipApi.async_get_full_summary",
            AsyncMock(
                return_value=FullRecordingSummary(
                    recording_id="recording-one",
                    transcription_status=2,
                    transcription="Full transcript",
                    summary="Full summary",
                    template="## Notes",
                    atmosphere="Focused",
                    todos=(
                        SummaryTodo(
                            "Send notes",
                            2000,
                            False,
                            1000,
                            "recording-one",
                            DEVICE_ID,
                            1,
                        ),
                    ),
                    speakers=(Speaker("spk_1", "Alice", "#fff", "#000", 0.9),),
                )
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, SERVICE_GET_RECORDING)
        assert hass.services.has_service(DOMAIN, SERVICE_GET_TRANSCRIPT)
        assert hass.services.has_service(DOMAIN, SERVICE_GET_SUMMARY)
        action_data = {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_RECORDING_ID: " recording-one ",
        }
        recording_response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_RECORDING,
            action_data,
            blocking=True,
            return_response=True,
        )
        transcript_response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TRANSCRIPT,
            action_data,
            blocking=True,
            return_response=True,
        )
        summary_response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SUMMARY,
            action_data,
            blocking=True,
            return_response=True,
        )

        assert recording_response["display_name"] == "Planning"
        assert transcript_response["transcription"] == '{"segments":[]}'
        assert transcript_response["speakers"][0]["speaker_name"] == "Alice"
        assert summary_response["summary"] == "Full summary"
        assert summary_response["todos"][0]["title"] == "Send notes"
        assert detail_mock.await_count == 3
        detail_mock.assert_awaited_with("recording-one", DEVICE_ID)

    registry = er.async_get(hass)
    todo_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_open_todo_count"
    )
    charging_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DEVICE_ID}_charging"
    )
    battery_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_battery"
    )
    recording_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DEVICE_ID}_recording"
    )
    event_entity_id = registry.async_get_entity_id(
        "event", DOMAIN, f"{DEVICE_ID}_new_todo"
    )
    assert todo_entity_id is not None
    assert charging_entity_id is not None
    assert battery_entity_id is not None
    assert recording_entity_id is not None
    assert event_entity_id is not None
    todo_state = hass.states.get(todo_entity_id)
    charging_state = hass.states.get(charging_entity_id)
    battery_state = hass.states.get(battery_entity_id)
    recording_state = hass.states.get(recording_entity_id)
    assert todo_state is not None
    assert charging_state is not None
    assert battery_state is not None
    assert recording_state is not None
    assert todo_state.state == "3"
    assert charging_state.state == "on"
    assert battery_state.state == "75"
    assert recording_state.state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    todo_state = hass.states.get(todo_entity_id)
    charging_state = hass.states.get(charging_entity_id)
    assert todo_state is not None
    assert charging_state is not None
    assert todo_state.state == STATE_UNAVAILABLE
    assert charging_state.state == STATE_UNAVAILABLE
