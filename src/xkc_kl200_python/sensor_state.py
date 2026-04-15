from dataclasses import dataclass

from .constants import DEFAULT_SENSOR_ADDRESS


@dataclass
class SensorState:
    """Mutable runtime state cached by the sensor wrapper."""

    distance_mm: int = 0
    last_received_distance_mm: int = 0
    available: bool = False
    auto_upload_enabled: bool = False
    address: int = DEFAULT_SENSOR_ADDRESS

    def mark_measurement(self, distance_mm: int, address: int) -> None:
        """Store a newly received distance measurement."""
        self.distance_mm = distance_mm
        self.last_received_distance_mm = distance_mm
        self.available = True
        self.address = address

    def consume_distance(self) -> int:
        """Return the current distance and clear the availability flag."""
        self.available = False
        return self.distance_mm
