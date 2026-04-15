# XKC KL200 Python

A simplified, typed, and testable Python library for controlling the `XKC-KL200-2M-UART` laser distance sensor over a serial connection.

This repository follows the same library architecture style as `cubemars_servo_can`: modern `pyproject.toml` packaging, `src` layout, strict typing, mock-based tests, and lightweight documentation.

## Key Features

- Typed API for sensor control and distance reads.
- Structured modules for config, protocol constants, serial transport, state, and utilities.
- No hardware required for tests because the serial link is mocked.
- `uv`, `black`, `ruff`, `mypy`, and `pytest` ready from the start.

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

### Raspberry Pi Notes

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
    sensor.set_upload_mode(False)
    distance_mm = sensor.read_distance()
    print(f"Distance: {distance_mm} mm")
```

For continuous mode:

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/serial0", baudrate=9600) as sensor:
    sensor.set_upload_mode(True)
    sensor.set_upload_interval(10)

    while True:
        if sensor.process_auto_data():
            print(sensor.get_distance())
```

If you are not using the Raspberry Pi UART header and instead use a USB-to-UART adapter, replace `/dev/serial0` with the matching device such as `/dev/ttyUSB0`.

### 3. Upgrade

Update to the latest repository version:

```bash
# If managed in a uv project dependency:
uv add --upgrade git+https://github.com/sam0rr/XKC_KL200_python.git

# If installed with pip:
pip install --upgrade git+https://github.com/sam0rr/XKC_KL200_python.git
```

## Documentation

- [Usage Guide](docs/usage.md)
- [Configuration Guide](docs/configuration.md)

## Project Structure

```text
.
├── src/
│   └── xkc_kl200_python/
│       ├── __init__.py
│       ├── sensor.py
│       ├── serial_manager.py
│       ├── sensor_state.py
│       ├── config.py
│       ├── constants.py
│       ├── utils.py
│       └── py.typed
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_serial_manager.py
│   ├── test_sensor_init_modes.py
│   ├── test_sensor_reading.py
│   └── test_utils.py
├── docs/
│   ├── usage.md
│   └── configuration.md
└── examples/
    └── main.py
```

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
