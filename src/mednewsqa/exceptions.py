class Error(Exception):
    """Base error."""


class RequestError(Error):
    """Malformed HTTP request error"""
