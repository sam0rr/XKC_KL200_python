from conftest import FakeSerialFactory
from pytest import MonkeyPatch

from xkc_kl200_python import XKC_KL200
from xkc_kl200_python.constants import XKC_KL200_Error
from xkc_kl200_python.utils import ProtocolFrame, build_command_frame


def test_read_distance_updates_state(serial_factory: FakeSerialFactory) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x01, 0x2C, 0x00, 0x75])
    )

    distance = sensor.read_distance()

    assert distance == 300
    assert sensor.available() is True
    assert sensor.get_distance() == 300
    assert sensor.available() is False


def test_read_distance_timeout_returns_last_distance(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    sensor.state.last_received_distance_mm = 123

    assert sensor.read_distance(timeout=0.0) == 123


def test_read_distance_in_auto_mode_drains_uploaded_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )

    distance = sensor.read_distance(timeout=0.0)

    assert distance == 100
    assert sensor.get_last_received_distance() == 100


def test_read_distance_in_auto_mode_waits_for_next_frame(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    sensor.state.last_received_distance_mm = 88
    process_results = iter([False, False, True, False])
    monotonic_values = iter([0.0, 0.0001, 0.0002, 0.0003, 0.0004])

    def fake_process_auto_data() -> bool:
        result = next(process_results)
        if result:
            sensor.state.mark_measurement(144, address=0x0001)
        return result

    monkeypatch.setattr(sensor, "process_auto_data", fake_process_auto_data)
    monkeypatch.setattr(
        "xkc_kl200_python.sensor.time.monotonic", lambda: next(monotonic_values)
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "xkc_kl200_python.sensor.time.sleep", lambda delay: sleep_calls.append(delay)
    )

    distance = sensor.read_distance(timeout=0.01)

    assert distance == 144
    assert sleep_calls == [0.001, 0.001]


def test_process_auto_data_incomplete_frame_returns_false(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_port = serial_factory.holder["serial"]
    # Only 8 bytes
    serial_port.queue_read(bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00]))

    assert sensor.process_auto_data() is False


def test_process_auto_data_invalid_frame_discards_and_returns_false(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    serial_port = serial_factory.holder["serial"]
    # Valid header but invalid checksum
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0xFF])
    )

    assert sensor.process_auto_data() is False
    assert sensor._serial_manager.bytes_available == 8


def test_wait_for_response_incomplete_read_returns_timeout(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    # Only 5 bytes, then timeout
    serial_port.queue_read(bytes([0x62, 0x33, 0x09, 0x00, 0x01]))

    result = sensor._wait_for_response(0x33)
    assert result == XKC_KL200_Error.TIMEOUT


def test_wait_for_response_generic_error_and_deadline(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.0, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]

    # 1. Trigger non-checksum ValueError inside parse_frame
    def mock_parse_frame(
        frame: bytes, expected_command: int | None = None
    ) -> ProtocolFrame:
        raise ValueError("Generic response error")

    monkeypatch.setattr("xkc_kl200_python.sensor.parse_frame", mock_parse_frame)
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )
    assert sensor._wait_for_response(0x33) == XKC_KL200_Error.RESPONSE_ERROR


def test_wait_for_response_peek_after_read_exact_covers_line_313(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)

    peeks = iter(
        [
            bytes([0x62]),
            bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D]),
        ]
    )
    monkeypatch.setattr(sensor._serial_manager, "peek", lambda size: next(peeks))
    monkeypatch.setattr(
        sensor._serial_manager, "read_exact", lambda size, timeout: bytes([0] * size)
    )

    assert sensor._wait_for_response(0x33) == XKC_KL200_Error.SUCCESS


def test_wait_for_response_continue_after_error_covers_line_329(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.05, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]

    # 1. First frame is invalid checksum
    # 2. deadline check fails (time is NOT past deadline)
    # 3. loop continues
    # 4. Second frame is valid

    # Header check is done in wait_for_response before parse_frame.
    # So we need to provide frames with valid headers.

    invalid_frame = bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0xFF])
    valid_frame = bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])

    serial_port.queue_read(invalid_frame + valid_frame)

    # We need enough values for the loop.
    # Each iteration calls time.monotonic() at least once at start of loop.
    # parse_frame block also calls it.
    times = iter([100.0] * 20)
    monkeypatch.setattr("xkc_kl200_python.sensor.time.monotonic", lambda: next(times))

    assert sensor._wait_for_response(0x33) == XKC_KL200_Error.SUCCESS


def test_wait_for_response_command_mismatch_deadline_covers_line_344(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]

    # Send a frame with wrong command
    serial_port.queue_read(
        bytes([0x62, 0x99, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x97])
    )

    times = iter([100.0, 100.0, 101.0])
    monkeypatch.setattr("xkc_kl200_python.sensor.time.monotonic", lambda: next(times))

    assert sensor._wait_for_response(0x33) == XKC_KL200_Error.RESPONSE_ERROR


def test_process_auto_data_short_peek(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    sensor.state.auto_upload_enabled = True
    # bytes_available >= FRAME_LENGTH but peek returns less
    from xkc_kl200_python.serial_manager import SerialManager

    monkeypatch.setattr(SerialManager, "bytes_available", property(lambda self: 10))
    monkeypatch.setattr(
        sensor._serial_manager, "peek", lambda size: bytes([0x62, 0x33])
    )

    assert sensor.process_auto_data() is False


def test_serial_manager_discard_zero_or_negative(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", serial_factory=serial_factory)
    # This should just return without doing anything
    sensor._serial_manager.discard(0)
    sensor._serial_manager.discard(-1)


def test_process_auto_data_reads_measurement(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x34, address=0xFFFF, data_low=1)
    )
    assert sensor.set_upload_mode(True) == XKC_KL200_Error.SUCCESS

    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0x00, 0x01, 0x00, 0x64, 0x00, 0x3D])
    )

    assert sensor.process_auto_data() is True
    assert sensor.get_last_received_distance() == 100


def test_change_baud_rate_accepts_real_baudrate(
    serial_factory: FakeSerialFactory,
) -> None:
    sensor = XKC_KL200(port="/dev/ttyUSB0", timeout=0.01, serial_factory=serial_factory)
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x30, address=0xFFFF, data_low=8)
    )

    result = sensor.change_baud_rate(115200)

    assert result == XKC_KL200_Error.SUCCESS
    assert sensor.config.baudrate == 115200
    assert serial_port.baudrate == 115200
