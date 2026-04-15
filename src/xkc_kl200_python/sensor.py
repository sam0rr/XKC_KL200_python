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
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 9600,
        timeout: float = 1.0,
        *,
        config: SensorConfig | None = None,
        serial_factory: SerialFactory | None = None,
    ) -> None:
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
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def state(self) -> SensorState:
        return self._state

    def close(self) -> None:
        self._serial_manager.close()

    def hard_reset(self) -> XKC_KL200_Error:
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFE,
        )

    def soft_reset(self) -> XKC_KL200_Error:
        return self._send_ack_command(
            command=RESET_COMMAND,
            tail=0xFD,
        )

    def change_address(self, address: int) -> XKC_KL200_Error:
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
        mode = UploadMode.AUTO if auto_upload else UploadMode.MANUAL
        result = self._send_ack_command(
            command=SET_UPLOAD_MODE_COMMAND,
            data_low=int(mode),
        )
        if result == XKC_KL200_Error.SUCCESS:
            self._state.auto_upload_enabled = auto_upload
        return result

    def set_upload_interval(self, interval: int) -> XKC_KL200_Error:
        if not MIN_UPLOAD_INTERVAL <= interval <= MAX_UPLOAD_INTERVAL:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_UPLOAD_INTERVAL_COMMAND,
            data_low=interval,
        )

    def set_led_mode(self, mode: int | LedMode) -> XKC_KL200_Error:
        value = self._coerce_enum_value(mode, LedMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_LED_MODE_COMMAND,
            data_low=value,
        )

    def set_relay_mode(self, mode: int | RelayMode) -> XKC_KL200_Error:
        value = self._coerce_enum_value(mode, RelayMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            command=SET_RELAY_MODE_COMMAND,
            data_low=value,
        )

    def set_communication_mode(self, mode: int | CommunicationMode) -> XKC_KL200_Error:
        value = self._coerce_enum_value(mode, CommunicationMode)
        if value is None:
            return XKC_KL200_Error.INVALID_PARAMETER
        return self._send_ack_command(
            header=SYSTEM_HEADER,
            command=SET_COMMUNICATION_MODE_COMMAND,
            data_low=value,
        )

    def read_distance(self, timeout: float | None = None) -> int:
        if self._state.auto_upload_enabled:
            return self._state.last_received_distance_mm

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
        if (
            self._state.auto_upload_enabled
            and self._serial_manager.bytes_available >= FRAME_LENGTH
        ):
            return True
        return self._state.available

    def process_auto_data(self) -> bool:
        if not self._state.auto_upload_enabled:
            return False
        if self._serial_manager.bytes_available < FRAME_LENGTH:
            return False

        response = self._serial_manager.read_exact(FRAME_LENGTH, timeout=0.0)
        if response is None:
            return False

        try:
            address, distance_mm = parse_measurement_frame(response)
        except ValueError:
            if self._serial_manager.bytes_available > 0:
                self._serial_manager.discard(1)
            return False

        self._state.mark_measurement(distance_mm, address)
        return True

    def get_distance(self) -> int:
        return self._state.consume_distance()

    def get_last_received_distance(self) -> int:
        return self._state.last_received_distance_mm

    def _send_ack_command(
        self,
        *,
        command: int,
        header: int = COMMAND_HEADER,
        data_high: int = 0,
        data_low: int = 0,
        tail: int = 0,
    ) -> XKC_KL200_Error:
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
        response = self._serial_manager.read_exact(FRAME_LENGTH, self.config.timeout)
        if response is None:
            return XKC_KL200_Error.TIMEOUT

        try:
            parsed = parse_frame(response, expected_command=expected_command)
        except ValueError as exc:
            if "checksum" in str(exc).lower():
                return XKC_KL200_Error.CHECKSUM_ERROR
            return XKC_KL200_Error.RESPONSE_ERROR

        self._state.address = parsed.address
        return XKC_KL200_Error.SUCCESS

    @staticmethod
    def _resolve_baud_rate_code(baud_rate: int) -> int | None:
        if baud_rate in BAUD_RATE_TO_CODE:
            return BAUD_RATE_TO_CODE[baud_rate]
        if baud_rate in CODE_TO_BAUD_RATE:
            return baud_rate
        return None

    @staticmethod
    def _coerce_enum_value(
        value: int | EnumValue, enum_type: type[EnumValue]
    ) -> int | None:
        try:
            return int(enum_type(value))
        except ValueError:
            return None
