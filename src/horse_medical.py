"""Load and standardize the team's HR_VET_HIST dataset."""

import argparse
import csv
import hashlib
import io
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("data/00_origin/horse/HR_VET_HIST.csv")
BRONZE = Path("data/01_bronze/HR_VET_HIST_RAW.parquet")
MANIFEST = Path("data/01_bronze/HR_VET_HIST_LOAD.json")
SILVER_HISTORY = Path("data/02_silver/HR_VET_HIST.parquet")
SILVER_BRIDGE = Path("data/02_silver/HR_VET_TYPE_BRIDGE.parquet")
SOURCE_COLUMNS = {"VET_DT_RAW", "HR_NAME", "TR_GRP_NO", "VET_PLACE_NM", "VET_NM_RAW", "REPORT_DT"}
KST = timezone(timedelta(hours=9), "KST")
HISTORY_SCHEMA = pa.schema([
    pa.field("VET_SEQ", pa.int32(), nullable=False),
    ("VET_DT", pa.date32()),
    ("HR_NM", pa.string()),
    ("TR_GRP_NO", pa.string()),
    ("VET_PLACE_NM", pa.string()),
    ("VET_NM", pa.string()),
    ("REPORT_DT", pa.date32()),
])
BRIDGE_SCHEMA = pa.schema([
    pa.field("VET_SEQ", pa.int32(), nullable=False),
    pa.field("VET_TYPE_NM", pa.string(), nullable=False),
])


def read_source(content: bytes) -> pa.Table:
    reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, [])
    if len(header) != len(SOURCE_COLUMNS) or set(header) != SOURCE_COLUMNS:
        raise ValueError("[VET-BR-01] Source CSV does not have the six expected columns.")

    columns = {name: [] for name in header}
    for record in reader:
        if len(record) != len(header):
            raise ValueError(f"[VET-BR-01] Invalid field count at CSV line {reader.line_num}.")
        for name, value in zip(header, record):
            columns[name].append(value)
    schema = pa.schema([(name, pa.string()) for name in header])
    return pa.Table.from_pydict(columns, schema=schema)


@contextmanager
def temporary_path(directory: Path):
    with NamedTemporaryFile(dir=directory, delete=False) as stream:
        path = Path(stream.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def load_bronze(root: Path = ROOT) -> dict:
    content = (root / SOURCE).read_bytes()
    source = read_source(content)
    output = root / BRONZE
    output.parent.mkdir(parents=True, exist_ok=True)

    with temporary_path(output.parent) as parquet_temp, temporary_path(output.parent) as manifest_temp:
        pq.write_table(source, parquet_temp)
        bronze = pq.read_table(parquet_temp)
        if not source.equals(bronze):
            raise ValueError("[VET-BR-01] Bronze rows, columns or values differ from the source.")

        manifest = {
            "SOURCE_FILE": SOURCE.as_posix(),
            "SOURCE_SHA256": hashlib.sha256(content).hexdigest(),
            "BRONZE_FILE": BRONZE.as_posix(),
            "BRONZE_SHA256": hashlib.sha256(parquet_temp.read_bytes()).hexdigest(),
            "LOAD_DTM_KST": datetime.now(KST).isoformat(timespec="seconds"),
            "ORIGIN_ROWS": source.num_rows,
            "BRONZE_ROWS": bronze.num_rows,
            "ORIGIN_COLUMNS": source.num_columns,
            "BRONZE_COLUMNS": bronze.num_columns,
            "COLUMN_MAPPINGS": [
                {"SOURCE_COLUMN": name, "BRONZE_COLUMN": name, "PARQUET_TYPE": "STRING", "VALUE_RULE": "PRESERVE"}
                for name in source.column_names
            ],
            "VALIDATION": {"DECISION_ID": "VET-BR-01", "SOURCE_BRONZE_EQUAL": True},
        }
        manifest_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        parquet_temp.replace(output)
        manifest_temp.replace(root / MANIFEST)
    return manifest


def standard_text(value: str) -> str | None:
    value = value.strip()
    return None if not value or set(value) == {"-"} else value


def standard_date(value: str, date_format: str, sequence: int, column: str):
    text = standard_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.strptime(text, date_format)
        if parsed.strftime(date_format) != text:
            raise ValueError("Date format differs.")
    except ValueError as error:
        raise ValueError(f"[VET-SL-02] Invalid {column} at VET_SEQ={sequence}.") from error
    return parsed.date()


def build_silver(root: Path = ROOT) -> dict[str, int]:
    raw_bronze = (root / BRONZE).read_bytes()
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if hashlib.sha256(raw_bronze).hexdigest() != manifest["BRONZE_SHA256"]:
        raise ValueError("[VET-SL-01] Bronze Parquet does not match the load record.")
    bronze = pq.read_table(pa.BufferReader(raw_bronze))
    if (
        bronze.num_rows != manifest["ORIGIN_ROWS"]
        or set(bronze.column_names) != SOURCE_COLUMNS
        or any(field.type != pa.string() for field in bronze.schema)
    ):
        raise ValueError("[VET-SL-01] Bronze schema or row count is invalid.")

    history_rows = []
    bridge_rows = []
    multi_name_rows = 0
    for sequence, raw in enumerate(bronze.to_pylist(), start=1):
        group = standard_text(raw["TR_GRP_NO"])
        if group is not None and len(group) > 2:
            raise ValueError(f"[VET-SL-02] TR_GRP_NO exceeds two characters at VET_SEQ={sequence}.")
        vet_name = standard_text(raw["VET_NM_RAW"])
        history_rows.append({
            "VET_SEQ": sequence,
            "VET_DT": standard_date(raw["VET_DT_RAW"], "%Y.%m.%d", sequence, "VET_DT_RAW"),
            "HR_NM": standard_text(raw["HR_NAME"]),
            "TR_GRP_NO": group,
            "VET_PLACE_NM": standard_text(raw["VET_PLACE_NM"]),
            "VET_NM": vet_name,
            "REPORT_DT": standard_date(raw["REPORT_DT"], "%Y%m%d", sequence, "REPORT_DT"),
        })
        labels = [label for part in (vet_name or "").split(",") if (label := standard_text(part)) is not None]
        multi_name_rows += len(labels) > 1
        bridge_rows.extend({"VET_SEQ": sequence, "VET_TYPE_NM": label} for label in labels)

    history = pa.Table.from_pylist(history_rows, schema=HISTORY_SCHEMA)
    bridge = pa.Table.from_pylist(bridge_rows, schema=BRIDGE_SCHEMA)
    if history.num_rows != bronze.num_rows:
        raise ValueError("[VET-SL-01] Bronze and Silver history row counts differ.")

    silver_dir = (root / SILVER_HISTORY).parent
    silver_dir.mkdir(parents=True, exist_ok=True)
    with temporary_path(silver_dir) as history_temp, temporary_path(silver_dir) as bridge_temp:
        pq.write_table(history, history_temp)
        pq.write_table(bridge, bridge_temp)
        if not history.equals(pq.read_table(history_temp)) or not bridge.equals(pq.read_table(bridge_temp)):
            raise ValueError("[VET-SL-01] Silver output differs from the validated tables.")
        history_temp.replace(root / SILVER_HISTORY)
        bridge_temp.replace(root / SILVER_BRIDGE)
    return {"HR_VET_HIST": history.num_rows, "HR_VET_TYPE_BRIDGE": bridge.num_rows, "MULTI_VET_NAME_ROWS": multi_name_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("bronze", "silver", "all"))
    stage = parser.parse_args().stage
    if stage in ("bronze", "all"):
        result = load_bronze()
        print(f"Origin to Bronze: {result['BRONZE_ROWS']:,} rows, {result['BRONZE_COLUMNS']} columns")
        print(f"Load record: {MANIFEST.as_posix()}")
    if stage in ("silver", "all"):
        for name, rows in build_silver().items():
            print(f"{name}: {rows:,}")


if __name__ == "__main__":
    main()
