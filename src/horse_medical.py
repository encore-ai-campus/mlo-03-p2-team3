"""Run the shared Bronze and Silver pipeline using the existing CLI."""

import argparse
from importlib import import_module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("bronze", "silver", "all"))
    stage = parser.parse_args().stage
    if stage in ("bronze", "all"):
        import_module("01_bronze").main()
    if stage in ("silver", "all"):
        import_module("02_normalize").main()


if __name__ == "__main__":
    main()
