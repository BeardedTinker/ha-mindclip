"""Tests for the MindClip API client."""

from collections.abc import Mapping
from typing import Any

import pytest

from custom_components.mindclip import api as api_module
from custom_components.mindclip.api import (
    MindClipApi,
    MindClipAuthError,
    MindClipDevice,
    MindClipResponseError,
    MindClipSchemaError,
)
from custom_components.mindclip.const import API_BASE_URL, SUMMARY_ATTRIBUTE_LIMIT

DEVICE_ID = "MINDCLIP-TEST-001"


class FakeResponse:
    """Small aiohttp response context-manager fake."""

    def __init__(self, payload: object, status: int = 200) -> None:
        """Initialize a fake response."""
        self.payload = payload
        self.status = status

    async def __aenter__(self) -> FakeResponse:
        """Enter the response context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the response context."""

    async def json(self, *, content_type: None = None) -> object:
        """Return the configured JSON payload."""
        return self.payload


class FakeSession:
    """Small aiohttp client-session fake."""

    def __init__(self, *responses: FakeResponse) -> None:
        """Initialize the queued responses."""
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str | int] | None,
    ) -> FakeResponse:
        """Record the request and return the next response."""
        self.calls.append({"url": url, "headers": headers, "params": params})
        return self.responses.pop(0)


def _success(body: object) -> FakeResponse:
    """Return a successful SwitchBot response."""
    return FakeResponse({"statusCode": 100, "message": "success", "body": body})


@pytest.mark.asyncio
async def test_device_discovery_filters_mindclips() -> None:
    """Device discovery returns only normalized AI MindClip devices."""
    session = FakeSession(
        _success(
            {
                "deviceList": [
                    {
                        "deviceId": "hub-one",
                        "deviceName": "Hub",
                        "deviceType": "Hub 2",
                    },
                    {
                        "deviceId": "mindclip-test-001",
                        "deviceName": "Pocket notes",
                        "deviceType": "AI MindClip",
                    },
                ],
                "infraredRemoteList": [],
            }
        )
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    devices = await client.async_get_devices()

    assert devices == [MindClipDevice(DEVICE_ID, "Pocket notes")]
    assert session.calls[0]["url"] == f"{API_BASE_URL}/devices"


@pytest.mark.asyncio
async def test_deterministic_request_signing() -> None:
    """Every request contains a deterministic valid signature."""
    session = FakeSession(
        _success(
            {
                "deviceId": DEVICE_ID,
                "deviceType": "AI MindClip",
                "chargingStatus": 1,
            }
        )
    )
    client = MindClipApi(
        session,  # type: ignore[arg-type]
        "token",
        "secret",
        clock=lambda: 1700000000.123,
        nonce_factory=lambda: "fixed-nonce",
    )

    status = await client.async_get_device_status(DEVICE_ID)

    assert status.charging is True
    assert session.calls == [
        {
            "url": f"{API_BASE_URL}/devices/{DEVICE_ID}/status",
            "headers": {
                "Authorization": "token",
                "sign": "bswPa97bfK+JqPT0ovgOfua8GxlBX2SbVU5fJE/x0pE=",
                "nonce": "fixed-nonce",
                "t": "1700000000123",
                "Content-Type": "application/json",
            },
            "params": None,
        }
    ]


@pytest.mark.asyncio
async def test_todo_pagination_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """To-Do pagination stops at the configured safety bound."""
    monkeypatch.setattr(api_module, "API_MAX_PAGES", 2)
    page = {
        "pages": 3,
        "list": [
            {
                "deviceID": DEVICE_ID,
                "isCompleted": False,
                "fileID": "recording-one",
                "createdTime": 1000,
                "reminderTime": 2000,
                "title": "Call the office",
            }
        ],
    }
    session = FakeSession(_success(page), _success(page))
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    result = await client.async_get_open_todo_count(DEVICE_ID)

    assert result.count == 2
    assert result.truncated is True
    assert result.items[0].title == "Call the office"
    assert result.items[0].reminder_time == 2000
    assert len(result.items[0].uid) == 64
    assert len(session.calls) == 2
    assert session.calls[0]["params"] == {
        "completedNum": 0,
        "pageNum": 1,
        "pageSize": 100,
    }
    assert session.calls[1]["params"]["pageNum"] == 2


@pytest.mark.asyncio
async def test_api_errors_do_not_include_response_content() -> None:
    """API exceptions expose only a status code, never response content."""
    private_content = "private-token private-secret private-recording-title"
    session = FakeSession(
        FakeResponse(
            {"statusCode": 190, "message": private_content, "body": private_content}
        )
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    with pytest.raises(MindClipResponseError) as error:
        await client.async_get_open_todo_count(DEVICE_ID)

    assert error.value.status_code == 190
    assert private_content not in str(error.value)


@pytest.mark.asyncio
async def test_arbitrary_status_content_is_not_echoed() -> None:
    """A non-numeric status is rejected without including its content."""
    private_content = "private-token-in-status"
    session = FakeSession(
        FakeResponse({"statusCode": private_content, "message": "failed", "body": {}})
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    with pytest.raises(MindClipSchemaError) as error:
        await client.async_get_open_todo_count(DEVICE_ID)

    assert private_content not in str(error.value)


@pytest.mark.asyncio
async def test_switchbot_auth_status_raises_auth_error() -> None:
    """Authentication failures in a successful HTTP response are explicit."""
    session = FakeSession(
        FakeResponse({"statusCode": "401", "message": "Unauthorized", "body": {}})
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    with pytest.raises(MindClipAuthError):
        await client.async_get_open_todo_count(DEVICE_ID)


@pytest.mark.asyncio
async def test_switchbot_forbidden_status_is_not_an_auth_error() -> None:
    """Permission and missing-resource errors do not trigger reauthentication."""
    session = FakeSession(
        FakeResponse({"statusCode": "403", "message": "Forbidden", "body": {}})
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    with pytest.raises(MindClipResponseError) as error:
        await client.async_get_open_todo_count(DEVICE_ID)

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_summary_path_is_encoded_and_text_is_capped() -> None:
    """Recording IDs are path-encoded and summary attributes stay bounded."""
    recording_id = "recording/with spaces"
    session = FakeSession(
        _success(
            {
                "fileID": recording_id,
                "aiSummaryResult": "x" * (SUMMARY_ATTRIBUTE_LIMIT + 20),
            }
        )
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    summary = await client.async_get_summary(recording_id)

    assert len(summary.short_text or "") == SUMMARY_ATTRIBUTE_LIMIT
    assert session.calls[0]["url"].endswith("/recording%2Fwith%20spaces")


@pytest.mark.asyncio
async def test_recordings_track_latest_and_latest_transcribed() -> None:
    """A recording in progress does not replace the latest completed transcript."""
    session = FakeSession(
        _success(
            {
                "total": 2,
                "pages": 1,
                "list": [
                    {
                        "id": "recording-new",
                        "displayName": "New recording",
                        "createdTime": 2000,
                        "transcribeStatus": 1,
                    },
                    {
                        "id": "recording-ready",
                        "displayName": "Ready recording",
                        "createdTime": 1000,
                        "transcribeStatus": 2,
                    },
                ],
            }
        )
    )
    client = MindClipApi(session, "token", "secret")  # type: ignore[arg-type]

    recordings = await client.async_get_recordings(DEVICE_ID)

    assert recordings.latest is not None
    assert recordings.latest.recording_id == "recording-new"
    assert recordings.latest_transcribed is not None
    assert recordings.latest_transcribed.recording_id == "recording-ready"
