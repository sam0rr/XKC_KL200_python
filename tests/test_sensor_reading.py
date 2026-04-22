from conftest import FakeSerialFactory
from pytest import MonkeyPatch

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


def test_read_distance_in_auto_mode_drains_uploaded_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )

    distance = sensor.read_distance(timeout=0.0)

    assert distance == 100
    assert sensor.get_last_received_distance() == 100


def test_read_distance_in_auto_mode_waits_for_next_frame(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    sensor.state.last_received_distance_mm = 88
    process_results = iter([False, False, True, False])
    monotonic_values = iter([0.0, 0.0001, 0.0002, 0.0003, 0.0004])

    def fake_process_auto_data() -> bool:
        result = next(process_results)
        if result:
            sensor.state.mark_measurement(144, address=0x0001)
        return result

    monkeypatch.setattr(sensor, "process_auto_data", fake_process_auto_data)
    monkeypatch.setattr(
        "xkc_kl200_python.sensor.time.monotonic", lambda: next(monotonic_values)
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "xkc_kl200_python.sensor.time.sleep", lambda delay: sleep_calls.append(delay)
    )

    distance = sensor.read_distance(timeout=0.01)

    assert distance == 144
    assert sleep_calls == [0.001, 0.001]


def test_process_auto_data_reads_measurement(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=1)
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
