"""Public exception types for fresh-read failures in the XKC-KL200 library."""


class XKC_KL200_ReadError(Exception):
    """Base exception for failures while reading a fresh sensor measurement."""


class XKC_KL200_TimeoutError(XKC_KL200_ReadError):
    """Raised when the sensor does not return a full measurement frame in time."""


class XKC_KL200_ResponseError(XKC_KL200_ReadError):
    """Raised when the sensor returns a malformed or unexpected measurement frame."""
