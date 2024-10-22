# from newssurvey.config import REQUEST_HEADERS
from newssurvey.util.threading_ import CooldownLock

# _REQUEST_COOLDOWN = 5  # Applicable to default Mozilla Firefox user agent. Values ≤2 led to HTTP 429 errors.
_REQUEST_COOLDOWN = 3  # Exceeds observed value of 2 for AhrefsBot in robots.txt as of 2024-10-22.
REQUEST_HEADERS = {"User-Agent": "AhrefsBot"}  # Observed to be approved in robots.txt as of 2024-10-22.
SOURCE_SITE_NAME = "PhysOrg"
SOURCE_TYPE = "science"
UNBLOCK_MESSAGE = "Consider visiting https://phys.org/ in a web browser to test and unblock it as relevant."

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)
