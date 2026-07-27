"""Shared serial test doubles and fixtures."""

from collections import deque

import pytest


class FakeSerial:
    """In-memory implementation of the serial interface used by tests."""

    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        """Initialize a fake serial port with no queued input."""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.written_frames: list[bytes] = []
        self.reset_input_count = 0
        self.reset_output_count = 0
        self._chunks: deque[bytes] = deque()

    @property
    def in_waiting(self) -> int:
        """Return the number of queued bytes available to read."""
        return sum(len(chunk) for chunk in self._chunks)

    def queue_read(self, data: bytes) -> None:
        """Queue one chunk of bytes for a future read."""
        self._chunks.append(data)

    def read(self, size: int = 1) -> bytes:
        """Read up to the requested number of queued bytes."""
        if size <= 0 or not self._chunks:
            return b""

        chunk = self._chunks.popleft()
        if len(chunk) > size:
            self._chunks.appendleft(chunk[size:])
            return bytes(chunk[:size])
        return bytes(chunk)

    def write(self, data: bytes) -> int:
        """Record written bytes and report their length."""
        self.written_frames.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        """Accept flush requests without additional behavior."""
        return

    def reset_input_buffer(self) -> None:
        """Record an input-buffer reset request."""
        self.reset_input_count += 1

    def reset_output_buffer(self) -> None:
        """Record an output-buffer reset request."""
        self.reset_output_count += 1

    def close(self) -> None:
        """Mark the fake serial port as closed."""
        self.is_open = False


class FakeSerialFactory:
    """Create fake serial ports and retain the most recent instance."""

    def __init__(self) -> None:
        """Initialize an empty serial-instance holder."""
        self.holder: dict[str, FakeSerial] = {}

    def __call__(self, port: str, baudrate: int, timeout: float) -> FakeSerial:
        """Create and retain a fake serial port."""
        fake_serial = FakeSerial(port=port, baudrate=baudrate, timeout=timeout)
        self.holder["serial"] = fake_serial
        return fake_serial


@pytest.fixture
def serial_factory() -> FakeSerialFactory:
    """Provide a fresh fake serial factory."""
    return FakeSerialFactory()
