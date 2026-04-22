from conftest import FakeSerialFactory

from xkc_kl200_python import XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import build_command_frame


def test_read_distance_updates_state(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x01, 0x2C, 0x00, 0x75])
    )

    distance = sensor.read_distance()

    assert distance == 300
    assert sensor.available() is True
    assert sensor.get_distance() == 300
    assert sensor.available() is False


def test_read_distance_timeout_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    sensor.state.last_received_distance_mm = 123

    assert sensor.read_distance(timeout=0.0) == 123


def test_process_auto_data_reads_measurement(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=0)
    )
    assert sensor.set_upload_mode(True) == XKC_KL200_Error.SUCCESS

    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )

    assert sensor.process_auto_data() is True
    assert sensor.get_last_received_distance() == 100


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
