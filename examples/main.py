"""Minimal command-line example for reading one sensor measurement."""

import logging

from xkc_kl200_python import XkcKl200

_LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Read and display one distance measurement."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with XkcKl200(port="/dev/ttyUSB0") as sensor:
        _LOGGER.info("Distance: %s mm", sensor.read_distance())


if __name__ == "__main__":
    main()
