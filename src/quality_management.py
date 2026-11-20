"""Apply the shared Silver quality rules without modifying Silver inputs.

Run from any directory with ``python src/quality_management.py``.  The script
reads only ``data/02_silver/*.parquet`` and writes deterministic clean/excluded
Parquet files plus append-only CSV audit logs.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DIR = PROJECT_ROOT / "data" / "02_silver"
CLEAN_DIR = SILVER_DIR / "clean"
EXCLUDED_DIR = SILVER_DIR / "_excluded"
META_DIR = PROJECT_ROOT / "meta"
CHANGE_LOG = META_DIR / "dq_change_log.csv"
VALIDATION_LOG = META_DIR / "dq_validation.csv"
REPORT_PATH = PROJECT_ROOT / "docs" / "품질관리.md"

BASE_RULE_ID = "DQ-U01"
BASE_DECISION_ID = "D-001"
LINEAGE_COLUMNS = ["DQ_RULE_ID", "DQ_DECISION_ID", "BRONZE_PATH", "_SRC_ROW_NO"]
BRONZE_FILES = {
    "BET_ORDER": "bet_order.parquet", "BET_TICKET": "bet_ticket.parquet",
    "MBR_MASTER": "MBR_MASTER.parquet", "HR_WEEKLY_SNAPSHOT": "HR_WEEKLY_SNAPSHOT.parquet",
    "TR_WEEKLY_SNAPSHOT": "TR_WEEKLY_SNAPSHOT.parquet", "RC_RACE": "RC_RACE.parquet",
    "RC_ENTRY": "RC_ENTRY.parquet", "RC_ODDS": "RC_ODDS.parquet",
    "RC_RESULT": "RC_RESULT.parquet", "RC_SALES": "RC_SALES.parquet",
    "RC_SALES_TOTAL": "RC_SALES.parquet", "HR_VET_HIST": "HR_VET_HIST.parquet",
    "HR_VET_TYPE_BRIDGE": "HR_VET_HIST.parquet", "RC_CHANGE_EVENT": "race_change_events.parquet",
}

CHANGE_FIELDS = [
    "RUN_DTM_KST", "STAGE", "TABLE_NAME", "INPUT_FILE", "OUTPUT_FILE",
    "INPUT_ROWS", "CLEAN_ROWS", "EXCLUDED_ROWS", "RULE_IDS", "DECISION_IDS",
    "CHANGE_DETAIL",
]
VALIDATION_FIELDS = [
    "RUN_DTM_KST", "TABLE_NAME", "INPUT_ROWS", "CLEAN_ROWS", "EXCLUDED_ROWS",
    "RECONCILED_YN", "ISSUE_ID", "EXPECTED_COUNT", "ACTUAL_COUNT", "MATCH_YN",
    "DETAIL",
]

EXPECTED_ISSUES = {
    "D-002": 1052,
    "D-003": 3632,
    "D-004_TICKET": 1000,
    "D-004_ORDER": 546,
    "D-005": 1560,
    "D-006_HEADER": 93,
    "D-006_ORIG_MISSING": 644,
    "D-007_GROUP_MISMATCH": 11,
    "D-007_NO_SNAPSHOT": 71,
    "D-011": 2,
}


def _is_missing(value: Any) -> bool:
    return value is None or pd.isna(value)


def _normal(value: Any) -> str:
    return "" if _is_missing(value) else str(value).strip()


def _run_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp.parquet", delete=False) as handle:
            temporary = Path(handle.name)
        frame.to_parquet(temporary, index=False, engine="pyarrow")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _append_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    """Append records atomically while preserving prior audit history."""
    META_DIR.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != fields:
                raise ValueError(f"Unexpected columns in {path}: {reader.fieldnames}")
            existing.extend(reader)
    existing.extend({key: str(value) for key, value in row.items()} for row in rows)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8-sig", newline="", dir=META_DIR,
            suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(existing)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_silver() -> dict[str, pd.DataFrame]:
    files = sorted(SILVER_DIR.glob("*.parquet"), key=lambda path: path.name.casefold())
    if not files:
        raise FileNotFoundError(f"No Silver Parquet files found under {SILVER_DIR}")
    return {path.stem: pd.read_parquet(path) for path in files}


def _attach_lineage(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Restore per-source row ordinals from stable Silver row order.

    Silver tables preserve source order.  HR_VET_HIST already has the canonical
    source ordinal as VET_SEQ; its exploded bridge inherits that ordinal.
    """
    result = frame.copy()
    source_file = BRONZE_FILES.get(table)
    if source_file is None:
        raise ValueError(f"No Bronze mapping configured for {table}")
    if "_SRC_FILE" not in result:
        result["_SRC_FILE"] = source_file
    if "_SRC_ROW_NO" in result:
        row_no = pd.to_numeric(result["_SRC_ROW_NO"], errors="raise").astype("int64")
    elif table == "HR_VET_HIST":
        if "VET_SEQ" not in result:
            raise ValueError("HR_VET_HIST has no VET_SEQ")
        row_no = pd.to_numeric(result["VET_SEQ"], errors="raise").astype("int64")
    elif table == "HR_VET_TYPE_BRIDGE":
        row_no = pd.to_numeric(result["VET_SEQ"], errors="raise").astype("int64")
    elif table in {"RC_SALES", "RC_SALES_TOTAL"}:
        bronze_path = PROJECT_ROOT / "data" / "01_bronze" / "race" / "RC_SALES.parquet"
        bronze = pd.read_parquet(bronze_path)
        is_total = bronze["POOL_NM"].astype("string").str.strip().eq("합계")
        selected = is_total if table == "RC_SALES_TOTAL" else ~is_total
        # Recover original source ordinals, including rows routed to the sibling output.
        positions = pd.Series(range(1, len(bronze) + 1), index=bronze.index)
        source_ordinals = bronze.loc[selected].assign(_SRC_ROW_NO=positions.loc[selected])
        row_no = result.groupby("_SRC_FILE", sort=False).cumcount()
        restored: list[int] = []
        for source, group in result.groupby("_SRC_FILE", sort=False):
            ordinals = source_ordinals.loc[source_ordinals["_SRC_FILE"].eq(source), "_SRC_ROW_NO"].tolist()
            if len(ordinals) != len(group):
                raise ValueError(f"{table}: Silver/Bronze source-row mapping does not reconcile for {source}")
            restored.extend(ordinals)
        row_no = pd.Series(restored, index=result.index, dtype="int64")
    else:
        row_no = result.groupby("_SRC_FILE", sort=False).cumcount() + 1
    result["_SRC_ROW_NO"] = row_no.astype("int64")
    result["BRONZE_PATH"] = f"data/01_bronze/{source_file}"
    result["DQ_RULE_ID"] = BASE_RULE_ID
    result["DQ_DECISION_ID"] = BASE_DECISION_ID
    return result


def _write_table(
    table: str,
    clean: pd.DataFrame,
    excluded: pd.DataFrame,
    input_rows: int,
    details: str,
    issue_counts: dict[str, int],
) -> list[dict[str, Any]]:
    clean_path = CLEAN_DIR / f"{table}.parquet"
    excluded_path = EXCLUDED_DIR / f"{table}.parquet"
    _write_parquet(clean, clean_path)
    if len(excluded):
        _write_parquet(excluded, excluded_path)
    elif excluded_path.exists():
        excluded_path.unlink()

    partition_rows = len(clean) + len(excluded)
    if table == "HR_VET_TYPE_BRIDGE":
        if input_rows - partition_rows != 2 or len(clean) != 1662:
            raise AssertionError(f"{table}: expected D-011 bridge merge 1,664 → 1,662, got {input_rows} → {partition_rows}")
    elif input_rows != partition_rows:
        raise AssertionError(
            f"{table}: input rows {input_rows} != clean + excluded {partition_rows}"
        )

    run_dtm = _run_time()
    issue_ids = sorted(issue_counts)
    change = {
        "RUN_DTM_KST": run_dtm,
        "STAGE": "SILVER_QUALITY",
        "TABLE_NAME": table,
        "INPUT_FILE": f"data/02_silver/{table}.parquet",
        "OUTPUT_FILE": (
            f"data/02_silver/clean/{table}.parquet; "
            f"data/02_silver/_excluded/{table}.parquet"
            if len(excluded) else f"data/02_silver/clean/{table}.parquet"
        ),
        "INPUT_ROWS": input_rows,
        "CLEAN_ROWS": len(clean),
        "EXCLUDED_ROWS": len(excluded),
        "RULE_IDS": json.dumps([BASE_RULE_ID], ensure_ascii=False),
        "DECISION_IDS": json.dumps([BASE_DECISION_ID, *issue_ids], ensure_ascii=False),
        "CHANGE_DETAIL": details,
    }
    row_expected = 1662 if table == "HR_VET_TYPE_BRIDGE" else input_rows
    row_actual = 1662 if table == "HR_VET_TYPE_BRIDGE" and len(clean) == 1662 else partition_rows
    row_reconciled = row_actual == row_expected
    validation = [{
        "RUN_DTM_KST": run_dtm,
        "TABLE_NAME": table,
        "INPUT_ROWS": input_rows,
        "CLEAN_ROWS": len(clean),
        "EXCLUDED_ROWS": len(excluded),
        "RECONCILED_YN": "Y" if row_reconciled else "N",
        "ISSUE_ID": "ROW_RECONCILIATION",
        "EXPECTED_COUNT": row_expected,
        "ACTUAL_COUNT": row_actual,
        "MATCH_YN": "Y" if row_reconciled else "N",
        "DETAIL": "D-011 브리지: Silver 1,664 분리 행을 clean 1,662 표준 조합으로 통합" if table == "HR_VET_TYPE_BRIDGE" else "입력 행 = clean 유지 행 + _excluded 행",
    }]
    for issue_id, actual in sorted(issue_counts.items()):
        expected = EXPECTED_ISSUES.get(issue_id)
        validation.append({
            "RUN_DTM_KST": run_dtm,
            "TABLE_NAME": table,
            "INPUT_ROWS": input_rows,
            "CLEAN_ROWS": len(clean),
            "EXCLUDED_ROWS": len(excluded),
            "RECONCILED_YN": "Y" if input_rows == partition_rows else "N",
            "ISSUE_ID": issue_id,
            "EXPECTED_COUNT": "" if expected is None else expected,
            "ACTUAL_COUNT": actual,
            "MATCH_YN": "N" if expected is not None and expected != actual else "Y",
            "DETAIL": "기준 건수 대조" if expected is not None else "측정 건수",
        })
    _append_csv(CHANGE_LOG, CHANGE_FIELDS, [change])
    return validation


def _add_flag(frame: pd.DataFrame, flag: str, values: pd.Series) -> None:
    frame[flag] = values.fillna(False).map({True: "Y", False: "N"}).astype("string")


def _timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    if _is_missing(value):
        return pd.NaT
    return pd.Timestamp(value)


def _race_start_map(races: pd.DataFrame) -> dict[tuple[Any, Any], pd.Timestamp]:
    return {
        (row.RC_DT, row.RC_NO): _timestamp(row.START_DTM)
        for row in races.itertuples(index=False)
        if not _is_missing(row.START_DTM)
    }


def _flag_tickets(
    tables: dict[str, pd.DataFrame],
    tickets: pd.DataFrame,
    orders: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    tickets = tickets.copy()
    orders = orders.copy()

    business_cols = [
        col for col in tickets.columns
        if col not in {"_SRC_FILE", "_LOAD_DTM", *LINEAGE_COLUMNS}
    ]
    # Retain the first source row; source path is the deterministic tie-breaker.
    order_idx = tickets.sort_values(
        ["_SRC_ROW_NO", "BRONZE_PATH"], kind="mergesort"
    ).index
    ordered = tickets.loc[order_idx].copy()
    duplicate_mask = ordered.duplicated(subset=business_cols, keep="first")
    duplicate_index = ordered.index[duplicate_mask]
    group_ids = ordered.groupby(business_cols, dropna=False, sort=False).ngroup()
    first_rows = ordered.assign(_DQ_GROUP=group_ids).drop_duplicates("_DQ_GROUP")
    kept_by_group = first_rows.set_index("_DQ_GROUP")["_SRC_ROW_NO"]
    excluded = tickets.loc[duplicate_index].copy()
    excluded["KEPT_SRC_ROW_NO"] = group_ids.loc[duplicate_index].map(kept_by_group).astype("int64")
    tickets = tickets.drop(index=duplicate_index).copy()
    excluded["EXCLUSION_REASON"] = "완전 중복 마권; 동일 행 중 _SRC_ROW_NO 최소 유지"
    excluded["DQ_ISSUE_ID"] = "D-002"
    excluded["DQ_ACTION_DECISION_ID"] = "D-002"
    excluded["RULE_ID"] = "DQ-U01"
    excluded["DECISION_ID"] = "D-002"
    excluded["REASON"] = excluded["EXCLUSION_REASON"]
    excluded["BRONZE_FILE"] = excluded["BRONZE_PATH"]

    duplicate_full = tickets.duplicated(subset=business_cols, keep=False)
    if duplicate_full.any():
        raise AssertionError("D-002 duplicate removal left duplicate business rows")

    _add_flag(tickets, "INVALID_YN", pd.to_numeric(tickets["BET_AMT"], errors="coerce").eq(0))
    tickets["ZERO_BET_AGG_EXCLUDE_YN"] = tickets["INVALID_YN"]
    tickets["ERROR_AGG_INCLUDE_YN"] = tickets["INVALID_YN"].map({"Y": "Y", "N": "N"})

    starts = _race_start_map(tables["RC_RACE"])
    order_times = orders.set_index("ORDER_NO")["SALE_DTM"].to_dict()
    race_keys = pd.Series(list(zip(tickets["RC_DT"], tickets["RC_NO"])), index=tickets.index)
    start_values = pd.to_datetime(race_keys.map(starts), errors="coerce", utc=True)
    sale_values = pd.to_datetime(tickets["ORDER_NO"].map(order_times), errors="coerce", utc=True)
    late_ticket = (
        sale_values.notna()
        & start_values.notna()
        & sale_values.ge(start_values)
        & tickets["TICKET_STAT_CD"].eq("CANCEL")
    )
    _add_flag(tickets, "LATE_CANCEL_YN", late_ticket)
    _add_flag(tickets, "ZERO_LATE_CANCEL_YN", late_ticket & tickets["INVALID_YN"].eq("Y"))
    valid_amount = tickets["INVALID_YN"].ne("Y")
    tickets["CANCEL_RATE_NUMERATOR_INCLUDE_YN"] = valid_amount.map({True: "Y", False: "N"})
    tickets["CANCEL_RATE_DENOMINATOR_INCLUDE_YN"] = valid_amount.map({True: "Y", False: "N"})
    late_by_order = set(tickets.loc[late_ticket, "ORDER_NO"].dropna())

    entries = tables["RC_ENTRY"].copy()
    entry_key = ["RC_DT", "RC_NO", "CHUL_NO"]
    horse_name = entries.drop_duplicates(entry_key, keep="first").set_index(entry_key)["HR_NM"].to_dict()
    original = tickets["HR_NM"].copy()
    blank = original.map(_normal).eq("")
    tickets["HR_NM_ORIG"] = original
    filled = original.copy()
    for idx in tickets.index[blank]:
        row = tickets.loc[idx]
        filled.at[idx] = horse_name.get((row.RC_DT, row.RC_NO, row.CHUL_NO), pd.NA)
    tickets["HR_NM"] = filled
    _add_flag(tickets, "HR_NM_FILLED_YN", blank & tickets["HR_NM"].notna())

    order_ticket_count = tickets.groupby("ORDER_NO", dropna=False).size()
    mismatch = pd.to_numeric(orders["TICKET_CNT"], errors="coerce").ne(
        pd.to_numeric(orders["ORDER_NO"].map(order_ticket_count), errors="coerce").fillna(0)
    )
    _add_flag(orders, "HEADER_MISMATCH_YN", mismatch)
    cancel = orders["ORDER_TYPE_CD"].eq("CANCEL")
    known_order_nos = set(orders["ORDER_NO"].dropna())
    missing_orig = cancel & (
        orders["ORIG_ORDER_NO"].isna()
        | orders["ORIG_ORDER_NO"].astype("string").str.strip().eq("")
        | ~orders["ORIG_ORDER_NO"].isin(known_order_nos)
    )
    _add_flag(orders, "ORIG_MISSING_YN", missing_orig)
    _add_flag(orders, "LATE_CANCEL_YN", orders["ORDER_NO"].isin(late_by_order))

    # Aggregation-ready ticket indicators.  Zero-value tickets remain in clean.
    tickets["SALES_AGG_INCLUDE_YN"] = (~tickets["INVALID_YN"].eq("Y")).map({True: "Y", False: "N"})
    orders["CANCEL_RATE_DENOM_INCLUDE_YN"] = (~orders["TOTAL_AMT"].eq(0)).map({True: "Y", False: "N"})
    counts = {
        "D-002": len(excluded),
        "D-003": int(tickets["INVALID_YN"].eq("Y").sum()),
        "D-004_TICKET": int(tickets["LATE_CANCEL_YN"].eq("Y").sum()),
        "D-004_ORDER": int(orders["LATE_CANCEL_YN"].eq("Y").sum()),
        "D-005": int(tickets["HR_NM_FILLED_YN"].eq("Y").sum()),
        "D-006_HEADER": int(orders["HEADER_MISMATCH_YN"].eq("Y").sum()),
        "D-006_ORIG_MISSING": int(orders["ORIG_MISSING_YN"].eq("Y").sum()),
    }
    return tickets, excluded, counts | {"_ORDER_ROWS": len(orders)}


def _quality_vet(tables: dict[str, pd.DataFrame], hist: pd.DataFrame, bridge: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    hist = hist.copy()
    snapshots = tables["HR_WEEKLY_SNAPSHOT"].copy()
    snapshots = snapshots.dropna(subset=["HR_NM", "SNAPSHOT_DT"])
    snapshots = snapshots.sort_values(["HR_NM", "SNAPSHOT_DT"], kind="mergesort")
    by_horse = {name: group for name, group in snapshots.groupby("HR_NM", sort=False)}
    no_snapshot: list[bool] = []
    mismatch: list[bool] = []
    for row in hist.itertuples(index=False):
        candidates = by_horse.get(row.HR_NM)
        if candidates is None or _is_missing(row.VET_DT):
            no_snapshot.append(True)
            mismatch.append(False)
            continue
        earlier = candidates[candidates["SNAPSHOT_DT"] < row.VET_DT]
        if earlier.empty:
            no_snapshot.append(True)
            mismatch.append(False)
            continue
        prior = earlier.iloc[-1]
        no_snapshot.append(False)
        mismatch.append(_normal(prior["TR_GRP_NO"]) != _normal(row.TR_GRP_NO))
    _add_flag(hist, "VET_TR_GRP_MISMATCH_YN", pd.Series(mismatch, index=hist.index))
    _add_flag(hist, "VET_NO_PRIOR_SNAPSHOT_YN", pd.Series(no_snapshot, index=hist.index))
    hist["VET_GROUP_ANALYSIS_STATUS"] = "정상"
    hist.loc[hist["VET_TR_GRP_MISMATCH_YN"].eq("Y") | hist["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y"), "VET_GROUP_ANALYSIS_STATUS"] = "확인 필요"
    hist["TR_GRP_MISMATCH_YN"] = hist["VET_TR_GRP_MISMATCH_YN"]
    hist["PRIOR_SNAPSHOT_MISSING_YN"] = hist["VET_NO_PRIOR_SNAPSHOT_YN"]

    bridge = bridge.copy()
    # Preserve the source wording. Type analysis gets one item per (event, type).
    bridge["VET_TYPE_AGG_NM"] = bridge["VET_TYPE_NM"].map(
        lambda value: "일·열사병" if _normal(value) in {"일", "열사병", "일,열사병"} else value
    )
    duplicate_type = bridge.duplicated(["VET_SEQ", "VET_TYPE_AGG_NM"], keep="first")
    d011_count = int(duplicate_type.sum())
    bridge = bridge.loc[~duplicate_type].copy()
    merged = bridge["VET_TYPE_AGG_NM"].eq("일·열사병")
    bridge.loc[merged, "VET_TYPE_NM"] = "일·열사병"
    bridge["VET_TYPE_AGG_INCLUDE_YN"] = "Y"
    bridge["VET_TYPE_MERGED_YN"] = merged.map({True: "Y", False: "N"})
    counts = {
        "D-007_GROUP_MISMATCH": int(hist["VET_TR_GRP_MISMATCH_YN"].eq("Y").sum()),
        "D-007_NO_SNAPSHOT": int(hist["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y").sum()),
        "D-011": d011_count,
    }
    return hist, bridge, counts


def _raw_row_numbers(frame: pd.DataFrame) -> pd.Series:
    if "_SRC_FILE" in frame:
        return frame.groupby("_SRC_FILE", sort=False).cumcount() + 1
    return pd.Series(range(1, len(frame) + 1), index=frame.index)


def _missing_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().isin(["", "-----"])


def _count_rate(count: int, denominator: int) -> str:
    return "0.00%" if denominator == 0 else f"{count / denominator * 100:.2f}%"


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _sample_rows(frame: pd.DataFrame, mask: pd.Series, columns: list[str], limit: int = 3) -> str:
    if frame.empty or not bool(mask.any()):
        return "없음"
    selected = frame.loc[mask].head(limit)
    snippets: list[str] = []
    for _, row in selected.iterrows():
        parts = []
        for column in columns:
            if column not in selected.columns:
                continue
            value = row[column]
            if _is_missing(value):
                value = "NULL"
            elif isinstance(value, (date, datetime, pd.Timestamp)):
                value = value.isoformat()
            parts.append(f"{column}={str(value)[:80]}")
        snippets.append("; ".join(parts))
    return "<br>".join(snippets) or "없음"


def _parse_raw_datetime(value: Any) -> pd.Timestamp | pd.NaT:
    if _is_missing(value):
        return pd.NaT
    value = str(value).strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d %H:%M", "%H:%M"):
        try:
            return pd.Timestamp(datetime.strptime(value, fmt))
        except ValueError:
            continue
    return pd.to_datetime(value, errors="coerce")


def _late_cancel_mask(
    tickets: pd.DataFrame,
    orders: pd.DataFrame,
    races: pd.DataFrame,
    *,
    raw: bool,
) -> tuple[pd.Series, pd.Series]:
    if raw:
        order_key, ticket_date, ticket_race, status_col = "order_no", "rc_date", "rc_no", "ticket_status"
        sale_col, race_date, race_time, race_no = "sale_dtm", "RC_DATE", "START_TM_RAW", "RC_NO"
        start_map: dict[tuple[Any, Any], Any] = {}
        for row in races.itertuples(index=False):
            race_dt = pd.to_datetime(str(getattr(row, race_date)).strip(), format="%Y%m%d", errors="coerce")
            tm = _parse_raw_datetime(getattr(row, race_time))
            if not pd.isna(race_dt) and not pd.isna(tm):
                start_map[(race_dt.date(), int(getattr(row, race_no)))] = pd.Timestamp.combine(race_dt.date(), tm.time())
        date_values = pd.to_datetime(tickets[ticket_date].astype("string"), format="%Y%m%d", errors="coerce").dt.date
        race_keys = pd.Series(list(zip(date_values, pd.to_numeric(tickets[ticket_race], errors="coerce"))), index=tickets.index)
        order_times = orders.set_index("order_no")[sale_col].map(_parse_raw_datetime).to_dict()
        sale_values = pd.to_datetime(tickets[order_key].map(order_times), errors="coerce")
    else:
        order_key, ticket_date, ticket_race, status_col = "ORDER_NO", "RC_DT", "RC_NO", "TICKET_STAT_CD"
        sale_col, race_date, race_time, race_no = "SALE_DTM", "RC_DT", "START_DTM", "RC_NO"
        start_map = _race_start_map(races)
        race_keys = pd.Series(list(zip(tickets[ticket_date], tickets[ticket_race])), index=tickets.index)
        order_times = orders.set_index("ORDER_NO")[sale_col].to_dict()
        sale_values = pd.to_datetime(tickets[order_key].map(order_times), errors="coerce", utc=True)
    start_values = pd.to_datetime(race_keys.map(start_map), errors="coerce", utc=not raw)
    if raw:
        sale_values = pd.to_datetime(sale_values, errors="coerce", utc=False)
    late = sale_values.notna() & start_values.notna() & sale_values.ge(start_values) & tickets[status_col].astype("string").str.upper().eq("CANCEL")
    late_orders = tickets.loc[late, order_key].dropna().drop_duplicates()
    return late, orders[order_key].isin(late_orders)


def _make_quality_report(
    silver: dict[str, pd.DataFrame],
    traced: dict[str, pd.DataFrame],
    ticket_clean: pd.DataFrame,
    ticket_excluded: pd.DataFrame,
    vet_clean: pd.DataFrame,
    bridge_clean: pd.DataFrame,
) -> None:
    """Write a reproducible Bronze/Silver/clean quality comparison report."""
    bronze = {
        "BET_TICKET": pd.read_parquet(PROJECT_ROOT / "data/01_bronze/bet_ticket.parquet"),
        "BET_ORDER": pd.read_parquet(PROJECT_ROOT / "data/01_bronze/bet_order.parquet"),
        "RC_RACE": pd.read_parquet(PROJECT_ROOT / "data/01_bronze/RC_RACE.parquet"),
        "HR_VET_HIST": pd.read_parquet(PROJECT_ROOT / "data/01_bronze/HR_VET_HIST.parquet"),
        "HR_WEEKLY_SNAPSHOT": pd.read_parquet(PROJECT_ROOT / "data/01_bronze/HR_WEEKLY_SNAPSHOT.parquet"),
    }
    bt = bronze["BET_TICKET"].copy()
    bt["_SRC_ROW_NO"] = _raw_row_numbers(bt).astype("int64")
    bo = bronze["BET_ORDER"].copy()
    bo["_SRC_ROW_NO"] = _raw_row_numbers(bo).astype("int64")
    bvet = bronze["HR_VET_HIST"].copy()
    bvet["_SRC_ROW_NO"] = _raw_row_numbers(bvet).astype("int64")

    raw_business = [c for c in bt.columns if c not in {"_SRC_FILE", "_LOAD_DTM", "_SRC_ROW_NO"}]
    silver_tickets = traced["BET_TICKET"].copy()
    silver_business = [c for c in silver_tickets.columns if c not in {"_SRC_FILE", "_LOAD_DTM", *LINEAGE_COLUMNS}]
    raw_dups = bt.duplicated(raw_business, keep="first")
    silver_dups = silver_tickets.duplicated(silver_business, keep="first")
    raw_tickets_unique = bt.loc[~raw_dups].copy()
    silver_tickets_unique = silver_tickets.loc[~silver_dups].copy()
    raw_tickets_unique["_SRC_ROW_NO"] = bt.loc[~raw_dups, "_SRC_ROW_NO"]
    zero_raw = pd.to_numeric(raw_tickets_unique["bet_amt"].astype("string").str.replace(",", "", regex=False), errors="coerce").eq(0)
    zero_silver = pd.to_numeric(silver_tickets_unique["BET_AMT"], errors="coerce").eq(0)
    blank_raw = _missing_mask(raw_tickets_unique["hr_name"])
    blank_silver = _missing_mask(silver_tickets_unique["HR_NM"])
    raw_late_ticket, raw_late_order = _late_cancel_mask(raw_tickets_unique, bo, bronze["RC_RACE"], raw=True)
    silver_late_ticket, silver_late_order = _late_cancel_mask(
        silver_tickets_unique, traced["BET_ORDER"], traced["RC_RACE"], raw=False
    )

    def header_mismatch(order_frame: pd.DataFrame, ticket_frame: pd.DataFrame, raw: bool) -> pd.Series:
        order_col = "order_no" if raw else "ORDER_NO"
        count_col = "ticket_cnt" if raw else "TICKET_CNT"
        counts = ticket_frame.groupby(order_col).size()
        return pd.to_numeric(order_frame[count_col], errors="coerce").ne(
            pd.to_numeric(order_frame[order_col].map(counts), errors="coerce").fillna(0)
        )

    raw_header = header_mismatch(bo, raw_tickets_unique, raw=True)
    silver_header = header_mismatch(traced["BET_ORDER"], silver_tickets_unique, raw=False)
    raw_orig = bo["order_type_cd"].astype("string").str.upper().eq("CANCEL") & (
        _missing_mask(bo["orig_order_no"]) | ~bo["orig_order_no"].isin(set(bo["order_no"]))
    )
    silver_orders = traced["BET_ORDER"]
    clean_orders = pd.read_parquet(CLEAN_DIR / "BET_ORDER.parquet")
    silver_orig = silver_orders["ORDER_TYPE_CD"].eq("CANCEL") & (
        silver_orders["ORIG_ORDER_NO"].isna() | ~silver_orders["ORIG_ORDER_NO"].isin(set(silver_orders["ORDER_NO"]))
    )

    # Reuse the Silver quality logic for the same latest-prior-snapshot definition.
    bvet_norm = pd.DataFrame({
        "VET_SEQ": bvet["_SRC_ROW_NO"],
        "VET_DT": pd.to_datetime(bvet["VET_DT_RAW"].astype("string").str.replace(".", "-", regex=False), errors="coerce").dt.date,
        "HR_NM": bvet["HR_NAME"],
        "TR_GRP_NO": bvet["TR_GRP_NO"],
    })
    bsnap = bronze["HR_WEEKLY_SNAPSHOT"]
    bsnap_norm = pd.DataFrame({
        "SNAPSHOT_DT": pd.to_datetime(bsnap["SNAPSHOT_DT"].astype("string"), format="%Y%m%d", errors="coerce").dt.date,
        "HR_NM": bsnap["HR_NAME"], "TR_GRP_NO": bsnap["TR_GRP_NO"],
    })
    # Apply the same latest-prior-snapshot check to the parsed Bronze fields.
    bvet_norm, _, _ = _quality_vet({"HR_WEEKLY_SNAPSHOT": bsnap_norm}, bvet_norm, pd.DataFrame(columns=["VET_SEQ", "VET_TYPE_NM"]))
    svet = silver["HR_VET_HIST"]
    svet_norm = vet_clean
    raw_group_bad = bvet_norm["VET_TR_GRP_MISMATCH_YN"].eq("Y")
    raw_no_snapshot = bvet_norm["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y")
    silver_group_bad = svet_norm["VET_TR_GRP_MISMATCH_YN"].eq("Y")
    silver_no_snapshot = svet_norm["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y")

    # Map the named D-011 source rows and their exploded bridge rows to parent events.
    raw_names = bvet["VET_NM_RAW"].astype("string").fillna("")
    raw_d011 = raw_names.map(lambda value: all(token in str(value) for token in ("일", "열사병")))
    silver_d011 = bridge_clean["VET_TYPE_MERGED_YN"].eq("Y")

    # Rule records contain independently measured Bronze, standardized Silver, and clean results.
    issues: list[dict[str, Any]] = []
    dimension_keys: dict[str, dict[str, set[tuple[str, int]]]] = {
        dimension: {stage: set() for stage in ("Bronze", "Silver", "clean")}
        for dimension in ("완전성", "유일성", "유효성", "일관성")
    }

    def keyset(table: str, row_numbers: Any) -> set[tuple[str, int]]:
        return {(table, int(value)) for value in row_numbers if not _is_missing(value)}

    def add_issue(rule: str, dimension: str, name: str, table: str, denominator: tuple[int, int, int],
                  bronze_count: int, silver_count: int, clean_count: int,
                  bronze_keys: set[tuple[str, int]], silver_keys: set[tuple[str, int]], clean_keys: set[tuple[str, int]],
                  sample_bronze: str, sample_silver: str, sample_clean: str, action: str) -> None:
        for stage, values in (("Bronze", bronze_keys), ("Silver", silver_keys), ("clean", clean_keys)):
            dimension_keys[dimension][stage].update(values)
        issues.append({
            "rule": rule, "dimension": dimension, "name": name, "table": table,
            "denominators": denominator,
            "counts": (bronze_count, silver_count, clean_count),
            "samples": (sample_bronze, sample_silver, sample_clean), "action": action,
        })

    b_ticket_rows = len(bt); s_ticket_rows = len(silver_tickets); c_ticket_rows = len(ticket_clean)
    b_ticket_unique_rows = len(raw_tickets_unique); s_ticket_unique_rows = len(silver_tickets_unique)
    b_order_rows = len(bo); s_order_rows = len(silver_orders); c_order_rows = len(clean_orders)
    b_vet_rows = len(bvet); s_vet_rows = len(svet); c_vet_rows = len(vet_clean)

    raw_dup_keys = keyset("BET_TICKET", bt.loc[raw_dups, "_SRC_ROW_NO"])
    silver_dup_keys = keyset("BET_TICKET", traced["BET_TICKET"].loc[silver_dups, "_SRC_ROW_NO"])
    add_issue("D-002", "유일성", "완전 중복 마권", "BET_TICKET", (b_ticket_rows, s_ticket_rows, c_ticket_rows),
        int(raw_dups.sum()), int(silver_dups.sum()), int(len(ticket_excluded) * 0),
        raw_dup_keys, silver_dup_keys, set(),
        _sample_rows(bt, raw_dups, ["_SRC_ROW_NO", "order_no", "ticket_seq", "bet_amt"]),
        _sample_rows(traced["BET_TICKET"], silver_dups, ["_SRC_ROW_NO", "ORDER_NO", "TICKET_SEQ", "BET_AMT"]),
        f"중복 제외 {len(ticket_excluded):,}행; 잔여 중복 없음", "첫 행 유지, 나머지 _excluded/ 보관")

    clean_invalid = ticket_clean["INVALID_YN"].eq("Y")
    add_issue("D-003", "유효성", "0원 마권", "BET_TICKET", (b_ticket_unique_rows, s_ticket_unique_rows, c_ticket_rows),
        int(zero_raw.sum()), int(zero_silver.sum()), int(clean_invalid.sum()),
        keyset("BET_TICKET", raw_tickets_unique.loc[zero_raw, "_SRC_ROW_NO"]),
        keyset("BET_TICKET", silver_tickets_unique.loc[zero_silver, "_SRC_ROW_NO"]),
        keyset("BET_TICKET", ticket_clean.loc[clean_invalid, "_SRC_ROW_NO"]),
        _sample_rows(raw_tickets_unique, zero_raw, ["_SRC_ROW_NO", "order_no", "bet_amt", "ticket_status"]),
        _sample_rows(silver_tickets_unique, zero_silver, ["_SRC_ROW_NO", "ORDER_NO", "BET_AMT", "TICKET_STAT_CD"]),
        _sample_rows(ticket_clean, clean_invalid, ["_SRC_ROW_NO", "ORDER_NO", "BET_AMT", "INVALID_YN"]),
        "clean 보존; 매출·취소율 양쪽에서 제외하고 오류 집계에 포함")

    clean_late_ticket = ticket_clean["LATE_CANCEL_YN"].eq("Y")
    add_issue("D-004-TICKET", "일관성", "출발 시각 이후 취소 마권", "BET_TICKET", (b_ticket_unique_rows, s_ticket_unique_rows, c_ticket_rows),
        int(raw_late_ticket.sum()), int(silver_late_ticket.sum()), int(clean_late_ticket.sum()),
        keyset("BET_TICKET", raw_tickets_unique.loc[raw_late_ticket, "_SRC_ROW_NO"]),
        keyset("BET_TICKET", silver_tickets_unique.loc[silver_late_ticket, "_SRC_ROW_NO"]),
        keyset("BET_TICKET", ticket_clean.loc[clean_late_ticket, "_SRC_ROW_NO"]),
        _sample_rows(raw_tickets_unique, raw_late_ticket, ["_SRC_ROW_NO", "order_no", "rc_date", "rc_no", "ticket_status"]),
        _sample_rows(silver_tickets_unique, silver_late_ticket, ["_SRC_ROW_NO", "ORDER_NO", "RC_DT", "RC_NO", "TICKET_STAT_CD"]),
        _sample_rows(ticket_clean, clean_late_ticket, ["_SRC_ROW_NO", "ORDER_NO", "RC_DT", "RC_NO", "LATE_CANCEL_YN"]),
        "마권·전표에 표시하고 취소 분석에 포함")
    raw_late_order_rows = bo["order_no"].isin(set(raw_tickets_unique.loc[raw_late_ticket, "order_no"]))
    silver_late_order_rows = silver_orders["ORDER_NO"].isin(set(silver_tickets_unique.loc[silver_late_ticket, "ORDER_NO"]))
    clean_late_order_rows = clean_orders["ORDER_NO"].isin(set(ticket_clean.loc[clean_late_ticket, "ORDER_NO"]))
    add_issue("D-004-ORDER", "일관성", "출발 시각 이후 취소 고유 전표", "BET_ORDER", (b_order_rows, s_order_rows, c_order_rows),
        int(raw_late_order_rows.sum()), int(silver_late_order_rows.sum()), int(clean_late_order_rows.sum()),
        keyset("BET_ORDER", bo.loc[raw_late_order_rows, "_SRC_ROW_NO"]), keyset("BET_ORDER", traced["BET_ORDER"].loc[silver_late_order_rows, "_SRC_ROW_NO"]),
        keyset("BET_ORDER", clean_orders.loc[clean_late_order_rows, "_SRC_ROW_NO"]),
        _sample_rows(bo, raw_late_order_rows, ["_SRC_ROW_NO", "order_no", "sale_dtm", "orig_order_no"]),
        _sample_rows(traced["BET_ORDER"], silver_late_order_rows, ["_SRC_ROW_NO", "ORDER_NO", "SALE_DTM", "ORIG_ORDER_NO"]),
        _sample_rows(clean_orders, clean_late_order_rows, ["_SRC_ROW_NO", "ORDER_NO", "SALE_DTM", "LATE_CANCEL_YN"]),
        "전표는 고유 전표 행으로 계산")

    clean_filled = ticket_clean["HR_NM_FILLED_YN"].eq("Y")
    clean_blank = _missing_mask(ticket_clean["HR_NM"])
    add_issue("D-005", "완전성", "마권 마명 빈칸", "BET_TICKET", (b_ticket_unique_rows, s_ticket_unique_rows, c_ticket_rows),
        int(blank_raw.sum()), int(blank_silver.sum()), int(clean_blank.sum()),
        keyset("BET_TICKET", raw_tickets_unique.loc[blank_raw, "_SRC_ROW_NO"]), keyset("BET_TICKET", silver_tickets_unique.loc[blank_silver, "_SRC_ROW_NO"]),
        keyset("BET_TICKET", ticket_clean.loc[clean_blank, "_SRC_ROW_NO"]),
        _sample_rows(raw_tickets_unique, blank_raw, ["_SRC_ROW_NO", "order_no", "rc_date", "rc_no", "chul_no", "hr_name"]),
        _sample_rows(silver_tickets_unique, blank_silver, ["_SRC_ROW_NO", "ORDER_NO", "RC_DT", "RC_NO", "CHUL_NO", "HR_NM"]),
        f"원래 빈칸 {int(clean_filled.sum()):,}행 보정; clean 빈칸 {int(clean_blank.sum()):,}행",
        "출전표 마명으로 보정하고 HR_NM_ORIG 보존")

    add_issue("D-006-HEADER", "일관성", "전표·마권 장수 불일치", "BET_ORDER", (b_order_rows, s_order_rows, c_order_rows),
        int(raw_header.sum()), int(silver_header.sum()), int(clean_orders["HEADER_MISMATCH_YN"].eq("Y").sum()),
        keyset("BET_ORDER", bo.loc[raw_header, "_SRC_ROW_NO"]), keyset("BET_ORDER", traced["BET_ORDER"].loc[silver_header, "_SRC_ROW_NO"]),
        keyset("BET_ORDER", clean_orders.loc[clean_orders["HEADER_MISMATCH_YN"].eq("Y"), "_SRC_ROW_NO"]),
        _sample_rows(bo, raw_header, ["_SRC_ROW_NO", "order_no", "ticket_cnt"]),
        _sample_rows(traced["BET_ORDER"], silver_header, ["_SRC_ROW_NO", "ORDER_NO", "TICKET_CNT"]),
        _sample_rows(clean_orders, clean_orders["HEADER_MISMATCH_YN"].eq("Y"), ["_SRC_ROW_NO", "ORDER_NO", "TICKET_CNT", "HEADER_MISMATCH_YN"]),
        "수정하지 않고 HEADER_MISMATCH_YN 표시")
    add_issue("D-006-ORIG", "일관성", "원전표 없는 취소", "BET_ORDER", (b_order_rows, s_order_rows, c_order_rows),
        int(raw_orig.sum()), int(silver_orig.sum()), int(clean_orders["ORIG_MISSING_YN"].eq("Y").sum()),
        keyset("BET_ORDER", bo.loc[raw_orig, "_SRC_ROW_NO"]), keyset("BET_ORDER", traced["BET_ORDER"].loc[silver_orig, "_SRC_ROW_NO"]),
        keyset("BET_ORDER", clean_orders.loc[clean_orders["ORIG_MISSING_YN"].eq("Y"), "_SRC_ROW_NO"]),
        _sample_rows(bo, raw_orig, ["_SRC_ROW_NO", "order_no", "orig_order_no", "order_type_cd"]),
        _sample_rows(traced["BET_ORDER"], silver_orig, ["_SRC_ROW_NO", "ORDER_NO", "ORIG_ORDER_NO", "ORDER_TYPE_CD"]),
        _sample_rows(clean_orders, clean_orders["ORIG_MISSING_YN"].eq("Y"), ["_SRC_ROW_NO", "ORDER_NO", "ORIG_ORDER_NO"]),
        "수정하지 않고 ORIG_MISSING_YN 표시")

    add_issue("D-007-GROUP", "일관성", "진료 조 불일치", "HR_VET_HIST", (b_vet_rows, s_vet_rows, c_vet_rows),
        int(raw_group_bad.sum()), int(silver_group_bad.sum()), int(vet_clean["VET_TR_GRP_MISMATCH_YN"].eq("Y").sum()),
        keyset("HR_VET_HIST", bvet_norm.loc[raw_group_bad, "VET_SEQ"]), keyset("HR_VET_HIST", svet.loc[silver_group_bad, "VET_SEQ"]),
        keyset("HR_VET_HIST", vet_clean.loc[vet_clean["VET_TR_GRP_MISMATCH_YN"].eq("Y"), "VET_SEQ"]),
        _sample_rows(bvet_norm, raw_group_bad, ["VET_SEQ", "VET_DT", "HR_NM", "TR_GRP_NO"]),
        _sample_rows(svet, silver_group_bad, ["VET_SEQ", "VET_DT", "HR_NM", "TR_GRP_NO"]),
        _sample_rows(vet_clean, vet_clean["VET_TR_GRP_MISMATCH_YN"].eq("Y"), ["VET_SEQ", "VET_DT", "HR_NM", "TR_GRP_NO"]),
        "진료 기록 보존; 조 분석 상태 확인 필요")
    add_issue("D-007-SNAPSHOT", "완전성", "진료일 이전 스냅샷 없음", "HR_VET_HIST", (b_vet_rows, s_vet_rows, c_vet_rows),
        int(raw_no_snapshot.sum()), int(silver_no_snapshot.sum()), int(vet_clean["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y").sum()),
        keyset("HR_VET_HIST", bvet_norm.loc[raw_no_snapshot, "VET_SEQ"]), keyset("HR_VET_HIST", svet.loc[silver_no_snapshot, "VET_SEQ"]),
        keyset("HR_VET_HIST", vet_clean.loc[vet_clean["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y"), "VET_SEQ"]),
        _sample_rows(bvet_norm, raw_no_snapshot, ["VET_SEQ", "VET_DT", "HR_NM"]),
        _sample_rows(svet, silver_no_snapshot, ["VET_SEQ", "VET_DT", "HR_NM"]),
        _sample_rows(vet_clean, vet_clean["VET_NO_PRIOR_SNAPSHOT_YN"].eq("Y"), ["VET_SEQ", "VET_DT", "HR_NM"]),
        "진료 기록 보존; 조·스냅샷 분석 상태 확인 필요")

    silver_d011_rows = int(silver_d011.sum())
    add_issue("D-011", "유효성", "일·열사병 유형 집계 중복", "HR_VET_HIST", (b_vet_rows, s_vet_rows, c_vet_rows),
        int(raw_d011.sum()), silver_d011_rows, int(bridge_clean["VET_TYPE_MERGED_YN"].eq("Y").sum()),
        keyset("HR_VET_HIST", bvet.loc[raw_d011, "_SRC_ROW_NO"]), keyset("HR_VET_HIST", bridge_clean.loc[silver_d011, "VET_SEQ"]),
        keyset("HR_VET_HIST", bridge_clean.loc[silver_d011, "VET_SEQ"]),
        _sample_rows(bvet, raw_d011, ["_SRC_ROW_NO", "HR_NAME", "VET_NM_RAW"]),
        _sample_rows(bridge_clean, silver_d011, ["VET_SEQ", "VET_TYPE_NM", "VET_TYPE_AGG_NM"]),
        _sample_rows(bridge_clean, silver_d011, ["VET_SEQ", "VET_TYPE_NM", "VET_TYPE_AGG_NM", "VET_TYPE_AGG_INCLUDE_YN"]),
        "표준화 Silver 원문 보존; clean 브리지는 VET_TYPE_NM 기준 진료당 한 행으로 통합")

    # Dimension-level distinct violating rows. Denominators cover only rows checked by that dimension.
    dim_denominators = {
        "완전성": (b_ticket_unique_rows + b_vet_rows, s_ticket_unique_rows + s_vet_rows, c_ticket_rows + c_vet_rows),
        "유일성": (b_ticket_rows, s_ticket_rows, c_ticket_rows),
        "유효성": (b_ticket_unique_rows + b_vet_rows, s_ticket_unique_rows + s_vet_rows, c_ticket_rows + c_vet_rows),
        "일관성": (b_ticket_unique_rows + b_order_rows + b_vet_rows, s_ticket_unique_rows + s_order_rows + s_vet_rows, c_ticket_rows + c_order_rows + c_vet_rows),
    }

    lines = [
        "# 품질 관리 보고서", "",
        f"- 생성 시각: {_run_time()}",
        "- 입력 기준: `data/01_bronze/`와 `data/02_silver/*.parquet` (Silver 원본은 읽기 전용)",
        "- 결과: `data/02_silver/clean/`; 완전 중복 제외 행은 `data/02_silver/_excluded/`",
        "- 비율은 해당 차원에서 점검한 행 수 대비 위반 행 비율입니다. 차원 내 규칙 중복 위반 행은 한 번만 셉니다.",
        "",
        "## 규칙 목록", "",
    ]
    rule_rows = [[BASE_RULE_ID, "공통", "모든 행의 출처·행 번호·규칙/결정 ID 기록과 행 수 대사", "추적 컬럼 추가, 제외 행은 별도 보관"]]
    for item in issues:
        rule_rows.append([item["rule"], item["dimension"], item["name"], item["action"]])
    lines.append(_md_table(["규칙 ID", "품질 차원", "검사 내용", "처리"], rule_rows))
    lines.extend(["", "## 차원별 위반 수·비율: Bronze와 Silver 비교", ""])
    dim_rows = []
    for dimension in ("완전성", "유일성", "유효성", "일관성"):
        denom = dim_denominators[dimension]
        counts = tuple(len(dimension_keys[dimension][stage]) for stage in ("Bronze", "Silver", "clean"))
        dim_rows.append([
            dimension,
            f"{counts[0]:,} / {denom[0]:,} ({_count_rate(counts[0], denom[0])})",
            f"{counts[1]:,} / {denom[1]:,} ({_count_rate(counts[1], denom[1])})",
            f"{counts[2]:,} / {denom[2]:,} ({_count_rate(counts[2], denom[2])})",
        ])
    lines.append(_md_table(["차원", "Bronze 위반 행/점검 행 (비율)", "Silver 위반 행/점검 행 (비율)", "clean 결과 위반 행/점검 행 (비율)"], dim_rows))
    lines.extend(["", "## 규칙별 위반 건수와 예시", ""])
    issue_table = []
    for item in issues:
        b_count, s_count, c_count = item["counts"]
        b_den, s_den, c_den = item["denominators"]
        issue_table.append([
            item["rule"], item["dimension"], item["name"],
            f"{b_count:,} ({_count_rate(b_count, b_den)})",
            f"{s_count:,} ({_count_rate(s_count, s_den)})",
            f"{c_count:,} ({_count_rate(c_count, c_den)})",
        ])
    lines.append(_md_table(["규칙 ID", "차원", "위반 항목", "Bronze", "Silver", "clean/처리 후"], issue_table))
    lines.extend(["", "### 샘플 행 (각 규칙 최대 3행)", ""])
    for item in issues:
        lines.extend([
            f"#### {item['rule']} · {item['name']}", "",
            f"- 처리: {item['action']}",
            f"- Bronze 예시: {item['samples'][0]}",
            f"- Silver 예시: {item['samples'][1]}",
            f"- clean 예시/결과: {item['samples'][2]}", "",
        ])
    lines.extend([
        "## 행 수 대사", "",
        "| Silver 테이블 | Silver 입력 | clean 유지 | _excluded | 대사 |",
        "|---|---:|---:|---:|---|",
    ])
    for table in sorted(silver, key=str.casefold):
        input_rows = len(silver[table])
        excluded_rows = len(ticket_excluded) if table == "BET_TICKET" else 0
        clean_rows = len(bridge_clean) if table == "HR_VET_TYPE_BRIDGE" else input_rows - excluded_rows
        reconciled = clean_rows == 1662 if table == "HR_VET_TYPE_BRIDGE" else input_rows == clean_rows + excluded_rows
        lines.append(f"| {table} | {input_rows:,} | {clean_rows:,} | {excluded_rows:,} | {'일치' if reconciled else '불일치'} |")
    lines.extend([
        "", "## 해석 기준", "",
        "- D-003, D-004, D-006, D-007 위반은 clean에서 제거하지 않고 플래그로 보존합니다.",
        "- D-002 완전 중복만 제외 데이터로 분리합니다. D-005 빈 마명은 출전표로 보정하고 원래 값을 함께 보존합니다.",
        "- D-011: 표준화 Silver의 진료명 분리 행은 보존하고, clean 브리지는 VET_TYPE_NM 기준으로 진료당 일·열사병 한 행(1,662 조합)으로 통합합니다.",
        "- Bronze·Silver 입력 행은 원천 행 번호로 추적합니다. 브리지의 1,664 → 1,662 행 통합은 D-011 결정에 따른 표준 유형 조합 단위입니다.",
        "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=REPORT_PATH.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write("\n".join(lines))
        os.replace(temporary, REPORT_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> None:
    if not SILVER_DIR.is_dir():
        raise FileNotFoundError(f"Silver directory not found: {SILVER_DIR}")
    tables = _read_silver()
    required = {"BET_TICKET", "BET_ORDER", "RC_RACE", "RC_ENTRY", "HR_VET_HIST", "HR_VET_TYPE_BRIDGE", "HR_WEEKLY_SNAPSHOT"}
    missing = sorted(required - tables.keys())
    if missing:
        raise ValueError(f"Missing required Silver tables: {', '.join(missing)}")

    traced = {name: _attach_lineage(name, frame) for name, frame in tables.items()}
    ticket_clean, ticket_excluded, ticket_counts = _flag_tickets(
        traced, traced["BET_TICKET"], traced["BET_ORDER"]
    )
    order_clean = ticket_counts.pop("_ORDER_ROWS")
    order_frame = traced["BET_ORDER"].copy()
    # Flags are constructed in _flag_tickets; repeat only its deterministic header work here.
    order_frame["HEADER_MISMATCH_YN"] = "N"
    n_by_order = ticket_clean.groupby("ORDER_NO").size()
    order_frame["HEADER_MISMATCH_YN"] = order_frame.apply(
        lambda row: "Y" if int(row.TICKET_CNT) != int(n_by_order.get(row.ORDER_NO, 0)) else "N", axis=1
    )
    late_order_set = set(ticket_clean.loc[ticket_clean["LATE_CANCEL_YN"].eq("Y"), "ORDER_NO"])
    order_frame["LATE_CANCEL_YN"] = order_frame["ORDER_NO"].isin(late_order_set).map({True: "Y", False: "N"})
    cancel = order_frame["ORDER_TYPE_CD"].eq("CANCEL")
    order_nos = set(order_frame["ORDER_NO"].dropna())
    missing_orig = cancel & (order_frame["ORIG_ORDER_NO"].isna() | order_frame["ORIG_ORDER_NO"].astype("string").str.strip().eq("") | ~order_frame["ORIG_ORDER_NO"].isin(order_nos))
    order_frame["ORIG_MISSING_YN"] = missing_orig.map({True: "Y", False: "N"})
    order_frame["CANCEL_RATE_DENOM_INCLUDE_YN"] = order_frame["TOTAL_AMT"].ne(0).map({True: "Y", False: "N"})

    vet_clean, bridge_clean, vet_counts = _quality_vet(
        traced, traced["HR_VET_HIST"], traced["HR_VET_TYPE_BRIDGE"]
    )
    issue_counts = ticket_counts | vet_counts
    validation_rows: list[dict[str, Any]] = []
    for table in sorted(traced, key=str.casefold):
        frame = traced[table]
        clean = frame
        excluded = frame.iloc[0:0].copy()
        details = "보존; DQ 추적 컬럼 추가"
        counts: dict[str, int] = {}
        if table == "BET_TICKET":
            clean, excluded = ticket_clean, ticket_excluded
            details = "완전 중복 마권만 _excluded; 0원·늦은 취소·마명 보정 플래그는 clean에 유지"
            counts = {key: value for key, value in ticket_counts.items() if key != "_ORDER_ROWS"}
        elif table == "BET_ORDER":
            clean = order_frame
            details = "전표 불일치·원전표 없음·늦은 취소를 표시하고 보존; 지표용 포함 플래그 추가"
            counts = {key: value for key, value in ticket_counts.items() if key.startswith("D-006") or key == "D-004_ORDER"}
        elif table == "HR_VET_HIST":
            clean = vet_clean
            details = "조 불일치·이전 스냅샷 부재를 확인 필요로 표시; 진료 원문 보존"
            counts = {key: value for key, value in vet_counts.items() if key.startswith("D-007")}
        elif table == "HR_VET_TYPE_BRIDGE":
            clean = bridge_clean
            details = "D-011: VET_TYPE_NM을 진료당 일·열사병 한 행으로 통합; Silver 원문 유지"
            counts = {"D-011": vet_counts["D-011"]}
        validations = _write_table(table, clean, excluded, len(frame), details, counts)
        validation_rows.extend(validations)
        print(f"{table}: input={len(frame):,}, clean={len(clean):,}, excluded={len(excluded):,}")

    # The D-007/D-011 expectations are repeated in their owning table rows only.
    # Also record the requested bridge reconciliation against its specified target.
    bridge_input = len(tables["HR_VET_TYPE_BRIDGE"])
    bridge_combinations = bridge_clean[["VET_SEQ", "VET_TYPE_NM"]].drop_duplicates()
    bridge_kept = len(bridge_combinations)
    if bridge_kept != 1662 or bridge_clean.duplicated(["VET_SEQ", "VET_TYPE_NM"]).any():
        raise AssertionError("D-011: clean bridge must contain 1,662 unique (VET_SEQ, VET_TYPE_NM) combinations")
    validation_rows.append({
        "RUN_DTM_KST": _run_time(), "TABLE_NAME": "HR_VET_TYPE_BRIDGE",
        "INPUT_ROWS": bridge_input, "CLEAN_ROWS": len(bridge_clean), "EXCLUDED_ROWS": 0,
        "RECONCILED_YN": "Y" if bridge_input - len(bridge_clean) == 2 and len(bridge_clean) == 1662 else "N",
        "ISSUE_ID": "D-011_BRIDGE_ROWS", "EXPECTED_COUNT": 1662,
        "ACTUAL_COUNT": bridge_kept, "MATCH_YN": "Y" if bridge_kept == 1662 else "N",
        "DETAIL": "D-011: 진료별 중복 유형을 일·열사병 한 행으로 통합; 원문 Silver 보존",
    })
    _append_csv(VALIDATION_LOG, VALIDATION_FIELDS, validation_rows)
    _make_quality_report(tables, traced, ticket_clean, ticket_excluded, vet_clean, bridge_clean)
    print(f"Wrote clean tables to {CLEAN_DIR}")
    print(f"Wrote audit logs to {CHANGE_LOG} and {VALIDATION_LOG}")
    print(f"Wrote report to {REPORT_PATH}")


if __name__ == "__main__":
    main()
