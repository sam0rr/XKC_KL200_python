"""Configuration validation for XKC-KL200 sensor instances."""

from dataclasses import dataclass

from .constants import (
    BAUD_RATE_TO_CODE,
    DEFAULT_SENSOR_ADDRESS,
    MAX_ADDRESS,
    MIN_ADDRESS,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SensorConfig:
    """Serial connection settings for an XKC-KL200 sensor instance."""

    port: str
    baudrate: int = 9600
    timeout: float = 1.0
    address: int = DEFAULT_SENSOR_ADDRESS
    startup_delay_s: float = 0.1

    def __post_init__(self) -> None:
        """Validate configuration values at construction time."""
        if not self.port:
            raise ValueError("port must be a non-empty string")
        if self.baudrate not in BAUD_RATE_TO_CODE:
            raise ValueError(f"Unsupported baudrate: {self.baudrate}")
        if not (
            MIN_ADDRESS <= self.address <= MAX_ADDRESS
            or self.address == DEFAULT_SENSOR_ADDRESS
        ):
            raise ValueError(
                f"address must be between {MIN_ADDRESS:#06x} and 0xffff inclusive"
            )
        if self.timeout < 0:
            raise ValueError("timeout must be >= 0")
        if self.startup_delay_s < 0:
            raise ValueError("startup_delay_s must be >= 0")
