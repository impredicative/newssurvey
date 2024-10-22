from newssurvey.config import REQUEST_HEADERS
from newssurvey.util.threading_ import CooldownLock

_REQUEST_COOLDOWN = 4  # Applicable to default Mozilla Firefox user agent. Values ≤3 led to HTTP 422 and 429 errors, also requiring subsequent "press-and-hold" "security verification" via a web browser.
REQUEST_HEADERS = REQUEST_HEADERS.copy()
SOURCE_SITE_NAME = "MedicalXpress"
SOURCE_TYPE = "medical"

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)
