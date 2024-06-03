from newsqa.util.threading_ import CooldownLock

SOURCE_SITE = "medicalxpress.com"
SOURCE_SITE_NAME = "MedicalXpress"
SOURCE_TYPE = "medical"

request_cooldown_lock = CooldownLock(cooldown=3, name=SOURCE_SITE_NAME)  # Note: 2s or lower values of cooldown led to HTTP 429 error.
