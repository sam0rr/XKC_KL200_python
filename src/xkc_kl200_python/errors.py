"""Public exception types for fresh-read failures in the XKC-KL200 library."""


# Provide one shared base class for measurement-read failures.
class XKC_KL200_ReadError(Exception):
    """Base exception for failures while reading a fresh sensor measurement."""


# Represent timeout failures while waiting for a complete measurement frame.
class XKC_KL200_TimeoutError(XKC_KL200_ReadError):
    """Raised when the sensor does not return a full measurement frame in time."""


# Represent malformed or otherwise unexpected measurement-response frames.
class XKC_KL200_ResponseError(XKC_KL200_ReadError):
    """Raised when the sensor returns a malformed or unexpected measurement frame."""
