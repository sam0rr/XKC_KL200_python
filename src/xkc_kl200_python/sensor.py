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
    FRAME_LENGTH,
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
    XKC_KL200_Error,
)
from .serial_manager import SerialFactory, SerialManager
from .utils import build_command_frame, parse_frame, parse_measurement_frame

EnumValue = TypeVar("EnumValue", bound=int)


class XKC_KL200:
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

    def __enter__(self) -> "XKC_KL200":
        """Support ``with XKC_KL200(...)`` context management."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the serial connection when leaving a context manager."""
        self.close()

    def close(self) -> None:
        """Close the underlying serial connection."""
        self._serial_manager.close()

    @property
    def address(self) -> int:
        """Return the most recently acknowledged or measured sensor address."""
        return self._address

    def hard_reset(self) -> XKC_KL200_Error:
        """Request a factory reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFE,
        )

    def soft_reset(self) -> XKC_KL200_Error:
        """Request a user-settings reset on the sensor."""
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFD,
        )

    def change_address(self, address: int) -> XKC_KL200_Error:
        """Change the sensor address if the requested value is valid."""
        if not MIN_ADDRESS <= address <= MAX_ADDRESS:
            return XKC_KL200_Error.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_ADDRESS_COMMAND,
            data_high=(address >> 8) & 0xFF,
            data_low=address & 0xFF,
        )
        if result == XKC_KL200_Error.SUCCESS:
            self.config.address = address
            self._address = address
        return result

    def change_baud_rate(self, baud_rate: int) -> XKC_KL200_Error:
        """Change the sensor baud rate using a baud value or protocol code."""
        baud_code = self._resolve_baud_rate_code(baud_rate)
        if baud_code is None:
            return XKC_KL200_Error.INVALID_PARAMETER

        result = self._send_ack_command(
            command=CHANGE_BAUD_RATE_COMMAND,
            data_low=baud_code,
        )
        if result == XKC_KL200_Error.SUCCESS:
            new_baudrate = CODE_TO_BAUD_RATE[baud_code]
            self.config.baudrate = new_baudrate
            self._serial_manager.set_baudrate(new_baudrate)
        return result

    def set_led_mode(self, mode: int | LedMode) -> XKC_KL200_Error:
        """Configure the sensor LED behavior."""
        value = self._coerce_enum_value(mode, LedMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_LED_MODE_COMMAND,
            data_low=value,
        )

    def set_relay_mode(self, mode: int | RelayMode) -> XKC_KL200_Error:
        """Configure the relay output behavior."""
        value = self._coerce_enum_value(mode, RelayMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_RELAY_MODE_COMMAND,
            data_low=value,
        )

    def set_communication_mode(self, mode: int | CommunicationMode) -> XKC_KL200_Error:
        """Switch the device between relay mode and UART mode."""
        value = self._coerce_enum_value(mode, CommunicationMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            header=SYSTEM_HEADER,
            command=SET_COMMUNICATION_MODE_COMMAND,
            data_low=value,
        )

    def read_distance(self, timeout: float | None = None) -> int:
        """Request one distance measurement and return the latest known value."""
        self._serial_manager.write_frame(
            build_command_frame(
                header=COMMAND_HEADER,
                command=READ_DISTANCE_COMMAND,
                address=self.config.address,
            )
        )

        response = self._serial_manager.read_exact(
            FRAME_LENGTH, self.config.timeout if timeout is None else timeout
        )
        if response is None:
            return self._last_received_distance_mm

        try:
            address, distance_mm = parse_measurement_frame(response)
        except ValueError:
            return self._last_received_distance_mm

        self._last_received_distance_mm = distance_mm
        self._address = address
        return distance_mm

    @property
    def last_received_distance(self) -> int:
        """Return the latest received distance."""
        return self._last_received_distance_mm

    def _send_ack_command(
        self,
        *,
        command: int,
        header: int = COMMAND_HEADER,
        data_high: int = 0,
        data_low: int = 0,
        tail: int = 0,
    ) -> XKC_KL200_Error:
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
        return self._wait_for_response(expected_command=command)

    def _wait_for_response(self, expected_command: int) -> XKC_KL200_Error:
        """Read and classify the acknowledgement for a configuration command."""
        response = self._serial_manager.read_exact(FRAME_LENGTH, self.config.timeout)
        if response is None:
            return XKC_KL200_Error.TIMEOUT

        try:
            parsed = parse_frame(response, expected_command=expected_command)
        except ValueError as exc:
            if "checksum" in str(exc).lower():
                return XKC_KL200_Error.CHECKSUM_ERROR
            return XKC_KL200_Error.RESPONSE_ERROR

        self._address = parsed.address
        return XKC_KL200_Error.SUCCESS

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
