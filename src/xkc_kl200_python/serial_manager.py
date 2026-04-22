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
        self._buffer = bytearray()

    @property
    def bytes_available(self) -> int:
        """Return the number of bytes currently buffered by the port and local buffer."""
        return int(self._serial.in_waiting) + len(self._buffer)

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

    def discard(self, count: int) -> None:
        """Discard up to ``count`` bytes from the serial buffer."""
        if count <= 0:
            return

        # First discard from local buffer
        from_buffer = min(count, len(self._buffer))
        if from_buffer > 0:
            del self._buffer[:from_buffer]
            count -= from_buffer

        # Then from serial port
        if count > 0:
            self._serial.read(count)

    def read_exact(self, size: int, timeout: float) -> bytes | None:
        """Read exactly ``size`` bytes or return ``None`` on timeout."""
        deadline = time.monotonic() + timeout

        while len(self._buffer) < size:
            remaining = size - len(self._buffer)
            waiting = int(self._serial.in_waiting)
            chunk_size = max(remaining, waiting)
            chunk = self._serial.read(chunk_size)
            if chunk:
                self._buffer.extend(chunk)
                if len(self._buffer) >= size:
                    break
                continue

            if time.monotonic() >= deadline:
                return None

            time.sleep(0.001)

        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    def peek(self, size: int) -> bytes:
        """Return up to ``size`` bytes from the buffer without consuming them."""
        waiting = int(self._serial.in_waiting)
        if waiting > 0:
            chunk = self._serial.read(waiting)
            if chunk:
                self._buffer.extend(chunk)
        return bytes(self._buffer[:size])
