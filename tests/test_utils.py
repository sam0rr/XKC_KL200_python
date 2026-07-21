"""Protocol helper tests shared by runtime code and test fixtures."""

import pytest

from xkc_kl200_python.constants import READ_DISTANCE_COMMAND
from xkc_kl200_python.utils import (
    FramePayload,
    build_command_frame,
    calculate_checksum,
    parse_frame,
    parse_measurement_frame,
)


def test_frame_payload_validates_and_encodes_bytes() -> None:
    """Verify payload encoding and byte-range validation."""
    assert FramePayload(data_high=1, data_low=2, tail=3).to_bytes() == b"\x01\x02\x03"

    with pytest.raises(ValueError, match="data_high must be between 0 and 255"):
        FramePayload(data_high=-1)

    with pytest.raises(ValueError, match="data_low must be between 0 and 255"):
        FramePayload(data_low=256)

    with pytest.raises(ValueError, match="tail must be between 0 and 255"):
        FramePayload(tail=256)


def test_calculate_checksum() -> None:
    """Verify the checksum helper matches the documented XOR calculation."""
    data = [0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00]

    assert calculate_checksum(data) == 0x58


def test_build_command_frame() -> None:
    """Verify that outbound command frames are assembled with the expected layout."""
    frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)

    assert frame == bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x58])


def test_parse_measurement_frame() -> None:
    """Verify that measurement frames decode into address and millimeter values."""
    frame = bytes([0x62, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xEF])

    address, distance_mm = parse_measurement_frame(frame)

    assert address == 0x1234
    assert distance_mm == 400


def test_parse_frame_invalid_checksum_raises() -> None:
    """Verify that bad checksums are rejected during frame parsing."""
    frame = bytes([0x62, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0x00])

    with pytest.raises(ValueError, match="Invalid checksum"):
        parse_frame(frame)


def test_parse_frame_invalid_length_raises() -> None:
    """Verify that undersized frames are rejected before deeper parsing."""
    with pytest.raises(ValueError, match="exactly 9 bytes"):
        parse_frame(b"\x62\x33")


def test_parse_frame_invalid_length_byte_raises() -> None:
    """Verify that the embedded length byte must match the fixed protocol size."""
    frame = bytes([0x62, 0x33, 0x08, 0x12, 0x34, 0x01, 0x90, 0x00, 0xEC])

    with pytest.raises(ValueError, match="Invalid frame length byte"):
        parse_frame(frame)


def test_parse_frame_invalid_header_raises() -> None:
    """Verify that unknown frame headers are treated as protocol errors."""
    frame = bytes([0x60, 0x33, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xED])

    with pytest.raises(ValueError, match="Invalid frame header"):
        parse_frame(frame)


def test_parse_frame_unexpected_command_raises() -> None:
    """Verify that callers can require one specific command type when parsing."""
    frame = bytes([0x62, 0x34, 0x09, 0x12, 0x34, 0x01, 0x90, 0x00, 0xE8])

    with pytest.raises(ValueError, match="Unexpected command"):
        parse_frame(frame, expected_command=READ_DISTANCE_COMMAND)
