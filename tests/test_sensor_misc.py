import pytest
from pytest import MonkeyPatch

from conftest import FakeSerialFactory

from xkc_kl200_python import CommunicationMode, SensorConfig, XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import build_command_frame


def make_sensor(
    serial_factory: FakeSerialFactory, *, timeout: float = 0.01
) -> XKC_KL200:
    config = SensorConfig(
        port="/dev/ttyUSB0",
        baudrate=9600,
        timeout=timeout,
        startup_delay_s=0.0,
    )
    return XKC_KL200(config=config, serial_factory=serial_factory)


def test_init_without_port_or_config_raises() -> None:
    with pytest.raises(ValueError, match="port is required"):
        XKC_KL200()


def test_context_manager_closes_serial(serial_factory: FakeSerialFactory) -> None:
    sensor: XKC_KL200
    with make_sensor(serial_factory) as sensor:
        assert sensor is not None
        assert sensor.state.address == 0xFFFF

    assert serial_factory.holder["serial"].is_open is False


def test_hard_and_soft_reset(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )

    assert sensor.hard_reset() == XKC_KL200_Error.SUCCESS
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )
    assert sensor.soft_reset() == XKC_KL200_Error.SUCCESS


def test_change_address_success_updates_config_and_state(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x32, address=0xFFFF)
    )

    result = sensor.change_address(0x1234)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.config.address == 0x1234
    assert sensor.state.address == 0x1234


def test_change_address_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.change_address(0x1_0000) == XKC_KL200_Error.INVALID_PARAMETER


def test_change_baud_rate_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.change_baud_rate(12345) == XKC_KL200_Error.INVALID_PARAMETER


def test_set_upload_interval_success(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x35, address=0xFFFF)
    )

    assert sensor.set_upload_interval(10) == XKC_KL200_Error.SUCCESS


def test_invalid_relay_and_communication_modes(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.set_relay_mode(3) == XKC_KL200_Error.INVALID_PARAMETER
    assert sensor.set_communication_mode(9) == XKC_KL200_Error.INVALID_PARAMETER


def test_read_distance_returns_last_value_in_auto_mode(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    sensor.state.auto_upload_enabled = True
    sensor.state.last_received_distance_mm = 77

    assert sensor.read_distance() == 77


def test_read_distance_invalid_frame_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    sensor.state.last_received_distance_mm = 55
    serial_port.queue_read(
        bytes([0x60, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x04])
    )

    assert sensor.read_distance() == 55


def test_available_true_when_auto_mode_has_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_factory.holder["serial"].queue_read(b"\x00" * 9)

    assert sensor.available() is True


def test_process_auto_data_false_when_auto_mode_disabled(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.process_auto_data() is False


def test_process_auto_data_false_when_frame_is_incomplete(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_factory.holder["serial"].queue_read(b"\x00" * 8)

    assert sensor.process_auto_data() is False


def test_process_auto_data_false_when_read_exact_returns_none(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = make_sensor(serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_factory.holder["serial"].queue_read(b"\x00" * 9)

    monkeypatch.setattr(
        sensor._serial_manager, "read_exact", lambda size, timeout: None
    )

    assert sensor.process_auto_data() is False


def test_process_auto_data_discards_extra_byte_on_invalid_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(b"\x60\x33\x09\xff\xff\x00\x64\x00\x04\xaa")

    assert sensor.process_auto_data() is False
    assert serial_port.in_waiting == 0


def test_wait_for_response_timeout_and_errors(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory, timeout=0.0)
    serial_port = serial_factory.holder["serial"]

    assert sensor._wait_for_response(0x34) == XKC_KL200_Error.TIMEOUT

    serial_port.queue_read(
        bytes([0x62, 0x34, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
    )
    assert sensor._wait_for_response(0x34) == XKC_KL200_Error.CHECKSUM_ERROR

    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x35, address=0xFFFF)
    )
    assert sensor._wait_for_response(0x34) == XKC_KL200_Error.RESPONSE_ERROR


def test_wait_for_response_ignores_measurement_frame_before_ack(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory, timeout=0.01)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0x0001)
    )

    assert sensor._wait_for_response(0x34) == XKC_KL200_Error.SUCCESS
    assert sensor.get_last_received_distance() == 100
    assert sensor.state.address == 0x0001


def test_wait_for_response_retries_after_invalid_non_checksum_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory, timeout=0.01)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x60, 0x34, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x5E])
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF)
    )

    assert sensor._wait_for_response(0x34) == XKC_KL200_Error.SUCCESS


def test_send_ack_command_preserves_measurement_frame_after_success(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory, timeout=0.01)
    serial_port = serial_factory.holder["serial"]
    ack_with_trailing_measurement = build_command_frame(
        header=0x62, command=0x34, address=0xFFFF
    ) + bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    serial_port.queue_read(ack_with_trailing_measurement)

    assert sensor.set_upload_mode(True) == XKC_KL200_Error.SUCCESS
    assert serial_port.in_waiting == 9
    assert sensor.read_distance(timeout=0.0) == 100


def test_resolve_baud_rate_code_static_helper() -> None:
    assert XKC_KL200._resolve_baud_rate_code(9600) == 2
    assert XKC_KL200._resolve_baud_rate_code(8) == 8
    assert XKC_KL200._resolve_baud_rate_code(99999) is None


def test_close_delegates_to_serial_manager(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = make_sensor(serial_factory)
    close_calls: list[str] = []
    manager = sensor._serial_manager

    monkeypatch.setattr(manager, "close", lambda: close_calls.append("closed"))

    sensor.close()

    assert close_calls == ["closed"]


def test_communication_mode_success_uses_system_header(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    )

    result = sensor.set_communication_mode(CommunicationMode.UART)

    assert result == XKC_KL200_Error.SUCCESS
    assert serial_port.written_frames[-1][0] == 0x61
