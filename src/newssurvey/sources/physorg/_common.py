from newssurvey.config import REQUEST_HEADERS
from newssurvey.util.threading_ import CooldownLock

_REQUEST_COOLDOWN = 5  # Applicable to default Mozilla Firefox user agent. Values ≤2 led to HTTP 429 errors.
REQUEST_HEADERS = REQUEST_HEADERS.copy()
SOURCE_SITE_NAME = "PhysOrg"
SOURCE_TYPE = "science"
UNBLOCK_MESSAGE = "Consider visiting https://phys.org/ in a web browser to test and unblock it as relevant."

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)
