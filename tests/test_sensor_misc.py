"""Miscellaneous behavior tests for the simplified sensor wrapper."""

import pytest
from pytest import MonkeyPatch

from conftest import FakeSerialFactory

from xkc_kl200_python import CommunicationMode, SensorConfig, XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Status
from xkc_kl200_python.utils import build_command_frame


# Create a zero-startup-delay sensor for focused behavior tests.
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


# Verify that callers must provide either a port or a full config object.
def test_init_without_port_or_config_raises() -> None:
    with pytest.raises(ValueError, match="port is required"):
        XKC_KL200()


# Verify that context-manager use always closes the serial port.
def test_context_manager_closes_serial(serial_factory: FakeSerialFactory) -> None:
    sensor: XKC_KL200
    with make_sensor(serial_factory) as sensor:
        assert sensor is not None
        assert sensor.address == 0xFFFF

    assert serial_factory.holder["serial"].is_open is False


# Verify that both reset command variants return successful acknowledgements.
def test_hard_and_soft_reset(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )

    assert sensor.hard_reset() == XKC_KL200_Status.SUCCESS
    assert sensor.soft_reset() == XKC_KL200_Status.SUCCESS


# Verify that address changes update both config intent and cached runtime state.
def test_change_address_success_updates_config_and_state(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x32, address=0xFFFF)
    )

    result = sensor.change_address(0x1234)

    assert result == XKC_KL200_Status.SUCCESS
    assert sensor.config.address == 0x1234
    assert sensor.address == 0x1234


# Verify that out-of-range addresses are rejected before touching the port.
def test_change_address_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.change_address(0x1_0000) == XKC_KL200_Status.INVALID_PARAMETER


# Verify that unsupported baud values are rejected before sending a command.
def test_change_baud_rate_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.change_baud_rate(12345) == XKC_KL200_Status.INVALID_PARAMETER


# Verify that invalid enum values for relay and communication mode are rejected.
def test_invalid_relay_and_communication_modes(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)

    assert sensor.set_relay_mode(3) == XKC_KL200_Status.INVALID_PARAMETER
    assert sensor.set_communication_mode(9) == XKC_KL200_Status.INVALID_PARAMETER


# Verify timeout, checksum, and wrong-command responses from the ACK reader.
def test_wait_for_response_timeout_and_errors(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory, timeout=0.0)
    serial_port = serial_factory.holder["serial"]

    assert sensor._wait_for_response(0x34) == XKC_KL200_Status.TIMEOUT

    serial_port.queue_read(
        bytes([0x62, 0x34, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
    )
    assert sensor._wait_for_response(0x34) == XKC_KL200_Status.CHECKSUM_ERROR

    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x35, address=0xFFFF)
    )
    assert sensor._wait_for_response(0x34) == XKC_KL200_Status.RESPONSE_ERROR


# Verify the small baud helper supports both values and raw codes.
def test_resolve_baud_rate_code_static_helper() -> None:
    assert XKC_KL200._resolve_baud_rate_code(9600) == 2
    assert XKC_KL200._resolve_baud_rate_code(8) == 8
    assert XKC_KL200._resolve_baud_rate_code(99999) is None


# Verify that close() delegates directly to the transport wrapper.
def test_close_delegates_to_serial_manager(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = make_sensor(serial_factory)
    close_calls: list[str] = []
    manager = sensor._serial_manager

    monkeypatch.setattr(manager, "close", lambda: close_calls.append("closed"))

    sensor.close()

    assert close_calls == ["closed"]


# Verify that communication-mode commands use the protocol system header.
def test_communication_mode_success_uses_system_header(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    )

    result = sensor.set_communication_mode(CommunicationMode.UART)

    assert result == XKC_KL200_Status.SUCCESS
    assert serial_port.written_frames[-1][0] == 0x61
