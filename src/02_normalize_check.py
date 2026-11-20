"""Read-only verification of persisted Silver files and source hashes."""
import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("normalize_check_engine", Path(__file__).with_name("02_normalize.py"))
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def verify(meta_root=ROOT/"meta", reference=False):
    meta_root = Path(meta_root)
    report = json.loads((meta_root/"silver_validation.json").read_text(encoding="utf-8"))
    if report["status"] != "passed":
        raise RuntimeError("The last normalization report failed.")
    if report["code_sha256"] != engine.digest(engine.__file__):
        raise RuntimeError("Normalization code changed after the last run; rerun first.")
    root = Path(report["output_root"])
    expected_names = {name+".parquet" for name in report["outputs"]}
    actual_names = {p.name for p in root.rglob("*.parquet") if p.parent==root}
    if actual_names != expected_names or any(p.parent!=root for p in root.rglob("*.parquet")):
        raise RuntimeError("Silver file set/flat layout mismatch")
    tables = {}
    for name,info in report["outputs"].items():
        path = root/(name+".parquet")
        if engine.digest(path) != info["sha256"]:
            raise RuntimeError(f"Output checksum mismatch: {name}")
        table = pq.read_table(path)
        if table.num_rows != info["rows"] or table.column_names != info["columns"]:
            raise RuntimeError(f"Output rows/columns mismatch: {name}")
        tables[name] = table
    audit = engine.Audit()
    audit.dictionary = pd.read_csv(meta_root/"data_dictionary.csv",encoding="utf-8-sig",keep_default_na=False).to_dict("records")
    for row in audit.dictionary:
        for key in ("parse_fail_rows","out_of_code_rows"):
            row[key] = int(row[key])
        if row["standard_column"] in tables[row["table"]].column_names:
            actual = tables[row["table"]].schema.field(row["standard_column"]).type
            if str(actual) != row["standard_type"]:
                raise RuntimeError(f"Dictionary type mismatch: {row['table']}.{row['standard_column']}")
            if tables[row["table"]][row["standard_column"]].null_count != int(row["null_rows"]):
                raise RuntimeError("Dictionary NULL count mismatch")
    checks = engine.check_outputs(tables,report["sources"],audit,reference=reference)
    failures = [c for c in checks if not c["passed"]]
    if failures:
        raise RuntimeError(json.dumps(failures,ensure_ascii=False))
    print(f"Read-only validation passed: {len(tables)} flat files, {len(checks)} checks, dictionary schema/NULL counts, output/source SHA-256.")
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-root",type=Path,default=ROOT/"meta")
    parser.add_argument("--check-reference",action="store_true")
    args = parser.parse_args()
    verify(args.meta_root,args.check_reference)
