"""Constants for the MindClip integration."""

from datetime import timedelta

DOMAIN = "mindclip"

CONF_API_TOKEN = "api_token"
CONF_API_SECRET = "api_secret"
CONF_DEVICE_ID = "device_id"

API_BASE_URL = "https://api.switch-bot.com/v1.1"
API_REQUEST_TIMEOUT = 10
API_PAGE_SIZE = 100
API_MAX_PAGES = 10
MAX_STATE_LENGTH = 255
SUMMARY_ATTRIBUTE_LIMIT = MAX_STATE_LENGTH

UPDATE_INTERVAL = timedelta(minutes=30)
