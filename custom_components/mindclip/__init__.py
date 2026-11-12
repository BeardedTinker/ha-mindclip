"""MindClip integration."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MindClipApi
from .calendar_sync import MindClipCalendarSync
from .const import CONF_API_SECRET, CONF_API_TOKEN, CONF_DEVICE_ID, DOMAIN
from .coordinator import MindClipCoordinator
from .frontend import async_register_frontend
from .services import async_setup_services

PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR, Platform.TODO, Platform.EVENT)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MindClipRuntimeData:
    """Runtime data for a MindClip config entry."""

    api: MindClipApi
    coordinator: MindClipCoordinator


type MindClipConfigEntry = ConfigEntry[MindClipRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up response-only MindClip actions."""
    async_setup_services(hass)
    return True


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
    calendar_sync = MindClipCalendarSync(hass, entry.options, coordinator)
    entry.runtime_data = MindClipRuntimeData(api=api, coordinator=coordinator)
    try:
        await async_register_frontend(hass)
    except Exception:
        _LOGGER.exception("Unable to register the bundled MindClip dashboard card")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    calendar_sync.async_start()
    entry.async_on_unload(calendar_sync.async_stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MindClipConfigEntry) -> bool:
    """Unload a MindClip config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
