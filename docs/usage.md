# Usage Guide

## Basic Initialization

```python
from xkc_kl200_python import XKC_KL200

sensor = XKC_KL200(port="/dev/serial0", baudrate=9600)
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

## Manual Distance Read

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/serial0", baudrate=9600) as sensor:
    sensor.set_upload_mode(False)
    print(sensor.read_distance())
```

## Automatic Upload Mode

```python
from xkc_kl200_python import XKC_KL200

with XKC_KL200(port="/dev/serial0", baudrate=9600) as sensor:
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
