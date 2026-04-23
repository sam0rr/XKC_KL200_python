"""Mode-setting tests for the remaining LED, relay, and communication controls."""

from conftest import FakeSerialFactory

from xkc_kl200_python import CommunicationMode, LedMode, RelayMode, XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import build_command_frame


# Verify that invalid LED enum values are rejected before any I/O.
def test_invalid_led_mode_returns_invalid_parameter(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", serial_factory=serial_factory)

    assert sensor.set_led_mode(9) == XKC_KL200_Error.INVALID_PARAMETER


# Verify that the supported mode-setting commands all receive acknowledgements.
def test_set_control_modes_acknowledge(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x37, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x38, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    )

    assert sensor.set_led_mode(LedMode.ALWAYS_ON) == XKC_KL200_Error.SUCCESS
    assert (
        sensor.set_relay_mode(RelayMode.ACTIVE_WHEN_DETECTED) == XKC_KL200_Error.SUCCESS
    )
    assert (
        sensor.set_communication_mode(CommunicationMode.UART) == XKC_KL200_Error.SUCCESS
    )
