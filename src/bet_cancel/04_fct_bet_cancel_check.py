"""Read-only verification of existing bet_cancel Gold artifacts."""
import argparse

from gold_pipeline import verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    verify()
