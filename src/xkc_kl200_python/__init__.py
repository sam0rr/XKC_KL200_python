"""Public package exports for the simplified XKC-KL200 library."""

from .config import SensorConfig
from .constants import (
    CommunicationMode,
    LedMode,
    RelayMode,
    XkcKl200Status,
)
from .errors import (
    XkcKl200ReadError,
    XkcKl200ResponseError,
    XkcKl200TimeoutError,
)
from .sensor import XkcKl200

# Re-export the supported public API from one stable package entrypoint.
__all__ = [
    "CommunicationMode",
    "LedMode",
    "RelayMode",
    "SensorConfig",
    "XkcKl200",
    "XkcKl200ReadError",
    "XkcKl200ResponseError",
    "XkcKl200Status",
    "XkcKl200TimeoutError",
]
