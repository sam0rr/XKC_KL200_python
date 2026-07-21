"""Protocol constants and small enums for the XKC-KL200 UART interface."""

from enum import IntEnum

# Fixed frame layout values shared by command and measurement packets.
FRAME_LENGTH = 9
COMMAND_HEADER = 0x62
SYSTEM_HEADER = 0x61
DEFAULT_SENSOR_ADDRESS = 0xFFFF

# Command identifiers used by the device protocol.
READ_DISTANCE_COMMAND = 0x33
CHANGE_BAUD_RATE_COMMAND = 0x30
CHANGE_ADDRESS_COMMAND = 0x32
SET_LED_MODE_COMMAND = 0x37
SET_RELAY_MODE_COMMAND = 0x38
RESET_COMMAND = 0x39
SET_COMMUNICATION_MODE_COMMAND = 0x30

MIN_ADDRESS = 0x0000
MAX_ADDRESS = 0xFFFE

# Supported baud-rate mappings between user values and protocol codes.
BAUD_RATE_TO_CODE = {
    2400: 0,
    4800: 1,
    9600: 2,
    14400: 3,
    19200: 4,
    38400: 5,
    56000: 6,
    57600: 7,
    115200: 8,
    128000: 9,
}

CODE_TO_BAUD_RATE = {code: baudrate for baudrate, code in BAUD_RATE_TO_CODE.items()}


class XKC_KL200_Status(IntEnum):
    """Protocol-level status codes returned by the library API."""

    SUCCESS = 0
    INVALID_PARAMETER = 1
    TIMEOUT = 2
    CHECKSUM_ERROR = 3
    RESPONSE_ERROR = 4


class LedMode(IntEnum):
    """Supported LED behavior modes."""

    ON_WHEN_DETECTED = 0
    OFF_WHEN_DETECTED = 1
    ALWAYS_OFF = 2
    ALWAYS_ON = 3


class RelayMode(IntEnum):
    """Supported relay output modes."""

    ACTIVE_WHEN_DETECTED = 0
    INACTIVE_WHEN_DETECTED = 1


class CommunicationMode(IntEnum):
    """High-level communication operating modes."""

    RELAY = 0
    UART = 1
