"""Configuration validation tests for the simplified sensor config object."""

import pytest

from xkc_kl200_python.config import SensorConfig


# Verify that the default config values match the expected library defaults.
def test_default_config_is_valid() -> None:
    config = SensorConfig(port="/dev/ttyUSB0")

    assert config.baudrate == 9600
    assert config.timeout == 1.0
    assert config.address == 0xFFFF


# Verify that unsupported baud rates fail early during config validation.
def test_invalid_baudrate_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported baudrate"):
        SensorConfig(port="/dev/ttyUSB0", baudrate=12345)


# Verify that addresses outside the protocol range are rejected.
def test_invalid_address_raises() -> None:
    with pytest.raises(ValueError, match="address must be"):
        SensorConfig(port="/dev/ttyUSB0", address=0x10000)


# Verify that negative timeouts are rejected.
def test_negative_timeout_raises() -> None:
    with pytest.raises(ValueError, match="timeout must be >= 0"):
        SensorConfig(port="/dev/ttyUSB0", timeout=-1.0)


# Verify that callers must provide a real port string.
def test_empty_port_raises() -> None:
    with pytest.raises(ValueError, match="port must be a non-empty string"):
        SensorConfig(port="")


# Verify that the optional startup delay cannot be negative.
def test_negative_startup_delay_raises() -> None:
    with pytest.raises(ValueError, match="startup_delay_s must be >= 0"):
        SensorConfig(port="/dev/ttyUSB0", startup_delay_s=-0.1)
