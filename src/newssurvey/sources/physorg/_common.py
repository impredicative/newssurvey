from newssurvey.config import REQUEST_HEADERS
from newssurvey.util.threading_ import CooldownLock

_REQUEST_COOLDOWN = 3  # Applicable to default Mozilla Firefox user agent.
REQUEST_HEADERS = REQUEST_HEADERS.copy()
SOURCE_SITE_NAME = "PhysOrg"
SOURCE_TYPE = "science"

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)  # Note: 2s or lower values of cooldown are expected to lead to an HTTP 429 error.
