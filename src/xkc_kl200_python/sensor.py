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
    MAX_UPLOAD_INTERVAL,
    MIN_ADDRESS,
    MIN_UPLOAD_INTERVAL,
    READ_DISTANCE_COMMAND,
    RESET_COMMAND,
    RelayMode,
    SET_COMMUNICATION_MODE_COMMAND,
    SET_LED_MODE_COMMAND,
    SET_RELAY_MODE_COMMAND,
    SET_UPLOAD_INTERVAL_COMMAND,
    SET_UPLOAD_MODE_COMMAND,
    SYSTEM_HEADER,
    UploadMode,
    XKC_KL200_Error,
)
from .sensor_state import SensorState
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
        self._state = SensorState(address=config.address)
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

    @property
    def state(self) -> SensorState:
        """Expose the current cached runtime state."""
        return self._state

    def close(self) -> None:
        """Close the underlying serial connection."""
        self._serial_manager.close()

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
            self._state.address = address
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

    def set_upload_mode(self, auto_upload: bool) -> XKC_KL200_Error:
        """Enable or disable automatic measurement uploads."""
        mode = UploadMode.AUTO if auto_upload else UploadMode.MANUAL
        result = self._send_ack_command(
            command=SET_UPLOAD_MODE_COMMAND,
            data_low=int(mode),
        )
        if result == XKC_KL200_Error.SUCCESS:
            self._state.auto_upload_enabled = auto_upload
        return result

    def set_upload_interval(self, interval: int) -> XKC_KL200_Error:
        """Set the automatic upload interval in protocol units."""
        if not MIN_UPLOAD_INTERVAL <= interval <= MAX_UPLOAD_INTERVAL:
            return XKC_KL200_Error.INVALID_PARAMETER
        was_auto_enabled = self._state.auto_upload_enabled
        if was_auto_enabled:
            result = self.set_upload_mode(False)
            if result != XKC_KL200_Error.SUCCESS:
                return result

        result = self._send_ack_command(
            command=SET_UPLOAD_INTERVAL_COMMAND,
            data_low=interval,
        )
        if result != XKC_KL200_Error.SUCCESS:
            if was_auto_enabled:
                restore_result = self.set_upload_mode(True)
                if restore_result != XKC_KL200_Error.SUCCESS:
                    return restore_result
            return result

        if was_auto_enabled:
            return self.set_upload_mode(True)
        return XKC_KL200_Error.SUCCESS

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
        """Read the latest distance in manual or automatic-upload mode."""
        if self._state.auto_upload_enabled:
            return self._read_auto_distance(timeout)

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
            return self._state.last_received_distance_mm

        try:
            address, distance_mm = parse_measurement_frame(response)
        except ValueError:
            return self._state.last_received_distance_mm

        self._state.mark_measurement(distance_mm, address)
        return distance_mm

    def available(self) -> bool:
        """Return True when a fresh measurement is ready to be consumed."""
        if (
            self._state.auto_upload_enabled
            and self._serial_manager.bytes_available >= FRAME_LENGTH
        ):
            return True
        return self._state.available

    def process_auto_data(self) -> bool:
        """Consume one automatic-upload frame if a complete frame is buffered."""
        if not self._state.auto_upload_enabled:
            return False

        while self._serial_manager.bytes_available >= FRAME_LENGTH:
            frame = self._serial_manager.peek(FRAME_LENGTH)
            if len(frame) < FRAME_LENGTH:
                return False

            if not frame or frame[0] not in (COMMAND_HEADER, SYSTEM_HEADER):
                self._serial_manager.discard(1)
                continue

            try:
                address, distance_mm = parse_measurement_frame(frame)
                self._serial_manager.discard(FRAME_LENGTH)
                self._state.mark_measurement(distance_mm, address)
                return True
            except ValueError:
                self._serial_manager.discard(1)
                continue

        return False

    def get_distance(self) -> int:
        """Return the latest distance and clear the available flag."""
        return self._state.consume_distance()

    def get_last_received_distance(self) -> int:
        """Return the latest received distance without changing state flags."""
        return self._state.last_received_distance_mm

    def _read_auto_distance(self, timeout: float | None) -> int:
        """Drain or wait for uploaded measurements and return the latest value."""
        deadline = time.monotonic() + (
            self.config.timeout if timeout is None else timeout
        )

        while True:
            received = False
            while self.process_auto_data():
                received = True

            if received or time.monotonic() >= deadline:
                return self._state.last_received_distance_mm

            time.sleep(0.001)

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
        """Read and classify the next response frame for a command."""
        deadline = time.monotonic() + self.config.timeout
        last_error = XKC_KL200_Error.TIMEOUT

        while True:
            remaining = max(0.0, deadline - time.monotonic())
            response = self._serial_manager.peek(FRAME_LENGTH)

            if len(response) < FRAME_LENGTH:
                # Wait for more data
                if self._serial_manager.read_exact(FRAME_LENGTH, remaining) is None:
                    return last_error
                # Re-peek after read_exact populated the buffer
                response = self._serial_manager.peek(FRAME_LENGTH)

            if not response or response[0] not in (COMMAND_HEADER, SYSTEM_HEADER):
                self._serial_manager.discard(1)
                continue

            try:
                parsed = parse_frame(response)
            except ValueError as exc:
                if "checksum" in str(exc).lower():
                    last_error = XKC_KL200_Error.CHECKSUM_ERROR
                else:
                    last_error = XKC_KL200_Error.RESPONSE_ERROR
                self._serial_manager.discard(1)
                if time.monotonic() >= deadline:
                    return last_error
                continue

            # Found a valid frame
            self._serial_manager.discard(FRAME_LENGTH)

            if parsed.command != expected_command:
                if parsed.command == READ_DISTANCE_COMMAND:
                    distance_mm = (parsed.data_high << 8) | parsed.data_low
                    self._state.mark_measurement(distance_mm, parsed.address)
                last_error = XKC_KL200_Error.RESPONSE_ERROR
                if time.monotonic() >= deadline:
                    return last_error
                continue

            self._state.address = parsed.address
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
