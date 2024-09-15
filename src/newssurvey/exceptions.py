class Error(Exception):
    """Base error."""


class EnvError(Error, EnvironmentError):
    """Environment variable availability error."""


class InputError(Error, ValueError):
    """Input validity error."""


class ModelOutputError(Error):
    """Model output error."""


class LanguageModelOutputError(ModelOutputError):
    """Language model output error."""


class LanguageModelOutputConvergenceError(LanguageModelOutputError):
    """Language model output convergence error."""


class LanguageModelOutputLimitError(LanguageModelOutputError):
    """Language model output limit error."""


class LanguageModelOutputRejectionError(LanguageModelOutputError):
    """Language model output rejection error."""


class LanguageModelOutputStructureError(LanguageModelOutputError):
    """Language model output structure error."""


class RequestError(Error):
    """Malformed HTTP request error"""


class SourceInsufficiencyError(Error):
    """Source data insufficiency error."""
