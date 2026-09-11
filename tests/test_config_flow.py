"""Tests for the MindClip config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mindclip.api import (
    DeviceStatus,
    MindClipAuthError,
    MindClipDevice,
)
from custom_components.mindclip.const import (
    CONF_API_SECRET,
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    DOMAIN,
)

DEVICE_ID = "MINDCLIP-TEST-001"
CREDENTIALS = {
    CONF_API_TOKEN: "token",
    CONF_API_SECRET: "secret",
}
OLD_DATA = {
    CONF_API_TOKEN: "old-token",
    CONF_API_SECRET: "old-secret",
    CONF_DEVICE_ID: DEVICE_ID,
}


async def test_user_flow_creates_device_entry(hass) -> None:
    """User setup validates status and creates a normalized unique entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    status_mock = AsyncMock(return_value=DeviceStatus(charging=False))
    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_devices",
            AsyncMock(return_value=[MindClipDevice(DEVICE_ID, "Pocket notes")]),
        ),
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            status_mock,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: " token ",
                CONF_API_SECRET: " secret ",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MindClip ST-001"
    assert result["data"] == {
        CONF_API_TOKEN: "token",
        CONF_API_SECRET: "secret",
        CONF_DEVICE_ID: DEVICE_ID,
    }
    assert result["result"].unique_id == DEVICE_ID
    status_mock.assert_awaited_once_with(DEVICE_ID)


async def test_user_flow_rejects_invalid_auth(hass) -> None:
    """Invalid credentials leave the form open with a safe error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.mindclip.config_flow.MindClipApi.async_get_devices",
        AsyncMock(side_effect=MindClipAuthError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_rejects_duplicate_device(hass) -> None:
    """One physical MindClip cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        title="MindClip ST-001",
        data=OLD_DATA,
        unique_id=DEVICE_ID,
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_devices",
            AsyncMock(return_value=[MindClipDevice(DEVICE_ID, "Pocket notes")]),
        ),
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=False)),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CREDENTIALS
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_selects_from_multiple_devices(hass) -> None:
    """Multiple discovered MindClips are presented for selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    devices = [
        MindClipDevice(DEVICE_ID, "Pocket notes"),
        MindClipDevice("MINDCLIP-TEST-002", "Office notes"),
    ]
    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_devices",
            AsyncMock(return_value=devices),
        ),
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=False)),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CREDENTIALS
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE_ID: "MINDCLIP-TEST-002"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == "MINDCLIP-TEST-002"


async def test_user_flow_falls_back_to_manual_device_id(hass) -> None:
    """An account with no discovered MindClip can enter its device ID manually."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_devices",
            AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=False)),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CREDENTIALS
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE_ID: " mindclip-test-001 "}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID


async def test_reauth_updates_only_existing_entry(hass) -> None:
    """Reauthentication validates replacement credentials and reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MindClip ST-001",
        data=OLD_DATA,
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": DEVICE_ID,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=False)),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "new-token", CONF_API_SECRET: "new-secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_API_TOKEN: "new-token",
        CONF_API_SECRET: "new-secret",
        CONF_DEVICE_ID: DEVICE_ID,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reconfigure_updates_existing_entry(hass) -> None:
    """Reconfigure validates updates without creating another entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MindClip ST-001",
        data=OLD_DATA,
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "custom_components.mindclip.config_flow.MindClipApi.async_get_device_status",
            AsyncMock(return_value=DeviceStatus(charging=True)),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "updated-token",
                CONF_API_SECRET: "updated-secret",
                CONF_DEVICE_ID: DEVICE_ID.lower(),
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_TOKEN] == "updated-token"
    assert entry.data[CONF_DEVICE_ID] == DEVICE_ID
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
