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


def default_serial_factory(port: str, baudrate: int, timeout: float) -> SerialPort:
    """Create the default pyserial-backed serial connection."""
    return cast(
        SerialPort,
        serial.Serial(port=port, baudrate=baudrate, timeout=timeout),
    )


class SerialManager:
    """Thin wrapper around the serial transport used by the sensor."""

    def __init__(
        self,
        config: SensorConfig,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        """Open the serial connection using the configured parameters."""
        factory = serial_factory or default_serial_factory
        self._serial = factory(config.port, config.baudrate, config.timeout)

    @property
    def is_open(self) -> bool:
        """Return True when the serial port is still open."""
        return bool(self._serial.is_open)

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial.is_open:
            self._serial.close()

    def set_baudrate(self, baudrate: int) -> None:
        """Update the serial port baud rate in place."""
        self._serial.baudrate = baudrate

    def write_frame(self, frame: bytes) -> None:
        """Write a full protocol frame and flush it immediately."""
        self._serial.write(frame)
        self._serial.flush()

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
