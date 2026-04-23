from conftest import FakeSerial, FakeSerialFactory
from pytest import MonkeyPatch

from xkc_kl200_python.config import SensorConfig
from xkc_kl200_python.serial_manager import SerialManager, default_serial_factory


def test_write_frame(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]

    manager.write_frame(b"\x01\x02")

    assert serial_port.written_frames == [b"\x01\x02"]


def test_read_exact_success(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )
    serial_port = serial_factory.holder["serial"]
    serial_port.queue_read(b"\x01")
    serial_port.queue_read(b"\x02\x03")

    result = manager.read_exact(3, timeout=0.01)

    assert result == b"\x01\x02\x03"


def test_read_exact_timeout(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )

    result = manager.read_exact(1, timeout=0.0)

    assert result is None


def test_default_serial_factory_uses_serial_module(monkeypatch: MonkeyPatch) -> None:
    fake_serial = FakeSerial(port="/dev/null", baudrate=9600, timeout=1.0)

    def fake_constructor(port: str, baudrate: int, timeout: float) -> FakeSerial:
        assert port == "/dev/ttyUSB0"
        assert baudrate == 9600
        assert timeout == 1.0
        return fake_serial

    monkeypatch.setattr(
        "xkc_kl200_python.serial_manager.serial.Serial", fake_constructor
    )

    result = default_serial_factory("/dev/ttyUSB0", 9600, 1.0)

    assert result is fake_serial


def test_close_discard_and_is_open(serial_factory: FakeSerialFactory) -> None:
    manager = SerialManager(
        config=SensorConfig(port="/dev/ttyUSB0"),
        serial_factory=serial_factory,
    )

    assert manager.is_open is True

    manager.close()

    assert manager.is_open is False


def test_read_exact_sleeps_before_timeout(
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

    result = manager.read_exact(1, timeout=0.001)

    assert result is None
    assert sleep_calls == [0.001]
