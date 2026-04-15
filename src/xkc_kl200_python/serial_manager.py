import time
from typing import Callable, Protocol, cast

import serial

from .config import SensorConfig


class SerialPort(Protocol):
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
    return cast(
        SerialPort,
        serial.Serial(port=port, baudrate=baudrate, timeout=timeout),
    )


class SerialManager:
    def __init__(
        self,
        config: SensorConfig,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        factory = serial_factory or default_serial_factory
        self._serial = factory(config.port, config.baudrate, config.timeout)

    @property
    def bytes_available(self) -> int:
        return int(self._serial.in_waiting)

    @property
    def is_open(self) -> bool:
        return bool(self._serial.is_open)

    def close(self) -> None:
        if self._serial.is_open:
            self._serial.close()

    def set_baudrate(self, baudrate: int) -> None:
        self._serial.baudrate = baudrate

    def write_frame(self, frame: bytes) -> None:
        self._serial.write(frame)
        self._serial.flush()

    def discard(self, count: int) -> None:
        if count > 0:
            self._serial.read(count)

    def read_exact(self, size: int, timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        buffer = bytearray()

        while len(buffer) < size:
            remaining = size - len(buffer)
            waiting = self.bytes_available
            chunk_size = remaining if waiting == 0 else min(remaining, waiting)
            chunk = self._serial.read(chunk_size)
            if chunk:
                buffer.extend(chunk)
                continue

            if time.monotonic() >= deadline:
                return None

            time.sleep(0.001)

        return bytes(buffer)
