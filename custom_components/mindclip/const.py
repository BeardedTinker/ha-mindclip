"""Constants for the MindClip integration."""

from datetime import timedelta

DOMAIN = "mindclip"

CONF_API_TOKEN = "api_token"
CONF_API_SECRET = "api_secret"
CONF_DEVICE_ID = "device_id"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_EVENT_DURATION_MINUTES = "event_duration_minutes"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_LIMIT = "limit"
ATTR_RECORDING_ID = "recording_id"

SERVICE_LIST_RECORDINGS = "list_recordings"
SERVICE_GET_RECORDING = "get_recording"
SERVICE_GET_TRANSCRIPT = "get_transcript"
SERVICE_GET_SUMMARY = "get_summary"

DEFAULT_EVENT_DURATION_MINUTES = 30

API_BASE_URL = "https://api.switch-bot.com/v1.1"
API_REQUEST_TIMEOUT = 10
API_PAGE_SIZE = 100
API_MAX_PAGES = 10
MAX_STATE_LENGTH = 255
SUMMARY_ATTRIBUTE_LIMIT = MAX_STATE_LENGTH
ACTION_MAX_TEXT_LENGTH = 1_000_000
ACTION_MAX_LIST_ITEMS = 1_000
ACTION_MAX_COLOR_LENGTH = 32
CARD_DEFAULT_RECORDING_LIMIT = 10
CARD_MAX_RECORDING_LIMIT = 50

UPDATE_INTERVAL = timedelta(minutes=30)
