# from newssurvey.config import REQUEST_HEADERS  # Not used due to longer cooldown period required for it.
from newssurvey.util.threading_ import CooldownLock

# _REQUEST_COOLDOWN = 3  # Applicable to default Mozilla Firefox user agent.
_REQUEST_COOLDOWN = 1.1  # Applicable to Yahoo! Slurp user agent.
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)"}
# SOURCE_SITE_URL = "medicalxpress.com"
SOURCE_SITE_NAME = "MedicalXpress"
SOURCE_TYPE = "medical"

request_cooldown_lock = CooldownLock(cooldown=_REQUEST_COOLDOWN, name=SOURCE_SITE_NAME)  # Note: 2s or lower values of cooldown led to HTTP 429 error.
