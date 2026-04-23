from xkc_kl200_python import XKC_KL200


def main() -> None:
    with XKC_KL200(port="/dev/ttyUSB0") as sensor:
        print(f"Distance: {sensor.read_distance()} mm")


if __name__ == "__main__":
    main()
