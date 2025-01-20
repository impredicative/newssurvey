# from newssurvey.config import REQUEST_HEADERS
from newssurvey.util.threading_ import CooldownLock

# _REQUEST_COOLDOWN = 5  # Applicable to default Mozilla Firefox user agent. Values ≤4 led to HTTP 422 and 429 errors, also requiring subsequent "press-and-hold" "security verification" via a web browser.
_REQUEST_COOLDOWN = 4  # Exceeds observed value of 2 for AhrefsBot in robots.txt as of 2024-10-22. Value of 3 led to HTTP 429 error.
REQUEST_HEADERS = {"User-Agent": "AhrefsBot"}  # Observed to be approved in robots.txt as of 2024-10-22.
SOURCE_SITE_NAME = "MedicalXpress"
SOURCE_TYPE = "medical"
UNBLOCK_MESSAGE = "Consider visiting https://medicalxpress.com/ in a web browser to test and unblock it as relevant."

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)
