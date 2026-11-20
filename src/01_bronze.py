"""원천을 읽기 전용으로 Parquet에 보존하고 KST 출처 두 컬럼과 수집 이력을 기록합니다."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import quote
import uuid

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import CONFIG, PROJECT_ROOT, DATETIME_FORMAT, BronzeConfig, FileRule

KST = timezone(timedelta(hours=9), name="KST")
SUPPORTED = {".csv", ".tsv", ".jsonl", ".xlsx", ".xlsm", ".parquet"}


def now_kst() -> str:
    return datetime.now(KST).strftime(DATETIME_FORMAT)


def absolute(path: Path) -> Path:
    return (PROJECT_ROOT / path).resolve()


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_columns(table: pa.Table, rule: FileRule) -> pa.Table:
    if rule.usecols is None:
        return table
    if len(set(rule.usecols)) != len(rule.usecols):
        raise ValueError("읽을 열 목록에 중복이 있습니다.")
    return table.select(list(rule.usecols))


def read_tables(path: Path, rule: FileRule):
    """행 필터/정렬/날짜 파싱/공백 제거/NULL 치환 없이 읽습니다."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        # CSV에는 타입 정보가 없으므로 숫자 추론 없이 원문 문자열을 보존합니다.
        delimiter = "\t" if suffix == ".tsv" else rule.delimiter
        with path.open(encoding=rule.encoding, newline="") as stream:
            reader = csv.reader(stream, delimiter=delimiter, strict=True)
            header = next(reader)
            if len(header) != len(set(header)) or any(name == "" for name in header):
                raise ValueError("빈 컬럼명 또는 중복 컬럼명: 자동 변경 없이 중단합니다.")
            for row_number, row in enumerate(reader, 2):
                if len(row) != len(header):
                    raise ValueError(f"CSV {row_number}행의 열 수가 헤더와 다릅니다.")
        frame = pd.read_csv(
            path, encoding=rule.encoding,
            sep=delimiter,
            dtype=str, na_filter=False, keep_default_na=False,
            skip_blank_lines=False, on_bad_lines="error",
        )
        if frame.columns.duplicated().any():
            raise ValueError("중복 컬럼은 손실 없이 변환할 수 없습니다.")
        yield None, pa.Table.from_pandas(frame, preserve_index=False)
    elif suffix in {".xlsx", ".xlsm"}:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            sheets = workbook.sheet_names if rule.sheet_names is None else rule.sheet_names
            for sheet in sheets:
                name = workbook.sheet_names[sheet] if isinstance(sheet, int) else sheet
                frame = pd.read_excel(workbook, sheet_name=name, header=rule.header,
                                      dtype=object, na_filter=False, keep_default_na=False)
                yield name, pa.Table.from_pandas(frame, preserve_index=False)
    elif suffix == ".jsonl":
        # json_normalize를 사용하지 않음: 중첩 필드는 struct/list로 유지합니다.
        records = []
        with path.open(encoding=rule.encoding) as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    raise ValueError(f"JSONL {line_number}행이 비어 있습니다.")
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"JSONL {line_number}행은 객체여야 합니다.")
                records.append(record)
        # from_pylist의 첫 행 기반 컬럼 추론으로 뒤쪽 필드가 유실되지 않도록 함.
        keys = list(dict.fromkeys(key for record in records for key in record))
        yield None, pa.table({key: pa.array([r.get(key) for r in records]) for key in keys})
    elif suffix == ".parquet":
        yield None, pq.read_table(path)


def plan(config: BronzeConfig):
    source = absolute(config.source_root)
    output = absolute(config.output_root)
    manifest = absolute(config.manifest_path)
    if not source.is_dir():
        raise ValueError(f"입력 폴더가 없습니다: {source}")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("입력·출력 폴더는 서로 겹칠 수 없습니다.")
    if manifest == source or source in manifest.parents:
        raise ValueError("수집 이력은 원천 폴더 밖에 저장해야 합니다.")
    inputs = {}
    for rule in config.rules:
        matches = sorted(p for p in source.glob(rule.pattern)
                         if p.is_file() and p.suffix.lower() in SUPPORTED
                         and not p.name.startswith("~$"))
        if not matches:
            raise ValueError(f"설정과 일치하는 지원 파일이 없습니다: {rule.pattern}")
        for path in matches:
            if source not in path.resolve().parents:
                raise ValueError(f"원천 폴더 밖의 경로는 허용하지 않습니다: {path}")
            if path in inputs:
                raise ValueError(f"여러 규칙이 같은 파일과 일치합니다: {path}")
            inputs[path] = rule
    jobs = []
    targets = set()
    for path, rule in sorted(inputs.items()):
        relative = path.relative_to(source)
        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            with pd.ExcelFile(path, engine="openpyxl") as workbook:
                selected = workbook.sheet_names if rule.sheet_names is None else rule.sheet_names
                sheets = [workbook.sheet_names[s] if isinstance(s, int) else s for s in selected]
                if not sheets or any(s not in workbook.sheet_names for s in sheets):
                    raise ValueError(f"시트 설정을 확인하세요: {path}")
            destinations = [(sheet, output / relative.with_suffix("") /
                             (quote(sheet, safe="") + ".parquet")) for sheet in sheets]
        else:
            destinations = [(None, output / relative.with_suffix(".parquet"))]
        for sheet, destination in destinations:
            resolved = destination.resolve()
            if output not in resolved.parents or resolved == manifest:
                raise ValueError(f"잘못된 저장 경로: {destination}")
            if resolved in targets:
                raise ValueError(f"출력 파일 경로 충돌: {destination}")
            targets.add(resolved)
            jobs.append((path, rule, sheet, destination))
    if any(a in b.parents or b in a.parents for a in targets for b in targets if a != b):
        raise ValueError("출력 파일과 폴더 경로가 충돌합니다.")
    return jobs


def collection_times(manifest: Path) -> dict:
    """같은 파일 내용/시트의 최초 성공 수집 시각을 재사용합니다."""
    times = {}
    if manifest.exists():
        with manifest.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("status") in {"written", "unchanged"}:
                    key = (record["source_path"], record["source_sha256"], record["sheet_name"])
                    times.setdefault(key, record.get("data_ingested_at", record["ingested_at"]))
    return times


def run(config: BronzeConfig = CONFIG) -> list[dict]:
    jobs = plan(config)
    manifest = absolute(config.manifest_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    results = []
    first_collection = collection_times(manifest)
    for source, rule, sheet, destination in jobs:
        record = dict(run_id=run_id, source_path=str(source.resolve()),
                      source_relative_path=source.relative_to(absolute(config.source_root)).as_posix(),
                      sheet_name=sheet, output_path=str(destination),
                      timezone="KST", utc_offset="+09:00", ingested_at=now_kst(),
                      selected_columns=None if rule.usecols is None else list(rule.usecols))
        temporary = None
        try:
            before = sha256(source)
            record["source_sha256"] = before
            effective = replace(rule, sheet_names=(sheet,)) if sheet is not None else rule
            _, original = next(read_tables(source, effective))
            source_table = select_columns(original, rule)
            provenance_columns = (config.source_file_column, config.ingested_at_column)
            if len(set(provenance_columns)) != 2 or any(not name for name in provenance_columns):
                raise ValueError("출처 컬럼 이름은 서로 다른 비어 있지 않은 이름이어야 합니다.")
            if any(name in original.column_names for name in provenance_columns):
                raise ValueError("출처 컬럼 이름이 원천 컬럼과 충돌합니다. config.py에서 변경하세요.")
            collection_key = (record["source_path"], before, sheet)
            data_ingested_at = first_collection.get(collection_key, record["ingested_at"])
            table = source_table.append_column(
                config.source_file_column, pa.array([source.name] * source_table.num_rows, type=pa.string())
            ).append_column(
                config.ingested_at_column, pa.array([data_ingested_at] * source_table.num_rows, type=pa.string())
            )
            record.update(data_ingested_at=data_ingested_at,
                          provenance_columns=list(provenance_columns))
            record.update(source_rows=original.num_rows, source_columns=original.column_names)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
            pq.write_table(table, temporary, compression=config.compression)
            restored = pq.read_table(temporary)
            if not restored.equals(table) or restored.num_rows != original.num_rows:
                raise ValueError("Parquet 왕복 검증 실패: 행 수 또는 원천 값이 다릅니다.")
            if not restored.select(source_table.column_names).equals(source_table):
                raise ValueError("원천 컬럼 값 보존 검증 실패")
            if sha256(source) != before:
                raise ValueError("읽는 동안 원천 파일이 변경되었습니다.")
            digest = sha256(temporary)
            if destination.exists() and sha256(destination) == digest:
                status = "unchanged"
            else:
                temporary.replace(destination)
                status = "written"
            record.update(status=status, saved_at=now_kst(), bronze_rows=restored.num_rows,
                          row_count_match=True, values_match=True, output_sha256=digest,
                          output_columns=restored.column_names)
        except Exception as exc:
            record.update(status="failed", failed_at=now_kst(), error=f"{type(exc).__name__}: {exc}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        with manifest.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        if record["status"] != "failed":
            first_collection.setdefault(collection_key, data_ingested_at)
        results.append(record)
        print(f"{record['status']}: {record['source_relative_path']} -> {destination}")
    failures = [r for r in results if r["status"] == "failed"]
    if failures:
        raise RuntimeError(f"{len(failures)}건 실패. 수집 이력 확인: {manifest}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--manifest-path", type=Path)
    args = parser.parse_args()
    overrides = {key: value for key, value in vars(args).items() if value is not None}
    run(replace(CONFIG, **overrides))


if __name__ == "__main__":
    main()
