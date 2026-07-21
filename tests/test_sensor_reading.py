"""Measurement-read tests for the simplified request/response sensor API."""

import pytest
from conftest import FakeSerialFactory

from xkc_kl200_python import (
    XKC_KL200,
    XKC_KL200_ResponseError,
    XKC_KL200_TimeoutError,
)
from xkc_kl200_python.constants import XKC_KL200_Status
from xkc_kl200_python.utils import FramePayload, build_command_frame


def test_read_distance_updates_state(serial_factory: FakeSerialFactory) -> None:
    """Verify that a valid measurement updates the cached value and address."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x01, 0x2C, 0x00, 0x75])
    )

    distance = sensor.read_distance()

    assert distance == 300
    assert serial_port.reset_input_count == 1
    assert sensor.last_received_distance == 300
    assert sensor.address == 0xFFFF
    assert serial_port.written_frames == [
        build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    ]


def test_read_distance_timeout_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that timeouts fail explicitly instead of returning cached data."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    sensor._last_received_distance_mm = 123

    with pytest.raises(XKC_KL200_TimeoutError):
        sensor.read_distance(timeout=0.0)

    assert sensor.last_received_distance == 123


def test_read_distance_invalid_frame_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that corrupted expected frames fail explicitly and preserve the last good value."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    sensor._last_received_distance_mm = 55
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
    )

    with pytest.raises(XKC_KL200_ResponseError):
        sensor.read_distance()

    assert sensor.last_received_distance == 55


def test_read_distance_recovers_from_checksum_error_with_buffered_reply(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that a valid measurement buffered behind a bad frame is still returned."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
        + build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            payload=FramePayload(data_low=23),
        )
    )

    distance = sensor.read_distance(timeout=0.0)

    assert distance == 23
    assert sensor.last_received_distance == 23


def test_read_distance_malformed_complete_frame_raises_response_error(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that a complete malformed measurement is not misreported as a timeout."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    sensor._last_received_distance_mm = 55
    serial_port.queue_read(b"\x62\x33\x08\xff\xff\x00\x64\x00\x00")

    with pytest.raises(XKC_KL200_ResponseError):
        sensor.read_distance(timeout=0.0)

    assert sensor.last_received_distance == 55


def test_read_distance_wrong_header_reply_raises_response_error(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that a complete wrong-header reply is surfaced as a response error."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(
            header=0x61,
            command=0x33,
            address=0xFFFF,
            payload=FramePayload(data_low=17),
        )
    )

    with pytest.raises(XKC_KL200_ResponseError):
        sensor.read_distance(timeout=0.0)


def test_read_distance_junk_before_timeout(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that stray junk still ends as a timeout when no measurement follows."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(b"\x60\x33\x09")

    with pytest.raises(XKC_KL200_TimeoutError):
        sensor.read_distance()


def test_read_distance_skips_stale_valid_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that stale valid frames are skipped until the measurement arrives."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            payload=FramePayload(data_low=17),
        )
    )

    distance = sensor.read_distance()

    assert distance == 17
    assert sensor.last_received_distance == 17


def test_read_distance_skips_stale_valid_frame_in_same_chunk(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that a coalesced stale frame and measurement still succeed at zero timeout."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
        + build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            payload=FramePayload(data_low=25),
        )
    )

    distance = sensor.read_distance(timeout=0.0)

    assert distance == 25
    assert sensor.last_received_distance == 25


def test_read_distance_resynchronizes_within_checksum_valid_overlap(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that an overlapped checksum-valid window still recovers the buffered measurement."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    measurement_frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0x0102,
        payload=FramePayload(data_high=0x03, data_low=0x04, tail=0x05),
    )
    serial_port.queue_read(bytes([0x61, 0x30, 0x09]) + measurement_frame)

    distance = sensor.read_distance(timeout=0.0)

    assert distance == 0x0304
    assert sensor.last_received_distance == 0x0304
    assert sensor.address == 0x0102


def test_change_baud_rate_accepts_real_baudrate(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that change_baud_rate accepts human-readable baud values."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(
            header=0x62,
            command=0x30,
            address=0xFFFF,
            payload=FramePayload(data_low=8),
        )
    )

    result = sensor.change_baud_rate(115200)

    assert result == XKC_KL200_Status.SUCCESS
    assert sensor.config.baudrate == 115200
    assert serial_port.baudrate == 115200


def test_change_baud_rate_requires_command_header_ack(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that change_baud_rate ignores a stale system-header ACK sharing command 0x30."""
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(
            header=0x61,
            command=0x30,
            address=0xFFFF,
            payload=FramePayload(data_low=8),
        )
    )

    result = sensor.change_baud_rate(115200)

    assert result == XKC_KL200_Status.TIMEOUT
    assert sensor.config.baudrate == 9600
    assert serial_port.baudrate == 9600
