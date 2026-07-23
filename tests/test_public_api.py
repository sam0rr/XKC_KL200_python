"""Tests for the supported typed package interface."""

import importlib.util

import xkc_kl200_python
from xkc_kl200_python import config, constants, errors, sensor


def test_package_exports_are_exact_and_sorted() -> None:
    """Expose exactly the documented high-level API."""
    assert xkc_kl200_python.__all__ == [
        "CommunicationMode",
        "LedMode",
        "RelayMode",
        "SensorConfig",
        "XkcKl200",
        "XkcKl200ReadError",
        "XkcKl200ResponseError",
        "XkcKl200Status",
        "XkcKl200TimeoutError",
    ]


def test_public_modules_declare_exact_interfaces() -> None:
    """Keep each importable public module limited to supported names."""
    assert config.__all__ == ["SensorConfig"]
    assert constants.__all__ == [
        "CommunicationMode",
        "LedMode",
        "RelayMode",
        "XkcKl200Status",
    ]
    assert errors.__all__ == [
        "XkcKl200ReadError",
        "XkcKl200ResponseError",
        "XkcKl200TimeoutError",
    ]
    assert sensor.__all__ == ["XkcKl200"]


def test_internal_module_paths_are_explicitly_private() -> None:
    """Ship underscored internals without retaining the old module paths."""
    assert importlib.util.find_spec("xkc_kl200_python._protocol") is not None
    assert importlib.util.find_spec("xkc_kl200_python._serial_manager") is not None
    assert importlib.util.find_spec("xkc_kl200_python.serial_manager") is None
    assert importlib.util.find_spec("xkc_kl200_python.utils") is None
