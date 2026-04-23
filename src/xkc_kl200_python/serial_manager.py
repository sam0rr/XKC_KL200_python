"""Small serial transport wrapper used by the sensor implementation."""

import time
from typing import Callable, Protocol, cast

import serial

from .config import SensorConfig


class SerialPort(Protocol):
    """Minimal serial-port interface required by the library."""

    baudrate: int
    is_open: bool

    @property
    def in_waiting(self) -> int: ...

    def read(self, size: int = 1) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


SerialFactory = Callable[[str, int, float], SerialPort]


# Create the default pyserial-backed port for production use.
def default_serial_factory(port: str, baudrate: int, timeout: float) -> SerialPort:
    """Create the default pyserial-backed serial connection."""
    return cast(
        SerialPort,
        serial.Serial(port=port, baudrate=baudrate, timeout=timeout),
    )


# Keep transport details separate from the higher-level sensor protocol code.
class SerialManager:
    """Thin wrapper around the serial transport used by the sensor."""

    # Open the underlying serial port with the validated connection settings.
    def __init__(
        self,
        config: SensorConfig,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        """Open the serial connection using the configured parameters."""
        factory = serial_factory or default_serial_factory
        self._serial = factory(config.port, config.baudrate, config.timeout)

    # Expose whether the underlying port still considers itself open.
    @property
    def is_open(self) -> bool:
        """Return True when the serial port is still open."""
        return bool(self._serial.is_open)

    # Close the port idempotently so callers can clean up safely.
    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial.is_open:
            self._serial.close()

    # Update the live port baud rate after a successful protocol change.
    def set_baudrate(self, baudrate: int) -> None:
        """Update the serial port baud rate in place."""
        self._serial.baudrate = baudrate

    # Send one whole protocol frame and flush it immediately.
    def write_frame(self, frame: bytes) -> None:
        """Write a full protocol frame and flush it immediately."""
        self._serial.write(frame)
        self._serial.flush()

    # Read exactly the requested byte count without keeping hidden buffer state.
    def read_exact(self, size: int, timeout: float) -> bytes | None:
        """Read exactly ``size`` bytes or return ``None`` on timeout."""
        deadline = time.monotonic() + timeout
        buffer = bytearray()

        while len(buffer) < size:
            remaining = size - len(buffer)
            waiting = int(self._serial.in_waiting)
            chunk_size = remaining if waiting == 0 else min(remaining, waiting)
            chunk = self._serial.read(chunk_size)
            if chunk:
                buffer.extend(chunk)
                continue

            if time.monotonic() >= deadline:
                return None

            time.sleep(0.001)

        return bytes(buffer)
