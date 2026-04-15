from collections import deque
from typing import Deque

import pytest


class FakeSerial:
    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.written_frames: list[bytes] = []
        self._chunks: Deque[bytes] = deque()

    @property
    def in_waiting(self) -> int:
        return sum(len(chunk) for chunk in self._chunks)

    def queue_read(self, data: bytes) -> None:
        self._chunks.append(data)

    def read(self, size: int = 1) -> bytes:
        if size <= 0 or not self._chunks:
            return b""

        chunk = self._chunks.popleft()
        if len(chunk) > size:
            self._chunks.appendleft(chunk[size:])
            return bytes(chunk[:size])
        return bytes(chunk)

    def write(self, data: bytes) -> int:
        self.written_frames.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.is_open = False


class FakeSerialFactory:
    def __init__(self) -> None:
        self.holder: dict[str, FakeSerial] = {}

    def __call__(self, port: str, baudrate: int, timeout: float) -> FakeSerial:
        fake_serial = FakeSerial(port=port, baudrate=baudrate, timeout=timeout)
        self.holder["serial"] = fake_serial
        return fake_serial


@pytest.fixture
def serial_factory() -> FakeSerialFactory:
    return FakeSerialFactory()
