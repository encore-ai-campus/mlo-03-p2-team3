"""Read-only full value/schema/hash/audit verification of existing Gold."""
import argparse
from gold_pipeline import ROOT, verify

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--meta-root',type=str,default=str(ROOT/'meta'))
    verify(parser.parse_args().meta_root)
