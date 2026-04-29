"""High-level request/response wrapper for the XKC-KL200 UART sensor."""

import time
from typing import TypeVar

from .config import SensorConfig
from .constants import (
    BAUD_RATE_TO_CODE,
    CHANGE_ADDRESS_COMMAND,
    CHANGE_BAUD_RATE_COMMAND,
    CODE_TO_BAUD_RATE,
    COMMAND_HEADER,
    CommunicationMode,
    LedMode,
    MAX_ADDRESS,
    MIN_ADDRESS,
    READ_DISTANCE_COMMAND,
    RESET_COMMAND,
    RelayMode,
    SET_COMMUNICATION_MODE_COMMAND,
    SET_LED_MODE_COMMAND,
    SET_RELAY_MODE_COMMAND,
    SYSTEM_HEADER,
    XKC_KL200_Status,
)
from .errors import XKC_KL200_ResponseError, XKC_KL200_TimeoutError
from .serial_manager import SerialFactory, SerialManager
from .utils import build_command_frame, parse_frame, parse_measurement_frame

EnumValue = TypeVar("EnumValue", bound=int)


# Keep the public API focused on direct command/response interactions.
class XKC_KL200:
    """High-level interface for controlling an XKC-KL200 UART sensor."""

    # Build the runtime state once and open the serial transport immediately.
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

    # Allow callers to use the sensor object in a context manager.
    def __enter__(self) -> "XKC_KL200":
        """Support ``with XKC_KL200(...)`` context management."""
        return self

    # Always close the port when the context manager exits.
    def __exit__(self, *_: object) -> None:
        """Close the serial connection when leaving a context manager."""
        self.close()

    # Expose an explicit manual close for non-context-manager use.
    def close(self) -> None:
        """Close the underlying serial connection."""
        self._serial_manager.close()

    # Surface the most recently acknowledged or measured device address.
    @property
    def address(self) -> int:
        """Return the most recently acknowledged or measured sensor address."""
        return self._address

    # Send the factory-reset command variant.
    def hard_reset(self) -> XKC_KL200_Status:
        """Request a factory reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFE,
        )

    # Send the user-settings-reset command variant.
    def soft_reset(self) -> XKC_KL200_Status:
        """Request a user-settings reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFD,
        )

    # Persist a new sensor address once the device acknowledges the change.
    def change_address(self, address: int) -> XKC_KL200_Status:
        """Change the sensor address if the requested value is valid."""
        if not MIN_ADDRESS <= address <= MAX_ADDRESS:
            return XKC_KL200_Status.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_ADDRESS_COMMAND,
            data_high=(address >> 8) & 0xFF,
            data_low=address & 0xFF,
        )
        if result == XKC_KL200_Status.SUCCESS:
            self.config.address = address
            self._address = address
        return result

    # Accept either a baud-rate value or the raw protocol baud code.
    def change_baud_rate(self, baud_rate: int) -> XKC_KL200_Status:
        """Change the sensor baud rate using a baud value or protocol code."""
        baud_code = self._resolve_baud_rate_code(baud_rate)
        if baud_code is None:
            return XKC_KL200_Status.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_BAUD_RATE_COMMAND,
            data_low=baud_code,
        )
        if result == XKC_KL200_Status.SUCCESS:
            new_baudrate = CODE_TO_BAUD_RATE[baud_code]
            self.config.baudrate = new_baudrate
            self._serial_manager.set_baudrate(new_baudrate)
        return result

    # Validate and forward the requested LED mode.
    def set_led_mode(self, mode: int | LedMode) -> XKC_KL200_Status:
        """Configure the sensor LED behavior."""
        value = self._coerce_enum_value(mode, LedMode)
        if value is None:
            return XKC_KL200_Status.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_LED_MODE_COMMAND,
            data_low=value,
        )

    # Validate and forward the requested relay-output mode.
    def set_relay_mode(self, mode: int | RelayMode) -> XKC_KL200_Status:
        """Configure the relay output behavior."""
        value = self._coerce_enum_value(mode, RelayMode)
        if value is None:
            return XKC_KL200_Status.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_RELAY_MODE_COMMAND,
            data_low=value,
        )

    # Validate and forward the overall communication operating mode.
    def set_communication_mode(self, mode: int | CommunicationMode) -> XKC_KL200_Status:
        """Switch the device between relay mode and UART mode."""
        value = self._coerce_enum_value(mode, CommunicationMode)
        if value is None:
            return XKC_KL200_Status.INVALID_PARAMETER
        return self._send_ack_command(
            header=SYSTEM_HEADER,
            command=SET_COMMUNICATION_MODE_COMMAND,
            data_low=value,
        )

    # Request one fresh measurement frame and cache the successful result.
    def read_distance(self, timeout: float | None = None) -> int:
        """Request one fresh distance measurement.

        Raises:
            XKC_KL200_TimeoutError: The sensor did not reply before the timeout.
            XKC_KL200_ResponseError: The reply frame was malformed or unexpected.
        """
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
            if status == XKC_KL200_Status.TIMEOUT:
                raise XKC_KL200_TimeoutError(
                    "Timed out waiting for a measurement frame"
                )
            raise XKC_KL200_ResponseError("Received an invalid measurement frame")

        address, distance_mm = parse_measurement_frame(response)

        self._last_received_distance_mm = distance_mm
        self._address = address
        return distance_mm

    # Expose the last successful measurement without triggering new I/O.
    @property
    def last_received_distance(self) -> int:
        """Return the latest received distance."""
        return self._last_received_distance_mm

    # Build and send a command frame, then wait for its acknowledgement.
    def _send_ack_command(
        self,
        *,
        command: int,
        header: int = COMMAND_HEADER,
        data_high: int = 0,
        data_low: int = 0,
        tail: int = 0,
    ) -> XKC_KL200_Status:
        """Send a command frame and wait for its acknowledgement."""
        frame = build_command_frame(
            header=header,
            command=command,
            address=self.config.address,
            data_high=data_high,
            data_low=data_low,
            tail=tail,
        )
        self._serial_manager.write_frame(frame)
        return self._wait_for_response(expected_header=header, expected_command=command)

    # Parse the next response frame as an acknowledgement for one command.
    def _wait_for_response(
        self,
        *,
        expected_header: int = COMMAND_HEADER,
        expected_command: int,
    ) -> XKC_KL200_Status:
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
        return XKC_KL200_Status.SUCCESS

    # Normalize user-facing baud-rate inputs into the protocol code space.
    @staticmethod
    def _resolve_baud_rate_code(baud_rate: int) -> int | None:
        """Normalize a baud rate value or code into a protocol baud code."""
        if baud_rate in BAUD_RATE_TO_CODE:
            return BAUD_RATE_TO_CODE[baud_rate]
        if baud_rate in CODE_TO_BAUD_RATE:
            return baud_rate
        return None

    # Reuse one small validator for the different command enums.
    @staticmethod
    def _coerce_enum_value(
        value: int | EnumValue, enum_type: type[EnumValue]
    ) -> int | None:
        """Validate an integer-like value against an enum type."""
        try:
            return int(enum_type(value))
        except ValueError:
            return None
