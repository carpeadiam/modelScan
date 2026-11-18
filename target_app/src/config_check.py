"""Fails (exit 2) when required runtime configuration is missing."""
import os
import sys


def main() -> int:
    value = os.environ.get("APP_CONFIG", "")
    if not value:
        print("ERROR: required environment variable APP_CONFIG is empty or unset", file=sys.stderr)
        return 2
    print(f"APP_CONFIG present ({len(value)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
