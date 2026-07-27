"""Miscellaneous behavior tests for the simplified sensor wrapper."""

import pytest
from conftest import FakeSerialFactory

from xkc_kl200_python import CommunicationMode, SensorConfig, XkcKl200
from xkc_kl200_python._protocol import FramePayload, build_command_frame
from xkc_kl200_python.constants import XkcKl200Status


def make_sensor(
    serial_factory: FakeSerialFactory, *, timeout: float = 0.01
) -> XkcKl200:
    """Create a zero-startup-delay sensor for focused behavior tests."""
    config = SensorConfig(
        port="/dev/ttyUSB0",
        baudrate=9600,
        timeout=timeout,
        startup_delay_s=0.0,
    )
    return XkcKl200(config=config, serial_factory=serial_factory)


def test_init_without_port_or_config_raises() -> None:
    """Verify that callers must provide either a port or a full config object."""
    with pytest.raises(ValueError, match="port is required"):
        XkcKl200()


def test_context_manager_closes_serial(serial_factory: FakeSerialFactory) -> None:
    """Verify that context-manager use always closes the serial port."""
    sensor: XkcKl200
    with make_sensor(serial_factory) as sensor:
        assert sensor is not None
        assert sensor.address == 0xFFFF

    assert serial_factory.holder["serial"].is_open is False


def test_reset_buffers_clears_serial_buffers(serial_factory: FakeSerialFactory) -> None:
    """Verify that callers can explicitly clear serial buffers during recovery."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]

    sensor.reset_buffers()

    assert serial_port.reset_input_count == 1
    assert serial_port.reset_output_count == 1


def test_reset_input_buffer_clears_serial_input(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that callers can clear the input buffer directly before a fresh probe."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]

    sensor.reset_input_buffer()

    assert serial_port.reset_input_count == 1
    assert serial_port.reset_output_count == 0


def test_reset_output_buffer_clears_serial_output(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify callers can clear the output buffer when aborting recovery."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]

    sensor.reset_output_buffer()

    assert serial_port.reset_input_count == 0
    assert serial_port.reset_output_count == 1


def test_hard_and_soft_reset(serial_factory: FakeSerialFactory) -> None:
    """Verify that both reset command variants return successful acknowledgements."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )

    assert sensor.hard_reset() == XkcKl200Status.SUCCESS
    assert sensor.soft_reset() == XkcKl200Status.SUCCESS
    assert serial_port.reset_input_count == 2


def test_change_address_success_updates_config_and_state(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify address changes update config intent and cached runtime state."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x32, address=0xFFFF)
    )

    result = sensor.change_address(0x1234)

    assert result == XkcKl200Status.SUCCESS
    assert sensor.config.address == 0x1234
    assert sensor.address == 0x1234


def test_change_address_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    """Verify that out-of-range addresses are rejected before touching the port."""
    sensor = make_sensor(serial_factory)

    assert sensor.change_address(0x1_0000) == XkcKl200Status.INVALID_PARAMETER


def test_change_baud_rate_invalid_parameter(serial_factory: FakeSerialFactory) -> None:
    """Verify that unsupported baud values are rejected before sending a command."""
    sensor = make_sensor(serial_factory)

    assert sensor.change_baud_rate(12345) == XkcKl200Status.INVALID_PARAMETER


def test_invalid_relay_and_communication_modes(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that invalid enum values for relay and communication mode are rejected."""
    sensor = make_sensor(serial_factory)

    assert sensor.set_relay_mode(3) == XkcKl200Status.INVALID_PARAMETER
    assert sensor.set_communication_mode(9) == XkcKl200Status.INVALID_PARAMETER


def test_wait_for_response_timeout_and_errors(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify timeout and checksum responses from the ACK reader."""
    sensor = make_sensor(serial_factory, timeout=0.0)
    serial_port = serial_factory.holder["serial"]

    assert sensor._wait_for_response(expected_command=0x34) == XkcKl200Status.TIMEOUT

    serial_port.queue_read(
        bytes([0x62, 0x34, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
    )
    assert (
        sensor._wait_for_response(expected_command=0x34)
        == XkcKl200Status.CHECKSUM_ERROR
    )

    serial_port.queue_read(b"\x62\x34\x08\xff\xff\x00\x00\x00\x00")
    assert (
        sensor._wait_for_response(expected_command=0x34)
        == XkcKl200Status.RESPONSE_ERROR
    )


def test_wait_for_response_skips_stale_valid_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that stale measurement frames are skipped until the ACK arrives."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            payload=FramePayload(data_low=21),
        )
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )

    assert sensor._wait_for_response(expected_command=0x39) == XkcKl200Status.SUCCESS


def test_wait_for_response_stale_frame_then_timeout(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that stale ACK traffic still times out when no matching ACK arrives."""
    sensor = make_sensor(serial_factory, timeout=0.0)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x35, address=0xFFFF)
    )

    assert sensor._wait_for_response(expected_command=0x34) == XkcKl200Status.TIMEOUT


def test_resolve_baud_rate_code_static_helper() -> None:
    """Verify the small baud helper supports both values and raw codes."""
    assert XkcKl200._resolve_baud_rate_code(9600) == 2
    assert XkcKl200._resolve_baud_rate_code(8) == 8
    assert XkcKl200._resolve_baud_rate_code(99999) is None


def test_close_delegates_to_serial_manager(
    serial_factory: FakeSerialFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that close() delegates directly to the transport wrapper."""
    sensor = make_sensor(serial_factory)
    close_calls: list[str] = []
    manager = sensor._serial_manager

    monkeypatch.setattr(manager, "close", lambda: close_calls.append("closed"))

    sensor.close()

    assert close_calls == ["closed"]


def test_communication_mode_success_uses_system_header(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify that communication-mode commands use the protocol system header."""
    sensor = make_sensor(serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    )

    result = sensor.set_communication_mode(CommunicationMode.UART)

    assert result == XkcKl200Status.SUCCESS
    assert serial_port.written_frames[-1][0] == 0x61


def test_set_communication_mode_requires_system_header_ack(
    serial_factory: FakeSerialFactory,
) -> None:
    """Verify communication mode ignores a stale ACK with the same command byte."""
    sensor = make_sensor(serial_factory, timeout=0.0)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x30, address=0xFFFF)
    )

    result = sensor.set_communication_mode(CommunicationMode.UART)

    assert result == XkcKl200Status.TIMEOUT
