"""High-level request/response wrapper for the XKC-KL200 UART sensor."""

import time
from dataclasses import replace
from typing import Self, TypeVar

from .config import SensorConfig
from .constants import (
    BAUD_RATE_TO_CODE,
    CHANGE_ADDRESS_COMMAND,
    CHANGE_BAUD_RATE_COMMAND,
    CODE_TO_BAUD_RATE,
    COMMAND_HEADER,
    MAX_ADDRESS,
    MIN_ADDRESS,
    READ_DISTANCE_COMMAND,
    RESET_COMMAND,
    SET_COMMUNICATION_MODE_COMMAND,
    SET_LED_MODE_COMMAND,
    SET_RELAY_MODE_COMMAND,
    SYSTEM_HEADER,
    CommunicationMode,
    LedMode,
    RelayMode,
    XkcKl200Status,
)
from .errors import XkcKl200ResponseError, XkcKl200TimeoutError
from .serial_manager import SerialFactory, SerialManager
from .utils import (
    EMPTY_FRAME_PAYLOAD,
    FramePayload,
    build_command_frame,
    parse_frame,
    parse_measurement_frame,
)

EnumValue = TypeVar("EnumValue", bound=int)


class XkcKl200:
    """High-level interface for controlling an XKC-KL200 UART sensor."""

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 9600,
        timeout: float = 1.0,
        *,
        config: SensorConfig | None = None,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        """Initialize the sensor wrapper from a port or explicit config object."""
        if config is None:
            if port is None:
                raise ValueError("port is required when config is not provided")
            config = SensorConfig(port=port, baudrate=baudrate, timeout=timeout)

        self.config = config
        self._last_received_distance_mm = 0
        self._address = config.address
        self._serial_manager = SerialManager(
            config=config, serial_factory=serial_factory
        )

        if config.startup_delay_s > 0:
            time.sleep(config.startup_delay_s)

    def __enter__(self) -> Self:
        """Support ``with XkcKl200(...)`` context management."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the serial connection when leaving a context manager."""
        self.close()

    @property
    def address(self) -> int:
        """Return the most recently acknowledged or measured sensor address."""
        return self._address

    @property
    def last_received_distance(self) -> int:
        """Return the latest received distance."""
        return self._last_received_distance_mm

    def close(self) -> None:
        """Close the underlying serial connection."""
        self._serial_manager.close()

    def reset_buffers(self) -> None:
        """Clear pending serial input and output buffers."""
        self._serial_manager.reset_buffers()

    def reset_input_buffer(self) -> None:
        """Clear pending serial input bytes."""
        self._serial_manager.reset_input_buffer()

    def reset_output_buffer(self) -> None:
        """Clear pending serial output bytes."""
        self._serial_manager.reset_output_buffer()

    def hard_reset(self) -> XkcKl200Status:
        """Request a factory reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            payload=FramePayload(tail=0xFE),
        )

    def soft_reset(self) -> XkcKl200Status:
        """Request a user-settings reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            payload=FramePayload(tail=0xFD),
        )

    def change_address(self, address: int) -> XkcKl200Status:
        """Change the sensor address if the requested value is valid."""
        if not MIN_ADDRESS <= address <= MAX_ADDRESS:
            return XkcKl200Status.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_ADDRESS_COMMAND,
            payload=FramePayload(
                data_high=(address >> 8) & 0xFF,
                data_low=address & 0xFF,
            ),
        )
        if result == XkcKl200Status.SUCCESS:
            self.config = replace(self.config, address=address)
            self._address = address
        return result

    def change_baud_rate(self, baud_rate: int) -> XkcKl200Status:
        """Change the sensor baud rate using a baud value or protocol code."""
        baud_code = self._resolve_baud_rate_code(baud_rate)
        if baud_code is None:
            return XkcKl200Status.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_BAUD_RATE_COMMAND,
            payload=FramePayload(data_low=baud_code),
        )
        if result == XkcKl200Status.SUCCESS:
            new_baudrate = CODE_TO_BAUD_RATE[baud_code]
            self.config = replace(self.config, baudrate=new_baudrate)
            self._serial_manager.set_baudrate(new_baudrate)
        return result

    def set_led_mode(self, mode: int | LedMode) -> XkcKl200Status:
        """Configure the sensor LED behavior."""
        value = self._coerce_enum_value(mode, LedMode)
        if value is None:
            return XkcKl200Status.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_LED_MODE_COMMAND,
            payload=FramePayload(data_low=value),
        )

    def set_relay_mode(self, mode: int | RelayMode) -> XkcKl200Status:
        """Configure the relay output behavior."""
        value = self._coerce_enum_value(mode, RelayMode)
        if value is None:
            return XkcKl200Status.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_RELAY_MODE_COMMAND,
            payload=FramePayload(data_low=value),
        )

    def set_communication_mode(self, mode: int | CommunicationMode) -> XkcKl200Status:
        """Switch the device between relay mode and UART mode."""
        value = self._coerce_enum_value(mode, CommunicationMode)
        if value is None:
            return XkcKl200Status.INVALID_PARAMETER
        return self._send_ack_command(
            header=SYSTEM_HEADER,
            command=SET_COMMUNICATION_MODE_COMMAND,
            payload=FramePayload(data_low=value),
        )

    def read_distance(self, timeout: float | None = None) -> int:
        """Request one fresh distance measurement.

        Raises:
            XkcKl200TimeoutError: The sensor did not reply before the timeout.
            XkcKl200ResponseError: The reply frame was malformed or unexpected.
        """
        self._serial_manager.reset_input_buffer()
        self._serial_manager.write_frame(
            build_command_frame(
                header=COMMAND_HEADER,
                command=READ_DISTANCE_COMMAND,
                address=self.config.address,
            )
        )

        response, status = self._serial_manager.read_frame(
            expected_header=COMMAND_HEADER,
            expected_command=READ_DISTANCE_COMMAND,
            timeout=self.config.timeout if timeout is None else timeout,
        )
        if response is None:
            if status == XkcKl200Status.TIMEOUT:
                raise XkcKl200TimeoutError("Timed out waiting for a measurement frame")
            raise XkcKl200ResponseError("Received an invalid measurement frame")

        address, distance_mm = parse_measurement_frame(response)

        self._last_received_distance_mm = distance_mm
        self._address = address
        return distance_mm

    def _send_ack_command(
        self,
        *,
        command: int,
        header: int = COMMAND_HEADER,
        payload: FramePayload = EMPTY_FRAME_PAYLOAD,
    ) -> XkcKl200Status:
        """Send a command frame and wait for its acknowledgement."""
        frame = build_command_frame(
            header=header,
            command=command,
            address=self.config.address,
            payload=payload,
        )
        self._serial_manager.reset_input_buffer()
        self._serial_manager.write_frame(frame)
        return self._wait_for_response(expected_header=header, expected_command=command)

    def _wait_for_response(
        self,
        *,
        expected_header: int = COMMAND_HEADER,
        expected_command: int,
    ) -> XkcKl200Status:
        """Read and classify the acknowledgement for a configuration command."""
        # Command 0x30 is shared by baud-rate and communication-mode ACKs.
        allow_header_mismatch_skip = expected_command == CHANGE_BAUD_RATE_COMMAND
        response, status = self._serial_manager.read_frame(
            allow_header_mismatch_skip=allow_header_mismatch_skip,
            expected_header=expected_header,
            expected_command=expected_command,
            timeout=self.config.timeout,
        )
        if response is None:
            return status

        parsed = parse_frame(
            response,
            expected_command=expected_command,
        )
        self._address = parsed.address
        return XkcKl200Status.SUCCESS

    @staticmethod
    def _resolve_baud_rate_code(baud_rate: int) -> int | None:
        """Normalize a baud rate value or code into a protocol baud code."""
        if baud_rate in BAUD_RATE_TO_CODE:
            return BAUD_RATE_TO_CODE[baud_rate]
        if baud_rate in CODE_TO_BAUD_RATE:
            return baud_rate
        return None

    @staticmethod
    def _coerce_enum_value(
        value: int | EnumValue, enum_type: type[EnumValue]
    ) -> int | None:
        """Validate an integer-like value against an enum type."""
        try:
            return int(enum_type(value))
        except ValueError:
            return None
