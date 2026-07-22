# Usage Guide

---

## Basic Initialization

```python
"""Initialize an XKC-KL200 sensor connection."""

import logging

from xkc_kl200_python import XkcKl200

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)

with XkcKl200(port="/dev/serial0", baudrate=9600) as sensor:
    _LOGGER.info("Sensor ready at address %#06x", sensor.address)
```

The default connection settings are:

- Baud rate: `9600`
- Timeout: `1.0` second
- Address: `0xFFFF`

On Raspberry Pi, `/dev/serial0` is the recommended UART device in most setups. If you use a USB serial adapter instead, the device will often be something like `/dev/ttyUSB0`.

Before using the library on a Pi:

- enable the hardware UART
- disable the Linux serial console on that UART
- ensure the sensor is in `UART` communication mode
- verify the sensor UART electrical level is compatible with the Pi `3.3V` UART
- wire `TX -> RX`, `RX -> TX`, and `GND -> GND`

---

## Manual Distance Read

```python
"""Read one XKC-KL200 measurement."""

import logging

from xkc_kl200_python import XkcKl200

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)

with XkcKl200(port="/dev/serial0", baudrate=9600) as sensor:
    _LOGGER.info("Distance: %s mm", sensor.read_distance())
```

---

## Looping In Your App

```python
"""Continuously read XKC-KL200 measurements."""

import logging
import time

from xkc_kl200_python import XkcKl200, XkcKl200ReadError

_LOGGER = logging.getLogger(__name__)


def log_distance(sensor: XkcKl200) -> None:
    """Read and log one measurement or the resulting sensor error."""
    try:
        distance_mm = sensor.read_distance()
    except XkcKl200ReadError:
        _LOGGER.exception("Sensor read failed")
    else:
        _LOGGER.info("Distance: %s mm", distance_mm)


logging.basicConfig(level=logging.INFO, format="%(message)s")

with XkcKl200(port="/dev/serial0", baudrate=9600) as sensor:
    while True:
        log_distance(sensor)
        time.sleep(0.1)
```

`read_distance()` always sends a measurement request and waits for the matching
response frame. If that fresh read fails, it raises instead of returning cached
data. If you want repeated readings, keep the loop in your own code.

This library intentionally does not expose an upload mode. The goal is to keep
the UART contract predictable and easy to debug: one command, one response, one
parsed measurement. Repeated reads stay in application code rather than inside
the library.

---

## Configuration Commands

The library exposes helpers for:

- `change_address`
- `change_baud_rate`
- `set_led_mode`
- `set_relay_mode`
- `set_communication_mode`
- `hard_reset`
- `soft_reset`

---
