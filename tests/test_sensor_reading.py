"""Measurement-read tests for the simplified request/response sensor API."""

from conftest import FakeSerialFactory

from xkc_kl200_python import XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import build_command_frame


# Verify that a valid measurement updates the cached value and address.
def test_read_distance_updates_state(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x01, 0x2C, 0x00, 0x75])
    )

    distance = sensor.read_distance()

    assert distance == 300
    assert sensor.last_received_distance == 300
    assert sensor.address == 0xFFFF
    assert serial_port.written_frames == [
        build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    ]


# Verify that timeouts preserve the previous successful measurement.
def test_read_distance_timeout_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    sensor._last_received_distance_mm = 123

    assert sensor.read_distance(timeout=0.0) == 123


# Verify that malformed frames also fall back to the last good value.
def test_read_distance_invalid_frame_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    sensor._last_received_distance_mm = 55
    serial_port.queue_read(
        bytes([0x60, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x04])
    )

    assert sensor.read_distance() == 55


# Verify that change_baud_rate accepts human-readable baud values.
def test_change_baud_rate_accepts_real_baudrate(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x30, address=0xFFFF, data_low=8)
    )

    result = sensor.change_baud_rate(115200)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.config.baudrate == 115200
    assert serial_port.baudrate == 115200
