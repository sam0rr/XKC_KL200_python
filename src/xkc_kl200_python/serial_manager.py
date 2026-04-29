"""Small serial transport wrapper used by the sensor implementation."""

import time
from typing import Callable, Protocol, cast

import serial

from .config import SensorConfig
from .constants import COMMAND_HEADER, FRAME_LENGTH, SYSTEM_HEADER, XKC_KL200_Status
from .utils import calculate_checksum


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
        self._buffer = bytearray()

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

    # Read one complete protocol frame while resynchronizing around junk bytes.
    def read_frame(
        self,
        *,
        timeout: float,
        expected_header: int | None = None,
        expected_command: int | None = None,
        allow_header_mismatch_skip: bool = False,
    ) -> tuple[bytes | None, XKC_KL200_Status]:
        """Read one valid frame or return the protocol-level failure status."""
        deadline = time.monotonic() + timeout
        buffered_bytes_at_deadline: int | None = None
        deferred_error: XKC_KL200_Status | None = None

        while True:
            frame, frame_status = self._scan_buffer(
                allow_header_mismatch_skip=allow_header_mismatch_skip,
                expected_header=expected_header,
                expected_command=expected_command,
            )
            if frame is not None:
                return frame, XKC_KL200_Status.SUCCESS
            if frame_status == XKC_KL200_Status.CHECKSUM_ERROR:
                deferred_error = XKC_KL200_Status.CHECKSUM_ERROR
            elif (
                frame_status == XKC_KL200_Status.RESPONSE_ERROR
                and deferred_error != XKC_KL200_Status.CHECKSUM_ERROR
            ):
                deferred_error = XKC_KL200_Status.RESPONSE_ERROR

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
                return None, XKC_KL200_Status.TIMEOUT

            if self._read_from_serial() > 0:
                continue

            time.sleep(0.001)

    # Keep parsing buffered bytes until no further progress is possible.
    def _scan_buffer(
        self,
        *,
        allow_header_mismatch_skip: bool,
        expected_header: int | None,
        expected_command: int | None,
    ) -> tuple[bytes | None, XKC_KL200_Status | None]:
        """Scan buffered bytes until a frame is found or parsing stalls."""
        deferred_error: XKC_KL200_Status | None = None

        while True:
            frame, frame_status, consumed_data = self._extract_frame(
                allow_header_mismatch_skip=allow_header_mismatch_skip,
                expected_header=expected_header,
                expected_command=expected_command,
            )
            if frame is not None:
                return frame, None
            if frame_status == XKC_KL200_Status.CHECKSUM_ERROR:
                deferred_error = XKC_KL200_Status.CHECKSUM_ERROR
            elif (
                frame_status == XKC_KL200_Status.RESPONSE_ERROR
                and deferred_error != XKC_KL200_Status.CHECKSUM_ERROR
            ):
                deferred_error = XKC_KL200_Status.RESPONSE_ERROR

            if not consumed_data:
                return None, deferred_error

    # Read whatever the serial backend currently has ready into the local buffer.
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

    # Scan the local buffer for one frame and report whether progress was made.
    def _extract_frame(
        self,
        *,
        allow_header_mismatch_skip: bool,
        expected_header: int | None,
        expected_command: int | None,
    ) -> tuple[bytes | None, XKC_KL200_Status | None, bool]:
        """Return the next valid frame, one protocol error, and whether data was consumed."""
        if not self._buffer:
            return None, None, False

        header_index = self._find_next_header()
        if header_index < 0:
            if len(self._buffer) >= FRAME_LENGTH:
                del self._buffer[0]
                return None, XKC_KL200_Status.RESPONSE_ERROR, True
            self._buffer.clear()
            return None, None, True
        if header_index > 0:
            malformed_frame = len(self._buffer) >= FRAME_LENGTH
            del self._buffer[:header_index]
            if malformed_frame:
                return None, XKC_KL200_Status.RESPONSE_ERROR, True
            return None, None, True

        if len(self._buffer) < 3:
            return None, None, False

        frame_length = self._buffer[2]
        if frame_length != FRAME_LENGTH:
            del self._buffer[0]
            if len(self._buffer) >= FRAME_LENGTH - 1:
                return None, XKC_KL200_Status.RESPONSE_ERROR, True
            return None, None, True

        if len(self._buffer) < FRAME_LENGTH:
            return None, None, False

        candidate = bytes(self._buffer[:FRAME_LENGTH])
        if candidate[-1] != calculate_checksum(candidate[:-1]):
            del self._buffer[0]
            return None, XKC_KL200_Status.CHECKSUM_ERROR, True

        if expected_command is not None and candidate[1] != expected_command:
            return self._consume_mismatched_candidate(error_status=None)

        if expected_header is not None and candidate[0] != expected_header:
            return self._consume_mismatched_candidate(
                error_status=(
                    None
                    if allow_header_mismatch_skip
                    else XKC_KL200_Status.RESPONSE_ERROR
                )
            )

        del self._buffer[:FRAME_LENGTH]
        return candidate, None, True

    # Preserve overlapping candidate windows when a checksum-valid frame mismatches.
    def _consume_mismatched_candidate(
        self,
        *,
        error_status: XKC_KL200_Status | None,
    ) -> tuple[None, XKC_KL200_Status | None, bool]:
        """Resynchronize within a checksum-valid mismatched candidate."""
        overlap_header_index = self._find_next_header(start=1, stop=FRAME_LENGTH)
        if overlap_header_index < 0:
            del self._buffer[:FRAME_LENGTH]
        else:
            del self._buffer[:overlap_header_index]
        return None, error_status, True

    # Find the next possible frame header without allocating new buffers.
    def _find_next_header(self, *, start: int = 0, stop: int | None = None) -> int:
        """Return the index of the next protocol header byte or ``-1``."""
        end_index = len(self._buffer) if stop is None else min(stop, len(self._buffer))
        for index in range(start, end_index):
            byte = self._buffer[index]
            if byte in (COMMAND_HEADER, SYSTEM_HEADER):
                return index
        return -1
