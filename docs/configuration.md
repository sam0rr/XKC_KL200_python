# Configuration Guide

---

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

---

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

---

## Notes

- `address=0xFFFF` is the default broadcast-style device address used by the original sensor examples.
- `change_address` only accepts values from `0x0000` to `0xFFFE`.
- `set_upload_interval` accepts values from `1` to `100`.

---

## Raspberry Pi Multi-Sensor Wiring

This setup uses the [XKC-KL200 Laser Distance Measurement Sensor](https://www.xkc-sensor.com/detail/1449.html). The manufacturer states that this product supports multiple output modes, including `UART` serial output, and links a separate UART manual for the UART-capable version.

---

## Hardware Used

The Raspberry Pi configuration described here uses:

- `UART1`, `UART2`, `UART3`, and `UART5`
- `SPI0` for the `MCP2515` CAN controller
- no `UART4`

Raspberry Pi documents the `uart2`, `uart3`, and `uart5` overlays on supported boards in its [configuration documentation](https://www.raspberrypi.com/documentation/computers/configuration.html).

---

## Why UART4 Is Not Used

The `MCP2515` CAN controller is connected over `SPI0`. In this Raspberry Pi wiring setup, `SPI0` occupies the same pin block needed for `UART4`, so both are not used together. The active UART selection is therefore:

- `UART1`
- `UART2`
- `UART3`
- `UART5`

---

## Sensor Wire Meaning

For the UART-capable XKC-KL200 family, the wiring used in this setup is:

- `Brown` = `VCC`
- `Blue` = `GND`
- `Yellow` = sensor signal output
- `Black` = sensor `RXD`

In practice for Raspberry Pi wiring, this becomes:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> Raspberry Pi `RX`
- `Black` -> Raspberry Pi `TX`

---

## Power And Logic Level

The XKC product page lists an operating voltage of `DC 5-24V`. In this setup:

- sensor power = `5V`
- sensor ground = `GND`
- Raspberry Pi UART logic remains `3.3V`

---

## config.txt Overlays

The active `/boot/firmware/config.txt` block is:

```ini
[all]
dtoverlay=disable-bt
enable_uart=1
dtoverlay=uart2
dtoverlay=uart3
dtoverlay=uart5
```

Meaning of each line:

- `enable_uart=1` enables serial and UART support
- `dtoverlay=uart2` enables `UART2`
- `dtoverlay=uart3` enables `UART3`
- `dtoverlay=uart5` enables `UART5`

---

## UART Mapping On Raspberry Pi

The active UART mapping is:

- `UART1` -> `GPIO14 / GPIO15`
- `UART2` -> `GPIO0 / GPIO1`
- `UART3` -> `GPIO4 / GPIO5`
- `UART5` -> `GPIO12 / GPIO13`

---

## Extension HAT Label Notes

Some extension HATs do not label these pins as `TXD2`, `RXD2`, `TXD3`, and so on. Instead, they expose the original GPIO labels:

- `UART1`: `TXD` = `TXD1`, `RXD` = `RXD1`
- `UART2`: `ID_SD` = `GPIO0` = `TXD2`, `ID_SC` = `GPIO1` = `RXD2`
- `UART3`: `IO4` = `GPIO4` = `TXD3`, `IO5` = `GPIO5` = `RXD3`
- `UART5`: `IO12` = `GPIO12` = `TXD5`, `IO13` = `GPIO13` = `RXD5`

---

## Full Wiring For Four Sensors

Sensor 1 on `UART1`:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> `RXD`
- `Black` -> `TXD`

Sensor 2 on `UART2`:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> `ID_SC`
- `Black` -> `ID_SD`

Sensor 3 on `UART3`:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> `IO5`
- `Black` -> `IO4`

Sensor 4 on `UART5`:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> `IO13`
- `Black` -> `IO12`

---

## Simple Color Summary

For every sensor:

- `Brown` -> `5V`
- `Blue` -> `GND`
- `Yellow` -> Pi `RX`
- `Black` -> Pi `TX`

---

## Shared Power

All sensors can share the same power rails:

- all `Brown` wires -> `5V`
- all `Blue` wires -> `GND`

The UART signal wires must remain separate for each sensor.

---

## Multi-Sensor Port Mapping

In a four-sensor Raspberry Pi deployment, each sensor can be opened on its own UART device:

- Sensor 1 -> `/dev/ttyAMA0`
- Sensor 2 -> `/dev/ttyAMA2`
- Sensor 3 -> `/dev/ttyAMA3`
- Sensor 4 -> `/dev/ttyAMA5`

The sensor sends serial data to the Raspberry Pi over the `yellow` wire, and the Raspberry Pi sends commands back over the `black` wire.

---
