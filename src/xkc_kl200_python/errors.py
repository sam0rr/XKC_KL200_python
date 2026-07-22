"""Public exception types for fresh-read failures in the XKC-KL200 library."""


class XkcKl200ReadError(Exception):
    """Base exception for failures while reading a fresh sensor measurement."""


class XkcKl200TimeoutError(XkcKl200ReadError):
    """Raised when the sensor does not return a full measurement frame in time."""


class XkcKl200ResponseError(XkcKl200ReadError):
    """Raised when the sensor returns a malformed or unexpected measurement frame."""
