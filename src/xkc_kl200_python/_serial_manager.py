"""Small serial transport wrapper used by the sensor implementation."""

import time
from collections.abc import Callable
from typing import Protocol

import serial

from ._protocol import (
    COMMAND_HEADER,
    FRAME_LENGTH,
    SYSTEM_HEADER,
    calculate_checksum,
)
from .config import SensorConfig
from .constants import XkcKl200Status


class SerialPort(Protocol):
    """Minimal serial-port interface required by the library."""

    baudrate: int
    is_open: bool

    @property
    def in_waiting(self) -> int:
        """Return the number of input bytes ready to read."""
        ...

    def read(self, size: int = 1) -> bytes:
        """Read up to the requested number of bytes."""
        ...

    def write(self, data: bytes) -> int | None:
        """Write bytes and return the number accepted when reported."""
        ...

    def flush(self) -> None:
        """Flush buffered output to the serial device."""
        ...

    def reset_input_buffer(self) -> None:
        """Discard pending input bytes."""
        ...

    def reset_output_buffer(self) -> None:
        """Discard pending output bytes."""
        ...

    def close(self) -> None:
        """Close the serial connection."""
        ...


SerialFactory = Callable[[str, int, float], SerialPort]


def default_serial_factory(port: str, baudrate: int, timeout: float) -> SerialPort:
    """Create the default pyserial-backed serial connection."""
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
        exclusive=True,
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

    def reset_input_buffer(self) -> None:
        """Clear buffered incoming bytes."""
        self._buffer.clear()
        self._serial.reset_input_buffer()

    def reset_output_buffer(self) -> None:
        """Clear buffered outgoing bytes."""
        self._serial.reset_output_buffer()

    def reset_buffers(self) -> None:
        """Clear incoming and outgoing serial buffers."""
        self.reset_input_buffer()
        self.reset_output_buffer()

    def write_frame(self, frame: bytes) -> None:
        """Write a full protocol frame and flush it immediately."""
        self._serial.write(frame)
        self._serial.flush()

    def read_frame(
        self,
        *,
        timeout: float,
        expected_header: int | None = None,
        expected_command: int | None = None,
        allow_header_mismatch_skip: bool = False,
    ) -> tuple[bytes | None, XkcKl200Status]:
        """Read one valid frame or return the protocol-level failure status."""
        deadline = time.monotonic() + timeout
        buffered_bytes_at_deadline: int | None = None
        deferred_error: XkcKl200Status | None = None

        while True:
            frame, frame_status = self._scan_buffer(
                allow_header_mismatch_skip=allow_header_mismatch_skip,
                expected_header=expected_header,
                expected_command=expected_command,
            )
            if frame is not None:
                return frame, XkcKl200Status.SUCCESS
            deferred_error = self._prefer_protocol_error(
                current=deferred_error,
                candidate=frame_status,
            )

            if time.monotonic() >= deadline:
                # Snapshot how many bytes were already queued when the timeout
                # expired. We may finish parsing those bytes, but we must not
                # let newly arriving data extend the read indefinitely.
                if buffered_bytes_at_deadline is None:
                    buffered_bytes_at_deadline = int(self._serial.in_waiting)
                if buffered_bytes_at_deadline > 0:
                    drained = self._read_from_serial(limit=buffered_bytes_at_deadline)
                    buffered_bytes_at_deadline -= drained
                    if drained > 0:
                        continue
                self._buffer.clear()
                if deferred_error is not None:
                    return None, deferred_error
                return None, XkcKl200Status.TIMEOUT

            if self._read_from_serial() > 0:
                continue

            time.sleep(0.001)

    def _scan_buffer(
        self,
        *,
        allow_header_mismatch_skip: bool,
        expected_header: int | None,
        expected_command: int | None,
    ) -> tuple[bytes | None, XkcKl200Status | None]:
        """Scan buffered bytes until a frame is found or parsing stalls."""
        deferred_error: XkcKl200Status | None = None

        while True:
            frame, frame_status, consumed_data = self._extract_frame(
                allow_header_mismatch_skip=allow_header_mismatch_skip,
                expected_header=expected_header,
                expected_command=expected_command,
            )
            if frame is not None:
                return frame, None
            deferred_error = self._prefer_protocol_error(
                current=deferred_error,
                candidate=frame_status,
            )

            if not consumed_data:
                return None, deferred_error

    def _read_from_serial(self, *, limit: int | None = None) -> int:
        """Read available serial bytes into the internal buffer without blocking."""
        waiting = int(self._serial.in_waiting)
        if waiting <= 0:
            return 0

        chunk_size = waiting if limit is None else min(waiting, limit)
        chunk = self._serial.read(chunk_size)
        if not chunk:
            return 0

        self._buffer.extend(chunk)
        return len(chunk)

    def _extract_frame(
        self,
        *,
        allow_header_mismatch_skip: bool,
        expected_header: int | None,
        expected_command: int | None,
    ) -> tuple[bytes | None, XkcKl200Status | None, bool]:
        """Return the next valid frame, one protocol error, and whether data was consumed."""
        if not self._buffer:
            return None, None, False

        consumed_data, prefix_status = self._consume_misaligned_prefix()
        if consumed_data:
            return None, prefix_status, True

        if len(self._buffer) < 3:
            return None, None, False

        frame_length = self._buffer[2]
        if frame_length != FRAME_LENGTH:
            del self._buffer[0]
            if len(self._buffer) >= FRAME_LENGTH - 1:
                return None, XkcKl200Status.RESPONSE_ERROR, True
            return None, None, True

        if len(self._buffer) < FRAME_LENGTH:
            return None, None, False

        candidate = bytes(self._buffer[:FRAME_LENGTH])
        if candidate[-1] != calculate_checksum(candidate[:-1]):
            del self._buffer[0]
            return None, XkcKl200Status.CHECKSUM_ERROR, True

        if expected_command is not None and candidate[1] != expected_command:
            return self._consume_mismatched_candidate(error_status=None)

        if expected_header is not None and candidate[0] != expected_header:
            return self._consume_mismatched_candidate(
                error_status=(
                    None
                    if allow_header_mismatch_skip
                    else XkcKl200Status.RESPONSE_ERROR
                )
            )

        del self._buffer[:FRAME_LENGTH]
        return candidate, None, True

    def _consume_misaligned_prefix(
        self,
    ) -> tuple[bool, XkcKl200Status | None]:
        """Discard bytes before a protocol header and report malformed data."""
        header_index = self._find_next_header()
        if header_index == 0:
            return False, None

        malformed_frame = len(self._buffer) >= FRAME_LENGTH
        if header_index < 0:
            discard_count = 1 if malformed_frame else len(self._buffer)
        else:
            discard_count = header_index

        del self._buffer[:discard_count]
        status = XkcKl200Status.RESPONSE_ERROR if malformed_frame else None
        return True, status

    @staticmethod
    def _prefer_protocol_error(
        *,
        current: XkcKl200Status | None,
        candidate: XkcKl200Status | None,
    ) -> XkcKl200Status | None:
        """Keep the most specific protocol error observed while scanning."""
        if candidate == XkcKl200Status.CHECKSUM_ERROR:
            return XkcKl200Status.CHECKSUM_ERROR
        if (
            candidate == XkcKl200Status.RESPONSE_ERROR
            and current != XkcKl200Status.CHECKSUM_ERROR
        ):
            return XkcKl200Status.RESPONSE_ERROR
        return current

    def _consume_mismatched_candidate(
        self,
        *,
        error_status: XkcKl200Status | None,
    ) -> tuple[None, XkcKl200Status | None, bool]:
        """Resynchronize within a checksum-valid mismatched candidate."""
        overlap_header_index = self._find_next_header(start=1, stop=FRAME_LENGTH)
        if overlap_header_index < 0:
            del self._buffer[:FRAME_LENGTH]
        else:
            del self._buffer[:overlap_header_index]
        return None, error_status, True

    def _find_next_header(self, *, start: int = 0, stop: int | None = None) -> int:
        """Return the index of the next protocol header byte or ``-1``."""
        end_index = len(self._buffer) if stop is None else min(stop, len(self._buffer))
        for index in range(start, end_index):
            byte = self._buffer[index]
            if byte in (COMMAND_HEADER, SYSTEM_HEADER):
                return index
        return -1
