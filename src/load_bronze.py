"""Load CSV and JSONL origin files into string-typed Bronze Parquet files."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as arrow
import pyarrow.parquet as parquet


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGIN_DIR = PROJECT_ROOT / "data" / "00_origin"
BRONZE_DIR = PROJECT_ROOT / "data" / "01_bronze"
MANIFEST_PATH = BRONZE_DIR / "_load_manifest.json"
META_DIR = PROJECT_ROOT / "meta"
CHANGE_LOG_PATH = META_DIR / "bronze_change_log.csv"
METADATA_COLUMNS = ("_SRC_FILE", "_LOAD_DTM")
CHANGE_LOG_FIELDS = [
    "RUN_DTM_KST",
    "STAGE",
    "SRC_FILE",
    "INPUT_FILE",
    "OUTPUT_FILE",
    "INPUT_ROWS",
    "OUTPUT_ROWS",
    "INPUT_COLUMNS",
    "OUTPUT_COLUMNS",
    "ADDED_COLUMNS",
    "REMOVED_COLUMNS",
    "CHANGE_DETAIL",
]


def json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def append_change_record(
    *,
    source_files: list[str],
    input_file: str,
    output_file: str,
    input_rows: int,
    output_rows: int,
    input_columns: list[str],
    output_columns: list[str],
    detail: str,
) -> None:
    input_column_set = set(input_columns)
    output_column_set = set(output_columns)
    record = {
        "RUN_DTM_KST": datetime.now().astimezone().isoformat(timespec="seconds"),
        "STAGE": "BRONZE",
        "SRC_FILE": json_list(source_files),
        "INPUT_FILE": input_file,
        "OUTPUT_FILE": output_file,
        "INPUT_ROWS": input_rows,
        "OUTPUT_ROWS": output_rows,
        "INPUT_COLUMNS": json_list(input_columns),
        "OUTPUT_COLUMNS": json_list(output_columns),
        "ADDED_COLUMNS": json_list(
            [column for column in output_columns if column not in input_column_set]
        ),
        "REMOVED_COLUMNS": json_list(
            [column for column in input_columns if column not in output_column_set]
        ),
        "CHANGE_DETAIL": detail,
    }

    META_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    if CHANGE_LOG_PATH.exists():
        with CHANGE_LOG_PATH.open("r", encoding="utf-8-sig", newline="") as log_file:
            reader = csv.DictReader(log_file)
            if reader.fieldnames != CHANGE_LOG_FIELDS:
                raise ValueError(
                    f"Unexpected columns in change log {CHANGE_LOG_PATH}: "
                    f"{reader.fieldnames}"
                )
            rows.extend(reader)
    rows.append(record)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=META_DIR,
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(temporary_file, fieldnames=CHANGE_LOG_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, CHANGE_LOG_PATH)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"sources": {}}

    with MANIFEST_PATH.open("r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest.get("sources"), dict):
        raise ValueError(f"Invalid source manifest: {MANIFEST_PATH}")
    return manifest


def save_manifest(manifest: dict[str, Any]) -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=BRONZE_DIR,
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(manifest, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, MANIFEST_PATH)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def read_csv_as_strings(path: Path) -> pd.DataFrame:
    options = {
        "dtype": str,
        "keep_default_na": False,
        "na_filter": False,
        "low_memory": False,
    }
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **options)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949", **options)


def json_value_as_string(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def read_jsonl_as_strings(path: Path) -> pd.DataFrame:
    records: list[dict[str, str]] = []
    columns: list[str] = []
    seen_columns: set[str] = set()

    with path.open("r", encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path} at line {line_number}: {error}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object in {path} at line {line_number}"
                )

            string_record: dict[str, str] = {}
            for column, value in record.items():
                column_name = str(column)
                if column_name not in seen_columns:
                    seen_columns.add(column_name)
                    columns.append(column_name)
                string_record[column_name] = json_value_as_string(value)
            records.append(string_record)

    return pd.DataFrame(records, columns=columns, dtype=str).fillna("")


def load_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_as_strings(path)
    if suffix == ".jsonl":
        return read_jsonl_as_strings(path)
    raise ValueError(f"Unsupported origin file type: {path}")


def write_parquet_atomically(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            suffix=".tmp.parquet",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        frame.to_parquet(temporary_path, engine="pyarrow", index=False)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def validate_parquet(output_path: Path, expected_rows: int) -> None:
    parquet_file = parquet.ParquetFile(output_path)
    actual_rows = parquet_file.metadata.num_rows
    non_string_columns = [
        field.name
        for field in parquet_file.schema_arrow
        if not (
            arrow.types.is_string(field.type)
            or arrow.types.is_large_string(field.type)
        )
    ]
    if actual_rows != expected_rows:
        raise ValueError(
            f"Row count mismatch for {output_path}: "
            f"expected {expected_rows}, found {actual_rows}"
        )
    if non_string_columns:
        raise TypeError(
            f"Non-string Parquet columns in {output_path}: "
            f"{', '.join(non_string_columns)}"
        )


def main() -> None:
    if not ORIGIN_DIR.is_dir():
        raise FileNotFoundError(f"Origin directory not found: {ORIGIN_DIR}")

    source_files = sorted(
        (
            path
            for path in ORIGIN_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in {".csv", ".jsonl"}
        ),
        key=lambda path: path.relative_to(ORIGIN_DIR).as_posix().casefold(),
    )
    if not source_files:
        raise FileNotFoundError(f"No CSV or JSONL files found under {ORIGIN_DIR}")

    output_sources: dict[str, str] = {}
    for source_path in source_files:
        relative_source = source_path.relative_to(ORIGIN_DIR).as_posix()
        relative_output = Path(relative_source).with_suffix(".parquet").as_posix()
        if relative_output in output_sources:
            raise ValueError(
                f"Output collision: {output_sources[relative_output]} and "
                f"{relative_source} both map to {relative_output}"
            )
        output_sources[relative_output] = relative_source

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    source_history: dict[str, Any] = manifest["sources"]

    for source_path in source_files:
        relative_source = source_path.relative_to(ORIGIN_DIR).as_posix()
        relative_output = Path(relative_source).with_suffix(".parquet")
        output_path = BRONZE_DIR / relative_output
        source_hash = sha256_file(source_path)
        previous = source_history.get(relative_source, {})

        if previous.get("sha256") == source_hash and previous.get("load_dtm"):
            load_dtm = previous["load_dtm"]
        else:
            load_dtm = datetime.now().astimezone().isoformat(timespec="seconds")

        frame = load_source(source_path)
        input_columns = frame.columns.tolist()
        reserved_columns = set(METADATA_COLUMNS).intersection(frame.columns)
        if reserved_columns:
            raise ValueError(
                f"Source file {relative_source} uses reserved columns: "
                f"{', '.join(sorted(reserved_columns))}"
            )

        # Confirm the source did not change while it was being read.
        if sha256_file(source_path) != source_hash:
            raise RuntimeError(f"Origin file changed while loading: {relative_source}")

        frame["_SRC_FILE"] = relative_source
        frame["_LOAD_DTM"] = load_dtm
        frame = frame.astype("string")
        write_parquet_atomically(frame, output_path)
        validate_parquet(output_path, expected_rows=len(frame))

        source_history[relative_source] = {
            "sha256": source_hash,
            "output_file": relative_output.as_posix(),
            "row_count": int(len(frame)),
            "load_dtm": load_dtm,
        }
        save_manifest(manifest)
        append_change_record(
            source_files=[relative_source],
            input_file=f"data/00_origin/{relative_source}",
            output_file=f"data/01_bronze/{relative_output.as_posix()}",
            input_rows=len(frame),
            output_rows=int(len(frame)),
            input_columns=input_columns,
            output_columns=frame.columns.tolist(),
            detail=(
                "CSV/JSONL 값을 문자열로 유지하고 Parquet으로 적재; "
                "_SRC_FILE 및 _LOAD_DTM 추적 컬럼 추가"
            ),
        )
        print(f"{relative_source}: {len(frame)} rows -> {relative_output.as_posix()}")


if __name__ == "__main__":
    main()
