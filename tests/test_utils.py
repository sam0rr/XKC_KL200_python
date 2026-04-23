"""Protocol helper tests shared by runtime code and test fixtures."""

import pytest

from xkc_kl200_python.constants import READ_DISTANCE_COMMAND
from xkc_kl200_python.utils import (
    build_command_frame,
    calculate_checksum,
    parse_frame,
    parse_measurement_frame,
)


# Verify the checksum helper matches the documented XOR calculation.
def test_calculate_checksum() -> None:
    data = [0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00]

    assert calculate_checksum(data) == 0x58


# Verify that outbound command frames are assembled with the expected layout.
def test_build_command_frame() -> None:
    frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)

    assert frame == bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x58])


# Verify that measurement frames decode into address and millimeter values.
def test_parse_measurement_frame() -> None:
    frame = bytes([0x62, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xEF])

    address, distance_mm = parse_measurement_frame(frame)

    assert address == 0x1234
    assert distance_mm == 400


# Verify that bad checksums are rejected during frame parsing.
def test_parse_frame_invalid_checksum_raises() -> None:
    frame = bytes([0x62, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0x00])

    with pytest.raises(ValueError, match="Invalid checksum"):
        parse_frame(frame)


# Verify that undersized frames are rejected before deeper parsing.
def test_parse_frame_invalid_length_raises() -> None:
    with pytest.raises(ValueError, match="exactly 9 bytes"):
        parse_frame(b"\x62\x33")


# Verify that unknown frame headers are treated as protocol errors.
def test_parse_frame_invalid_header_raises() -> None:
    frame = bytes([0x60, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xED])

    with pytest.raises(ValueError, match="Invalid frame header"):
        parse_frame(frame)


# Verify that callers can require one specific command type when parsing.
def test_parse_frame_unexpected_command_raises() -> None:
    frame = bytes([0x62, 0x34, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xE8])

    with pytest.raises(ValueError, match="Unexpected command"):
        parse_frame(frame, expected_command=READ_DISTANCE_COMMAND)
