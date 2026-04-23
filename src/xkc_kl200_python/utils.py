"""Protocol frame helpers shared by commands, parsing, and tests."""

from dataclasses import dataclass
from typing import Sequence

from .constants import (
    COMMAND_HEADER,
    FRAME_LENGTH,
    READ_DISTANCE_COMMAND,
    SYSTEM_HEADER,
)


# Represent a validated frame in a structured form once parsing succeeds.
@dataclass(frozen=True)
class ProtocolFrame:
    """Decoded view of a raw 9-byte XKC-KL200 protocol frame."""

    header: int
    command: int
    length: int
    address: int
    data_high: int
    data_low: int
    tail: int


# Match the device protocol checksum rule used across all frames.
def calculate_checksum(data: Sequence[int]) -> int:
    """Compute the protocol XOR checksum for a byte sequence."""
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


# Build outbound command frames in one place so tests and runtime stay aligned.
def build_command_frame(
    *,
    header: int,
    command: int,
    address: int,
    data_high: int = 0,
    data_low: int = 0,
    tail: int = 0,
) -> bytes:
    """Build a validated command frame with an automatically computed checksum."""
    frame = bytearray(
        [
            header,
            command,
            FRAME_LENGTH,
            (address >> 8) & 0xFF,
            address & 0xFF,
            data_high & 0xFF,
            data_low & 0xFF,
            tail & 0xFF,
            0,
        ]
    )
    frame[-1] = calculate_checksum(frame[:-1])
    return bytes(frame)


# Validate a raw frame before higher-level code interprets its contents.
def parse_frame(frame: bytes, *, expected_command: int | None = None) -> ProtocolFrame:
    """Validate and decode a raw protocol frame."""
    if len(frame) != FRAME_LENGTH:
        raise ValueError(f"Protocol frame must be exactly {FRAME_LENGTH} bytes")

    if frame[0] not in (COMMAND_HEADER, SYSTEM_HEADER):
        raise ValueError(f"Invalid frame header: {frame[0]:#04x}")

    expected_checksum = calculate_checksum(frame[:-1])
    if frame[-1] != expected_checksum:
        raise ValueError("Invalid checksum")

    if expected_command is not None and frame[1] != expected_command:
        raise ValueError(
            f"Unexpected command: expected {expected_command:#04x}, got {frame[1]:#04x}"
        )

    return ProtocolFrame(
        header=frame[0],
        command=frame[1],
        length=frame[2],
        address=(frame[3] << 8) | frame[4],
        data_high=frame[5],
        data_low=frame[6],
        tail=frame[7],
    )


# Decode the standard measurement-response frame into address and millimeters.
def parse_measurement_frame(frame: bytes) -> tuple[int, int]:
    """Decode a distance measurement frame into address and millimeters."""
    parsed = parse_frame(frame, expected_command=READ_DISTANCE_COMMAND)
    distance_mm = (parsed.data_high << 8) | parsed.data_low
    return parsed.address, distance_mm
