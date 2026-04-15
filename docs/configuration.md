# Configuration Guide

## SensorConfig

`SensorConfig` stores the serial connection parameters used by the library:

```python
from xkc_kl200_python import SensorConfig, XKC_KL200

config = SensorConfig(
    port="/dev/ttyUSB0",
    baudrate=9600,
    timeout=1.0,
    address=0xFFFF,
    startup_delay_s=0.1,
)

sensor = XKC_KL200(config=config)
```

## Supported Baud Rates

The protocol exposes the following baud rates:

- `2400`
- `4800`
- `9600`
- `14400`
- `19200`
- `38400`
- `56000`
- `57600`
- `115200`
- `128000`

`change_baud_rate` accepts either a baud-rate code (`0` to `9`) or one of the actual baud-rate values listed above.

## Notes

- `address=0xFFFF` is the default broadcast-style device address used by the original sensor examples.
- `change_address` only accepts values from `0x0000` to `0xFFFE`.
- `set_upload_interval` accepts values from `1` to `100`.
