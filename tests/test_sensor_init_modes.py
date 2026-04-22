from conftest import FakeSerialFactory
from pytest import MonkeyPatch

from xkc_kl200_python import CommunicationMode, LedMode, RelayMode, XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import build_command_frame


def test_set_upload_mode_updates_state(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(
        port="/dev/ttyUSB0",
        timeout=0.01,
        config=None,
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF)
    )

    result = sensor.set_upload_mode(True)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.state.auto_upload_enabled is True
    assert serial_port.written_frames == [
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=1)
    ]


def test_set_upload_mode_false_uses_manual_value(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(
        port="/dev/ttyUSB0",
        timeout=0.01,
        config=None,
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF)
    )

    result = sensor.set_upload_mode(False)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.state.auto_upload_enabled is False
    assert serial_port.written_frames == [
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=0)
    ]


def test_invalid_upload_interval_returns_invalid_parameter(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", serial_factory=serial_factory)

    assert sensor.set_upload_interval(0) == XKC_KL200_Error.INVALID_PARAMETER


def test_set_upload_interval_after_enabling_auto_upload(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(
        port="/dev/ttyUSB0",
        timeout=0.01,
        config=None,
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]

    def queue_response(data: bytes) -> int:
        serial_port.written_frames.append(bytes(data))
        command = data[1]
        if command == 0x34:
            serial_port.queue_read(
                build_command_frame(header=0x62, command=0x34, address=0xFFFF)
            )
        elif command == 0x35:
            serial_port.queue_read(
                build_command_frame(header=0x62, command=0x35, address=0xFFFF)
            )
        return len(data)

    monkeypatch.setattr(serial_port, "write", queue_response)

    assert sensor.set_upload_mode(True) == XKC_KL200_Error.SUCCESS
    result = sensor.set_upload_interval(10)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.state.auto_upload_enabled is True
    assert serial_port.written_frames == [
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=1),
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=0),
        build_command_frame(header=0x62, command=0x35, address=0xFFFF, data_low=10),
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=1),
    ]


def test_set_upload_interval_returns_disable_error_when_auto_mode_turn_off_fails(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(
        port="/dev/ttyUSB0",
        timeout=0.01,
        config=None,
        serial_factory=serial_factory,
    )
    sensor.state.auto_upload_enabled = True
    monkeypatch.setattr(
        sensor, "set_upload_mode", lambda auto_upload: XKC_KL200_Error.TIMEOUT
    )

    assert sensor.set_upload_interval(10) == XKC_KL200_Error.TIMEOUT


def test_set_upload_interval_propagates_interval_command_error(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(
        port="/dev/ttyUSB0",
        timeout=0.01,
        config=None,
        serial_factory=serial_factory,
    )
    monkeypatch.setattr(
        sensor, "_send_ack_command", lambda **kwargs: XKC_KL200_Error.TIMEOUT
    )

    assert sensor.set_upload_interval(10) == XKC_KL200_Error.TIMEOUT


def test_invalid_led_mode_returns_invalid_parameter(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", serial_factory=serial_factory)

    assert sensor.set_led_mode(9) == XKC_KL200_Error.INVALID_PARAMETER


def test_set_control_modes_acknowledge(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x37, address=0xFFFF)
    )

    assert sensor.set_led_mode(LedMode.ALWAYS_ON) == XKC_KL200_Error.SUCCESS
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x38, address=0xFFFF)
    )
    assert (
        sensor.set_relay_mode(RelayMode.ACTIVE_WHEN_DETECTED) == XKC_KL200_Error.SUCCESS
    )
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    )
    assert (
        sensor.set_communication_mode(CommunicationMode.UART) == XKC_KL200_Error.SUCCESS
    )
