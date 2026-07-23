"""Public enums and status values for the XKC-KL200 UART interface."""

from enum import IntEnum

__all__ = [
    "CommunicationMode",
    "LedMode",
    "RelayMode",
    "XkcKl200Status",
]


class XkcKl200Status(IntEnum):
    """Protocol-level status codes returned by the library API."""

    SUCCESS = 0
    INVALID_PARAMETER = 1
    TIMEOUT = 2
    CHECKSUM_ERROR = 3
    RESPONSE_ERROR = 4


class LedMode(IntEnum):
    """Supported LED behavior modes."""

    ON_WHEN_DETECTED = 0
    OFF_WHEN_DETECTED = 1
    ALWAYS_OFF = 2
    ALWAYS_ON = 3


class RelayMode(IntEnum):
    """Supported relay output modes."""

    ACTIVE_WHEN_DETECTED = 0
    INACTIVE_WHEN_DETECTED = 1


class CommunicationMode(IntEnum):
    """High-level communication operating modes."""

    RELAY = 0
    UART = 1
