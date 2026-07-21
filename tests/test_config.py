"""Configuration validation tests for the simplified sensor config object."""

import pytest

from xkc_kl200_python.config import SensorConfig


def test_default_config_is_valid() -> None:
    """Verify that the default config values match the expected library defaults."""
    config = SensorConfig(port="/dev/ttyUSB0")

    assert config.baudrate == 9600
    assert config.timeout == 1.0
    assert config.address == 0xFFFF


def test_invalid_baudrate_raises() -> None:
    """Verify that unsupported baud rates fail early during config validation."""
    with pytest.raises(ValueError, match="Unsupported baudrate"):
        SensorConfig(port="/dev/ttyUSB0", baudrate=12345)


def test_invalid_address_raises() -> None:
    """Verify that addresses outside the protocol range are rejected."""
    with pytest.raises(ValueError, match="address must be"):
        SensorConfig(port="/dev/ttyUSB0", address=0x10000)


def test_negative_timeout_raises() -> None:
    """Verify that negative timeouts are rejected."""
    with pytest.raises(ValueError, match="timeout must be >= 0"):
        SensorConfig(port="/dev/ttyUSB0", timeout=-1.0)


def test_empty_port_raises() -> None:
    """Verify that callers must provide a real port string."""
    with pytest.raises(ValueError, match="port must be a non-empty string"):
        SensorConfig(port="")


def test_negative_startup_delay_raises() -> None:
    """Verify that the optional startup delay cannot be negative."""
    with pytest.raises(ValueError, match="startup_delay_s must be >= 0"):
        SensorConfig(port="/dev/ttyUSB0", startup_delay_s=-0.1)
