# Usage Guide

## Basic Initialization

```python
from xkc_kl200_python import XKC_KL200

sensor = XKC_KL200(port="/dev/ttyUSB0")
```

The default connection settings are:

- Baud rate: `9600`
- Timeout: `1.0` second
- Address: `0xFFFF`

## Manual Distance Read

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/ttyUSB0") as sensor:
    sensor.set_upload_mode(False)
    print(sensor.read_distance())
```

## Automatic Upload Mode

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/ttyUSB0") as sensor:
    sensor.set_upload_mode(True)
    sensor.set_upload_interval(5)

    while True:
        if sensor.process_auto_data():
            print(sensor.get_distance())
```

## Configuration Commands

The library exposes helpers for:

- `change_address`
- `change_baud_rate`
- `set_upload_mode`
- `set_upload_interval`
- `set_led_mode`
- `set_relay_mode`
- `set_communication_mode`
- `hard_reset`
- `soft_reset`
