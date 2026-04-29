"""Transport-level tests for the simplified serial manager."""

from conftest import FakeSerial, FakeSerialFactory
from pytest import MonkeyPatch

from xkc_kl200_python.constants import XKC_KL200_Status
from xkc_kl200_python.config import SensorConfig
from xkc_kl200_python.serial_manager import SerialManager, default_serial_factory
from xkc_kl200_python.utils import build_command_frame


# Verify that frame writes pass straight through to the serial backend.
def test_write_frame(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]

    manager.write_frame(b"\x01\x02")

    assert serial_port.written_frames == [b"\x01\x02"]


# Verify that the default serial factory wires through to pyserial.
def test_default_serial_factory_uses_serial_module(monkeypatch: MonkeyPatch) -> None:
    fake_serial = FakeSerial(port="/dev/null", baudrate=9600, timeout=1.0)

    def fake_constructor(
        port: str,
        baudrate: int,
        timeout: float,
        exclusive: bool,
    ) -> FakeSerial:
        assert port == "/dev/ttyUSB0"
        assert baudrate == 9600
        assert timeout == 1.0
        assert exclusive is True
        return fake_serial

    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.serial.Serial", fake_constructor
    )

    result = default_serial_factory("/dev/ttyUSB0", 9600, 1.0)

    assert result is fake_serial


# Verify that open-state reporting follows the underlying port lifecycle.
def test_close_and_is_open(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )

    assert manager.is_open is True

    manager.close()

    assert manager.is_open is False


# Verify that an empty read with pending bytes still times out cleanly.
def test_read_frame_handles_empty_read_with_waiting(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]

    monkeypatch.setattr(type(serial_port), "in_waiting", property(lambda self: 1))
    monkeypatch.setattr(serial_port, "read", lambda size=1: b"")

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.TIMEOUT


# Verify that the timeout loop sleeps briefly before giving up.
def test_read_frame_sleeps_before_timeout(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    sleep_calls: list[float] = []
    monotonic_values = iter([0.0, 0.0, 0.002])

    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.time.sleep",
        lambda duration: sleep_calls.append(duration),
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.001)

    assert result is None
    assert status == XKC_KL200_Status.TIMEOUT
    assert sleep_calls == [0.001]


# Verify that read_frame resynchronizes after leading junk bytes.
def test_read_frame_skips_leading_junk(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        b"\x00"
        + build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            data_low=17,
        )
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.01)

    assert result == build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=17,
    )
    assert status == XKC_KL200_Status.SUCCESS


# Verify that helper resynchronization keeps a partial header candidate for later bytes.
def test_extract_frame_keeps_partial_header_after_leading_junk(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    manager._buffer.extend(b"\x00\x62")

    result, status, consumed_data = manager._extract_frame(
        allow_header_mismatch_skip=False,
        expected_header=None,
        expected_command=0x33,
    )

    assert result is None
    assert status is None
    assert consumed_data is True
    assert manager._buffer == bytearray(b"\x62")


# Verify that read_frame waits for the length byte before deciding.
def test_read_frame_waits_for_frame_prefix(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    serial_port.queue_read(frame[:2])
    serial_port.queue_read(frame[2:])

    result, status = manager.read_frame(expected_command=0x33, timeout=0.01)

    assert result == frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a zero-timeout read still drains already-buffered split chunks.
def test_read_frame_zero_timeout_drains_buffered_chunks(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    serial_port.queue_read(frame[:2])
    serial_port.queue_read(frame[2:])

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result == frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that read_frame waits for the rest of a partial frame payload.
def test_read_frame_waits_for_partial_frame(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    serial_port.queue_read(frame[:5])
    serial_port.queue_read(frame[5:])

    result, status = manager.read_frame(expected_command=0x33, timeout=0.01)

    assert result == frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that read_frame rejects invalid frame lengths and keeps scanning.
def test_read_frame_skips_invalid_length_then_recovers(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(b"\x62\x33\x08")
    serial_port.queue_read(
        build_command_frame(
            header=0x62,
            command=0x33,
            address=0xFFFF,
            data_low=18,
        )
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.01)

    assert result == build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=18,
    )
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a complete malformed frame reports a response error after resync fails.
def test_read_frame_invalid_length_reports_response_error(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(b"\x62\x33\x08\xff\xff\x00\x00\x00\x00")

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.RESPONSE_ERROR


# Verify that checksum failures are reported when no good frame follows.
def test_read_frame_checksum_error(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.CHECKSUM_ERROR


# Verify that a bad frame does not discard a valid reply already buffered behind it.
def test_read_frame_recovers_from_checksum_error_with_buffered_valid_reply(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    valid_frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=22,
    )
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00]) + valid_frame
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result == valid_frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a malformed frame does not fail early while a valid reply is still in flight.
def test_read_frame_waits_through_interframe_gap_after_checksum_error(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    valid_frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=24,
    )
    sleep_calls: list[float] = []
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
    )

    def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        if len(sleep_calls) == 1:
            serial_port.queue_read(valid_frame)

    monkeypatch.setattr("xkc_kl200_python.serial_manager.time.sleep", fake_sleep)

    result, status = manager.read_frame(expected_command=0x33, timeout=0.01)

    assert result == valid_frame
    assert status == XKC_KL200_Status.SUCCESS
    assert sleep_calls == [0.001]


# Verify that a bad frame can recover using a valid reply read immediately afterward.
def test_read_frame_recovers_from_checksum_error_with_next_ready_chunk(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    valid_frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=24,
    )
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
    )
    serial_port.queue_read(valid_frame)

    result, status = manager.read_frame(expected_command=0x33, timeout=1.0)

    assert result == valid_frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that malformed frames still surface as errors once the timeout window closes.
def test_read_frame_returns_deferred_checksum_error_at_timeout(
    serial_factory: FakeSerialFactory, monkeypatch: MonkeyPatch
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    sleep_calls: list[float] = []
    monotonic_values = iter([0.0, 0.0, 0.002])
    serial_port.queue_read(
        bytes([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x00])
    )
    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.time.sleep",
        lambda duration: sleep_calls.append(duration),
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.001)

    assert result is None
    assert status == XKC_KL200_Status.CHECKSUM_ERROR
    assert sleep_calls == []


# Verify that a complete reply with a corrupted header is not misreported as a timeout.
def test_read_frame_invalid_header_reports_response_error(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x60, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x58])
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.RESPONSE_ERROR


# Verify that a wrong-header reply for a unique command is reported as malformed.
def test_read_frame_wrong_header_for_unique_command_reports_response_error(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x61, command=0x33, address=0xFFFF)
    )

    result, status = manager.read_frame(
        expected_header=0x62,
        expected_command=0x33,
        timeout=0.01,
    )

    assert result is None
    assert status == XKC_KL200_Status.RESPONSE_ERROR


# Verify that replies with the right command byte but wrong header are skipped only when requested.
def test_read_frame_matches_expected_header_and_command_for_ambiguous_opcode(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    expected_frame = build_command_frame(header=0x61, command=0x30, address=0xFFFF)
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x30, address=0xFFFF)
    )
    serial_port.queue_read(expected_frame)

    result, status = manager.read_frame(
        allow_header_mismatch_skip=True,
        expected_header=0x61,
        expected_command=0x30,
        timeout=0.01,
    )

    assert result == expected_frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a checksum-valid overlapped candidate does not discard the real reply.
def test_read_frame_resynchronizes_within_checksum_valid_mismatched_candidate(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    expected_frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0x0102,
        data_high=0x03,
        data_low=0x04,
        tail=0x05,
    )
    serial_port.queue_read(bytes([0x61, 0x30, 0x09]) + expected_frame)

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result == expected_frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a stale frame consumed after timeout does not hide a buffered valid reply.
def test_read_frame_zero_timeout_rescans_buffer_after_skipping_stale_frame(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    expected_frame = build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF) + expected_frame
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result == expected_frame
    assert status == XKC_KL200_Status.SUCCESS


# Verify that a bad checksum is reported even when the command byte is corrupted.
def test_read_frame_reports_checksum_error_for_corrupted_command(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        bytes([0x62, 0x39, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.CHECKSUM_ERROR


# Verify that wrong-command frames are ignored and still end in timeout.
def test_read_frame_unexpected_command_error(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )

    result, status = manager.read_frame(expected_command=0x33, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.TIMEOUT


# Verify that stale queued frames cannot extend a zero-timeout read.
def test_read_frame_honors_deadline_while_draining_stale_frames(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x39, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x35, address=0xFFFF)
    )
    serial_port.queue_read(
        build_command_frame(header=0x62, command=0x33, address=0xFFFF)
    )

    result, status = manager.read_frame(expected_command=0x34, timeout=0.0)

    assert result is None
    assert status == XKC_KL200_Status.TIMEOUT


# Verify that a partial timed-out frame is discarded before the next request.
def test_read_frame_clears_partial_buffer_on_timeout(
    serial_factory: FakeSerialFactory,
) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    frame = build_command_frame(
        header=0x62,
        command=0x33,
        address=0xFFFF,
        data_low=19,
    )
    serial_port.queue_read(frame[:2])

    timed_out_result, timed_out_status = manager.read_frame(
        expected_command=0x33,
        timeout=0.0,
    )

    serial_port.queue_read(frame[2:])
    next_result, next_status = manager.read_frame(
        expected_command=0x33,
        timeout=0.0,
    )

    assert timed_out_result is None
    assert timed_out_status == XKC_KL200_Status.TIMEOUT
    assert next_result is None
    assert next_status == XKC_KL200_Status.TIMEOUT
