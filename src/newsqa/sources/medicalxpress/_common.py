from newsqa.util.threading_ import CooldownLock

SOURCE_SITE = "medicalxpress.com"
SOURCE_SITE_NAME = "MedicalXpress"
SOURCE_TYPE = "medical"

request_cooldown_lock = CooldownLock(cooldown=0.5, name=SOURCE_SITE_NAME)
