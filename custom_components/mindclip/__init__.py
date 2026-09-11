"""MindClip integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MindClipApi
from .const import CONF_API_SECRET, CONF_API_TOKEN, CONF_DEVICE_ID
from .coordinator import MindClipCoordinator

PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR, Platform.TODO)


@dataclass(slots=True)
class MindClipRuntimeData:
    """Runtime data for a MindClip config entry."""

    api: MindClipApi
    coordinator: MindClipCoordinator


type MindClipConfigEntry = ConfigEntry[MindClipRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: MindClipConfigEntry) -> bool:
    """Set up MindClip from a config entry."""
    api = MindClipApi(
        async_get_clientsession(hass),
        entry.data[CONF_API_TOKEN],
        entry.data[CONF_API_SECRET],
    )
    coordinator = MindClipCoordinator(
        hass,
        entry,
        api,
        entry.data[CONF_DEVICE_ID],
    )
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MindClipRuntimeData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MindClipConfigEntry) -> bool:
    """Unload a MindClip config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
