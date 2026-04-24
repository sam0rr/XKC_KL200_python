"""Public package exports for the simplified XKC-KL200 library."""

from .config import SensorConfig
from .constants import (
    CommunicationMode,
    LedMode,
    RelayMode,
    XKC_KL200_Status,
)
from .errors import (
    XKC_KL200_ReadError,
    XKC_KL200_ResponseError,
    XKC_KL200_TimeoutError,
)
from .sensor import XKC_KL200

# Re-export the supported public API from one stable package entrypoint.
__all__ = [
    "XKC_KL200",
    "SensorConfig",
    "XKC_KL200_Status",
    "XKC_KL200_ReadError",
    "XKC_KL200_TimeoutError",
    "XKC_KL200_ResponseError",
    "LedMode",
    "RelayMode",
    "CommunicationMode",
]
