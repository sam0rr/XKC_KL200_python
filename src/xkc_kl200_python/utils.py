"""Protocol frame helpers shared by commands, parsing, and tests."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from .constants import (
    COMMAND_HEADER,
    FRAME_LENGTH,
    READ_DISTANCE_COMMAND,
    SYSTEM_HEADER,
)


@dataclass(frozen=True, kw_only=True, slots=True)
class FramePayload:
    """Three data bytes carried by an XKC-KL200 protocol frame."""

    data_high: int = 0
    data_low: int = 0
    tail: int = 0

    def __post_init__(self) -> None:
        """Validate that every payload field fits in one byte."""
        for field_name, value in (
            ("data_high", self.data_high),
            ("data_low", self.data_low),
            ("tail", self.tail),
        ):
            if not 0 <= value <= 0xFF:
                raise ValueError(f"{field_name} must be between 0 and 255")

    def to_bytes(self) -> bytes:
        """Encode the payload fields as their three wire-level bytes."""
        return bytes((self.data_high, self.data_low, self.tail))


@dataclass(frozen=True, kw_only=True, slots=True)
class ProtocolFrame:
    """Decoded view of a raw 9-byte XKC-KL200 protocol frame."""

    header: int
    command: int
    length: int
    address: int
    payload: FramePayload


EMPTY_FRAME_PAYLOAD: Final = FramePayload()


def calculate_checksum(data: Sequence[int]) -> int:
    """Compute the protocol XOR checksum for a byte sequence."""
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


def build_command_frame(
    *,
    header: int,
    command: int,
    address: int,
    payload: FramePayload = EMPTY_FRAME_PAYLOAD,
) -> bytes:
    """Build a validated command frame with an automatically computed checksum."""
    frame = bytearray(
        [
            header,
            command,
            FRAME_LENGTH,
            (address >> 8) & 0xFF,
            address & 0xFF,
            *payload.to_bytes(),
            0,
        ]
    )
    frame[-1] = calculate_checksum(frame[:-1])
    return bytes(frame)


def parse_frame(frame: bytes, *, expected_command: int | None = None) -> ProtocolFrame:
    """Validate and decode a raw protocol frame."""
    if len(frame) != FRAME_LENGTH:
        raise ValueError(f"Protocol frame must be exactly {FRAME_LENGTH} bytes")

    if frame[0] not in (COMMAND_HEADER, SYSTEM_HEADER):
        raise ValueError(f"Invalid frame header: {frame[0]:#04x}")

    if frame[2] != FRAME_LENGTH:
        raise ValueError(f"Invalid frame length byte: {frame[2]:#04x}")

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
        payload=FramePayload(
            data_high=frame[5],
            data_low=frame[6],
            tail=frame[7],
        ),
    )


def parse_measurement_frame(frame: bytes) -> tuple[int, int]:
    """Decode a distance measurement frame into address and millimeters."""
    parsed = parse_frame(frame, expected_command=READ_DISTANCE_COMMAND)
    distance_mm = (parsed.payload.data_high << 8) | parsed.payload.data_low
    return parsed.address, distance_mm
