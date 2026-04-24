# XKC KL200 Python

---

A simplified, typed, and testable Python library for controlling the `XKC-KL200-2M-UART` laser distance sensor over a serial connection.

---

## Key Features

- Typed API for sensor control and distance reads.
- Straightforward request/response serial flow.
- No hardware required for tests because the serial link is mocked.
- `uv`, `black`, `ruff`, `mypy`, and `pytest` ready from the start.

---

## Quick Start

### 1. Install

Install directly from the repository using `uv` or `pip`:

```bash
# Add as a dependency to your project (uv)
uv add git+https://github.com/sam0rr/XKC_KL200_python.git

# Install into the current Python environment (pip)
pip install git+https://github.com/sam0rr/XKC_KL200_python.git
```

### 2. Run

#### Raspberry Pi Notes

For Raspberry Pi, the recommended UART device is usually `/dev/serial0`.

Before running the library on a Pi:

- enable the hardware UART
- disable the Linux serial console on that UART
- make sure the sensor is using `UART` communication mode
- make sure the sensor UART level is compatible with the Pi `3.3V` UART pins
- connect `TX -> RX`, `RX -> TX`, and `GND -> GND`

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/serial0", baudrate=9600) as sensor:
    distance_mm = sensor.read_distance()
    print(f"Distance: {distance_mm} mm")
```

If you want continuous data, loop in your own application:

```python
import time

from xkc_kl200_python import XKC_KL200, XKC_KL200_ReadError

with XKC_KL200(port="/dev/serial0", baudrate=9600) as sensor:
    while True:
        try:
            print(sensor.read_distance())
        except XKC_KL200_ReadError:
            print("Read failed")
        time.sleep(0.1)
```

This library intentionally does not expose an upload mode.

That was a deliberate design choice to keep the serial contract simple and
reliable: one command, one response, one parsed measurement. Supporting sensor
driven upload frames added buffer management, frame resynchronization, and
interleaving between measurements and command acknowledgements. For repeated
measurements, it is simpler and safer for the application to own the loop and
call `read_distance()` each time.

`read_distance()` is the fresh-read API. It raises on timeout or invalid sensor
responses instead of silently returning cached data. If you want the last known
successful value, read `last_received_distance` explicitly.

If you are not using the Raspberry Pi UART header and instead use a USB-to-UART adapter, replace `/dev/serial0` with the matching device such as `/dev/ttyUSB0`.

### Raspberry Pi Multi-Sensor Setup

This project has also been validated with the [XKC-KL200 Laser Distance Measurement Sensor](https://www.xkc-sensor.com/detail/1449.html) in a Raspberry Pi setup that uses:

- `UART1`, `UART2`, `UART3`, and `UART5` for four sensors
- `SPI0` for an `MCP2515` CAN controller
- no `UART4`, because it conflicts with the SPI0 pin block in this wiring layout

For the UART-capable XKC-KL200 family, the sensor wiring used in this setup is:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> Raspberry Pi `RX`
- `Black` -> Raspberry Pi `TX`

The active `/boot/firmware/config.txt` overlay block is:

```ini
[all]
dtoverlay=disable-bt
enable_uart=1
dtoverlay=uart2
dtoverlay=uart3
dtoverlay=uart5
```

In this four-sensor Raspberry Pi deployment, the active UART mapping is:

- `UART1` -> `GPIO14 / GPIO15`
- `UART2` -> `GPIO0 / GPIO1`
- `UART3` -> `GPIO4 / GPIO5`
- `UART5` -> `GPIO12 / GPIO13`

Typical device names for those UARTs are:

- `/dev/ttyAMA0`
- `/dev/ttyAMA2`
- `/dev/ttyAMA3`
- `/dev/ttyAMA5`

The full wiring and overlay reference is documented in [docs/configuration.md](docs/configuration.md). Raspberry Pi overlay behavior is described in the [official configuration documentation](https://www.raspberrypi.com/documentation/computers/configuration.html).

### 3. Upgrade

Update to the latest repository version:

```bash
# If managed in a uv project dependency:
uv add --upgrade git+https://github.com/sam0rr/XKC_KL200_python.git

# If installed with pip:
pip install --upgrade git+https://github.com/sam0rr/XKC_KL200_python.git
```

---

## Documentation

- [Usage Guide](docs/usage.md)
- [Configuration Guide](docs/configuration.md)

---

## Development

To contribute to this library:

1. Clone the repository:

```bash
git clone https://github.com/sam0rr/XKC_KL200_python.git
cd XKC_KL200_python
```

2. Install dependencies:

```bash
uv sync
```

3. Run formatting and linting:

```bash
uv run black .
uv run ruff check .
```

4. Run type checks:

```bash
uv run mypy
```

5. Run tests:

```bash
uv run pytest
```

---
