"""Standardize Bronze Parquet files into Silver tables."""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow as arrow
import pyarrow.parquet as parquet



PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "01_bronze"
SILVER_DIR = PROJECT_ROOT / "data" / "02_silver"
META_DIR = PROJECT_ROOT / "meta"
CHANGE_LOG_PATH = META_DIR / "silver_change_log.csv"
METADATA_COLUMNS = ["_SRC_FILE", "_LOAD_DTM"]
MISSING_VALUES = {"", "-----"}
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
        "STAGE": "SILVER",
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


def require_columns(frame: pd.DataFrame, columns: list[str], table: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{table} is missing Bronze columns: {', '.join(missing)}")


def clean_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    return None if value in MISSING_VALUES else value


def cleaned_series(series: pd.Series) -> pd.Series:
    return series.map(clean_value)


def parse_date_value(value: Any) -> date | None:
    value = clean_value(value)
    if value is None:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date value: {value!r}")


def date_column(series: pd.Series) -> pd.Series:
    return series.map(parse_date_value)


def parse_datetime_value(value: Any, formats: tuple[str, ...]) -> pd.Timestamp | None:
    value = clean_value(value)
    if value is None:
        return None
    for fmt in formats:
        try:
            return pd.Timestamp(datetime.strptime(value, fmt))
        except ValueError:
            pass
    raise ValueError(f"Unrecognized datetime value: {value!r}")


def datetime_column(
    series: pd.Series,
    formats: tuple[str, ...],
) -> pd.Series:
    values = series.map(lambda value: parse_datetime_value(value, formats))
    return pd.to_datetime(values).dt.tz_localize("Asia/Seoul")


def time_column(series: pd.Series) -> pd.Series:
    def parse(value: Any) -> time | None:
        value = clean_value(value)
        if value is None:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                pass
        raise ValueError(f"Unrecognized time value: {value!r}")

    return series.map(parse)


def integer_column(series: pd.Series, *, multiplier: int = 1) -> pd.Series:
    values = cleaned_series(series).map(
        lambda value: None if value is None or pd.isna(value) else str(value).replace(",", "")
    )
    numeric = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & numeric.isna()
    if invalid.any():
        examples = values[invalid].head(5).tolist()
        raise ValueError(f"Invalid integer values: {examples}")
    if multiplier != 1:
        numeric = numeric * multiplier
    fractional = numeric.notna() & (numeric % 1 != 0)
    if fractional.any():
        examples = values[fractional].head(5).tolist()
        raise ValueError(f"Non-integer values in integer column: {examples}")
    return numeric.astype("Int64")


def decimal_column(series: pd.Series) -> pd.Series:
    values = cleaned_series(series).map(
        lambda value: None if value is None or pd.isna(value) else str(value).replace(",", "")
    )
    numeric = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & numeric.isna()
    if invalid.any():
        examples = values[invalid].head(5).tolist()
        raise ValueError(f"Invalid decimal values: {examples}")
    return numeric.astype("Float64")


def map_values(
    series: pd.Series,
    mapping: dict[str, str],
    *,
    upper: bool = False,
    unknown: str = "preserve",
) -> pd.Series:
    def map_one(value: Any) -> str | None:
        value = clean_value(value)
        if value is None:
            return None
        key = value.upper() if upper else value
        mapped = mapping.get(key)
        if mapped is not None:
            return mapped
        if unknown == "error":
            raise ValueError(f"Unmapped code value: {value!r}")
        return key

    return series.map(map_one)


def attach_metadata(
    frame: pd.DataFrame,
    source: pd.DataFrame,
) -> pd.DataFrame:
    for column in METADATA_COLUMNS:
        if column in source.columns:
            frame[column] = source[column].astype("string")
    return frame


def normalize_string_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the shared TRIM and missing-value rule to textual columns."""
    for column in frame.columns:
        series = frame[column]
        is_text = all(
            value is None or pd.isna(value) or isinstance(value, str)
            for value in series
        )
        if is_text:
            frame[column] = cleaned_series(series).astype("string")
    return frame


def renamed_table(
    source: pd.DataFrame,
    rename: dict[str, str],
    *,
    drop: tuple[str, ...] = (),
) -> pd.DataFrame:
    output = source.drop(columns=[column for column in drop if column in source])
    output = output.rename(columns=rename)
    return output


BET_TYPE_MAP = {
    "WIN": "WIN",
    "단승": "WIN",
    "단식": "WIN",
    "PLC": "PLC",
    "연승": "PLC",
    "연식": "PLC",
    "QNL": "QNL",
    "복승": "QNL",
    "복식": "QNL",
    "복연": "QPL",
    "쌍식": "EXA",
    "삼복": "TRI",
    "삼쌍": "TLA",
}
TICKET_STATUS_MAP = {"SOLD": "SOLD", "CANCEL": "CANCEL", "VOID": "VOID"}
REGION_MAP = {
    "서울특별시": "서울", "서울": "서울",
    "부산광역시": "부산", "부산": "부산",
    "경기도": "경기", "경기": "경기",
    "경상북도": "경북", "경북": "경북",
    "경상남도": "경남", "경남": "경남",
    "전라남도": "전남", "전남": "전남",
    "제주특별자치도": "제주", "제주": "제주",
    "대구광역시": "대구", "대구": "대구",
    "인천광역시": "인천", "인천": "인천",
    "광주광역시": "광주", "광주": "광주",
    "대전광역시": "대전", "대전": "대전",
    "울산광역시": "울산", "울산": "울산",
    "충청북도": "충북", "충북": "충북",
    "충청남도": "충남", "충남": "충남",
    "전라북도": "전북", "전북": "전북",
    "강원도": "강원", "강원특별자치도": "강원", "강원": "강원",
}


def table_bet_order(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(
        source,
        ["order_no", "order_type_cd", "orig_order_no", "member_no", "channel_cd",
         "sale_dtm", "biz_date", "ticket_cnt", "total_amt"],
        "BET_ORDER",
    )
    output = renamed_table(source, {
        "order_no": "ORDER_NO", "order_type_cd": "ORDER_TYPE_CD",
        "orig_order_no": "ORIG_ORDER_NO", "member_no": "MBR_NO",
        "sale_dtm": "SALE_DTM", "biz_date": "BIZ_DT",
        "ticket_cnt": "TICKET_CNT", "total_amt": "TOTAL_AMT",
    }, drop=("channel_cd",))
    channel = cleaned_series(source["channel_cd"])
    branches = channel.str.extract(r"(?i)^OTB(\d{2})$")[0]
    output["CHNL_CD"] = channel.map(
        lambda value: "UNKNOWN" if value is None or pd.isna(value) else
        ("OTB" if re.fullmatch(r"(?i)OTB\d{2}", value) else value.upper())
    )
    output["OTB_BRANCH_NO"] = branches
    output["MBR_NO"] = cleaned_series(source["member_no"]).str.upper()
    output["ORIG_ORDER_NO"] = cleaned_series(source["orig_order_no"])
    output["SALE_DTM"] = datetime_column(
        source["sale_dtm"], ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S")
    )
    output["BIZ_DT"] = date_column(source["biz_date"])
    output["TICKET_CNT"] = integer_column(source["ticket_cnt"])
    output["TOTAL_AMT"] = integer_column(source["total_amt"])
    return {"BET_ORDER": attach_metadata(output, source)}


def table_bet_ticket(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, [
        "order_no", "ticket_seq", "rc_date", "rc_no", "bet_type_cd", "chul_no",
        "hr_name", "chul_no2", "hr_name2", "ticket_cnt", "bet_amt", "ticket_status",
    ], "BET_TICKET")
    output = renamed_table(source, {
        "order_no": "ORDER_NO", "ticket_seq": "TICKET_SEQ", "rc_date": "RC_DT",
        "rc_no": "RC_NO", "bet_type_cd": "BET_TYPE_CD", "chul_no": "CHUL_NO",
        "hr_name": "HR_NM", "chul_no2": "CHUL_NO2", "hr_name2": "HR_NM2",
        "ticket_cnt": "UNIT_CNT", "bet_amt": "BET_AMT", "ticket_status": "TICKET_STAT_CD",
    }, drop=("unit_amt",))
    output["RC_DT"] = date_column(source["rc_date"])
    for column in ("TICKET_SEQ", "RC_NO", "CHUL_NO", "CHUL_NO2", "UNIT_CNT", "BET_AMT"):
        source_column = {
            "TICKET_SEQ": "ticket_seq", "RC_NO": "rc_no", "CHUL_NO": "chul_no",
            "CHUL_NO2": "chul_no2", "UNIT_CNT": "ticket_cnt", "BET_AMT": "bet_amt",
        }[column]
        output[column] = integer_column(source[source_column])
    output["BET_TYPE_CD"] = map_values(source["bet_type_cd"], BET_TYPE_MAP, upper=True, unknown="error")
    output["TICKET_STAT_CD"] = map_values(source["ticket_status"], TICKET_STATUS_MAP, upper=True, unknown="error")
    for column in ("ORDER_NO", "HR_NM", "HR_NM2"):
        output[column] = cleaned_series(output[column])
    return {"BET_TICKET": attach_metadata(output, source)}


def table_member(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["MBR_NO", "BIRTH_DT", "JOIN_DT", "REGION_NM", "MBR_GRADE_CD", "MBR_STAT_CD"], "MBR_MASTER")
    output = source.drop(columns=METADATA_COLUMNS, errors="ignore").copy()
    output["BIRTH_DT"] = date_column(source["BIRTH_DT"])
    output["JOIN_DT"] = date_column(source["JOIN_DT"])
    output["REGION_CD"] = map_values(source["REGION_NM"], REGION_MAP, unknown="error")
    output = output.drop(columns="REGION_NM")
    output["MBR_NO"] = cleaned_series(source["MBR_NO"]).str.upper()
    output["MBR_GRADE_CD"] = cleaned_series(source["MBR_GRADE_CD"]).str.upper()
    output["MBR_STAT_CD"] = cleaned_series(source["MBR_STAT_CD"]).str.upper()
    return {"MBR_MASTER": attach_metadata(output, source)}


def grade_code(value: Any) -> str | None:
    value = clean_value(value)
    if value is None:
        return None
    value = value.upper()
    if value in {"미", "NONE"}:
        return "NONE"
    match = re.search(r"([1-6])", value)
    return match.group(1) if match else value


def horse_weekly(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, [
        "SNAPSHOT_DT", "HR_NAME", "PRD_NM", "SEX_NM", "BIRTH_RAW", "AGE_RAW",
        "GRADE_RAW", "TR_GRP_NO", "TR_NAME", "OW_NAME", "TOT_RC_CNT", "TOT_1ST",
        "TOT_2ND", "TOT_3RD", "Y1_RC_CNT", "Y1_1ST", "Y1_2ND", "Y1_3RD",
        "PRIZE_AMT_RAW", "RATING_RAW", "INTRO_PRICE_RAW", "SIRE_NAME", "DAM_NAME",
    ], "HR_WEEKLY_SNAPSHOT")
    mapping = {
        "HR_NAME": "HR_NM", "SEX_NM": "HR_SEX_CD", "BIRTH_RAW": "HR_BIRTH_DT",
        "AGE_RAW": "HR_AGE", "GRADE_RAW": "HR_GRADE_CD", "TR_NAME": "TR_NM",
        "OW_NAME": "OW_NM", "TOT_1ST": "TOT_1ST_CNT", "TOT_2ND": "TOT_2ND_CNT",
        "TOT_3RD": "TOT_3RD_CNT", "Y1_1ST": "Y1_1ST_CNT", "Y1_2ND": "Y1_2ND_CNT",
        "Y1_3RD": "Y1_3RD_CNT", "PRIZE_AMT_RAW": "PRIZE_AMT", "RATING_RAW": "RATING_VAL",
        "SIRE_NAME": "SIRE_NM", "DAM_NAME": "DAM_NM",
    }
    output = renamed_table(source, mapping, drop=("PRD_NM", "INTRO_PRICE_RAW"))
    output["SNAPSHOT_DT"] = date_column(source["SNAPSHOT_DT"])
    output["HR_BIRTH_DT"] = date_column(source["BIRTH_RAW"])
    output["HR_SEX_CD"] = map_values(source["SEX_NM"], {"수": "M", "암": "F", "거": "G"}, unknown="error")
    output["HR_GRADE_CD"] = source["GRADE_RAW"].map(grade_code)
    output["TR_GRP_NO"] = cleaned_series(source["TR_GRP_NO"])
    external = cleaned_series(source["TR_NAME"]).eq("외부마")
    output["TR_EXTERNAL_YN"] = external.map({True: "Y", False: "N"})
    output.loc[external, "TR_NM"] = pd.NA

    for column, source_column in {
        "HR_AGE": "AGE_RAW", "TOT_RC_CNT": "TOT_RC_CNT", "TOT_1ST_CNT": "TOT_1ST",
        "TOT_2ND_CNT": "TOT_2ND", "TOT_3RD_CNT": "TOT_3RD", "Y1_RC_CNT": "Y1_RC_CNT",
        "Y1_1ST_CNT": "Y1_1ST", "Y1_2ND_CNT": "Y1_2ND", "Y1_3RD_CNT": "Y1_3RD",
        "PRIZE_AMT": "PRIZE_AMT_RAW", "RATING_VAL": "RATING_RAW",
    }.items():
        output[column] = integer_column(source[source_column])

    intro_amount: list[int | None] = []
    intro_type: list[str | None] = []
    for raw_value in source["INTRO_PRICE_RAW"]:
        value = clean_value(raw_value)
        if value is None:
            intro_amount.append(None)
            intro_type.append(None)
            continue
        if value == "자가생산":
            intro_amount.append(None)
            intro_type.append("자가생산")
            continue
        type_match = re.search(r"\(([^()]*)\)\s*$", value)
        amount_match = re.search(r"([\d,]+)\s*천원", value)
        intro_amount.append(int(amount_match.group(1).replace(",", "")) * 1000 if amount_match else None)
        intro_type.append(type_match.group(1).strip() if type_match else None)
        if amount_match is None and type_match is None:
            raise ValueError(f"Unrecognized INTRO_PRICE_RAW value: {value!r}")
    output["INTRO_AMT"] = pd.Series(intro_amount, dtype="Int64")
    output["INTRO_TYPE_NM"] = pd.Series(intro_type, dtype="string")
    return {"HR_WEEKLY_SNAPSHOT": attach_metadata(output, source)}


def trainer_weekly(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, [
        "SNAPSHOT_DT", "TR_NAME", "GRP_NO", "BIRTH_RAW", "AGE_RAW", "DEBUT_RAW",
        "TOT_RC_CNT", "TOT_1ST", "TOT_2ND", "TOT_3RD", "Y1_RC_CNT", "Y1_1ST", "Y1_2ND", "Y1_3RD",
    ], "TR_WEEKLY_SNAPSHOT")
    output = renamed_table(source, {
        "TR_NAME": "TR_NM", "GRP_NO": "TR_GRP_NO", "BIRTH_RAW": "TR_BIRTH_DT",
        "AGE_RAW": "TR_AGE", "DEBUT_RAW": "DEBUT_DT", "TOT_1ST": "TOT_1ST_CNT",
        "TOT_2ND": "TOT_2ND_CNT", "TOT_3RD": "TOT_3RD_CNT", "Y1_1ST": "Y1_1ST_CNT",
        "Y1_2ND": "Y1_2ND_CNT", "Y1_3RD": "Y1_3RD_CNT",
    })
    for column in ("SNAPSHOT_DT", "TR_BIRTH_DT", "DEBUT_DT"):
        output[column] = date_column(output[column])
    for column in ("TR_AGE", "TOT_RC_CNT", "TOT_1ST_CNT", "TOT_2ND_CNT", "TOT_3RD_CNT",
                   "Y1_RC_CNT", "Y1_1ST_CNT", "Y1_2ND_CNT", "Y1_3RD_CNT"):
        output[column] = integer_column(output[column])
    output["TR_GRP_NO"] = cleaned_series(output["TR_GRP_NO"])
    return {"TR_WEEKLY_SNAPSHOT": attach_metadata(output, source)}


def race_grade(value: Any) -> tuple[str | None, str | None]:
    value = clean_value(value)
    if value is None:
        return None, None
    grade_match = re.search(r"OPEN|[1-6]", value.upper())
    grade = "OPEN" if grade_match and grade_match.group(0) == "OPEN" else (grade_match.group(0) if grade_match else None)
    if "핸디캡" in value:
        burden = "HANDICAP"
    elif "별정A" in value or "별정 A" in value:
        burden = "SPECIAL_A"
    else:
        burden = None
    return grade, burden


def race_condition(value: Any) -> tuple[str | None, str | None]:
    value = clean_value(value)
    if value is None:
        return None, None
    value = re.sub(r"^핸디캡\s*", "", value)
    class_name = next((name for name in ("제주마", "한라마") if value.startswith(name)), None)
    if class_name is None:
        return value.strip() or None, None
    remainder = value[len(class_name):].strip()
    if remainder == "일반":
        return class_name, None
    return class_name, remainder or None


def weather_track(value: Any) -> tuple[str | None, str | None, float | None]:
    value = clean_value(value)
    if value is None:
        return None, None, None
    weather_map = {"맑음": "CLEAR", "흐림": "CLOUDY", "비": "RAIN", "안개": "FOG"}
    track_map = {"건조": "DRY", "양호": "GOOD", "다습": "MOIST", "포화": "SATURATED", "불량": "SLOPPY"}
    weather = next((code for label, code in weather_map.items() if label in value), None)
    track = next((code for label, code in track_map.items() if label in value), None)
    moisture_match = re.search(r"\(([\d.]+)\s*%\)", value)
    moisture = float(moisture_match.group(1)) if moisture_match else None
    return weather, track, moisture


def table_race(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, [
        "RC_DATE", "RC_NO", "TITLE_RAW", "RC_DOW", "MEET_NM", "RC_DAY_RAW", "RC_DIST_RAW",
        "RANK_RAW", "RC_COND_RAW", "WEATHER_TRACK_RAW", "PRIZE_RAW", "DIVIDEND_RAW", "START_TM_RAW",
    ], "RC_RACE")
    output = pd.DataFrame(index=source.index)
    output["RC_DT"] = date_column(source["RC_DATE"])
    output["RC_NO"] = integer_column(source["RC_NO"])
    output["MEET_CD"] = map_values(source["MEET_NM"], {"제주": "JEJU"}, unknown="error")
    output["RC_DAY_SEQ"] = integer_column(source["RC_DAY_RAW"].map(lambda v: re.sub(r"\D", "", clean_value(v) or "")))
    output["RC_DIST_M"] = integer_column(source["RC_DIST_RAW"].map(lambda v: re.sub(r"\D", "", clean_value(v) or "")))

    grades = source["RANK_RAW"].map(race_grade)
    output["RC_GRADE_CD"] = grades.map(lambda value: value[0])
    output["BUDAM_TYPE_CD"] = grades.map(lambda value: value[1])
    conditions = source["RC_COND_RAW"].map(race_condition)
    output["HR_CLASS_NM"] = conditions.map(lambda value: value[0])
    output["RC_TITLE_NM"] = conditions.map(lambda value: value[1])
    weather = source["WEATHER_TRACK_RAW"].map(weather_track)
    output["WEATHER_CD"] = weather.map(lambda value: value[0])
    output["TRACK_STAT_CD"] = weather.map(lambda value: value[1])
    output["TRACK_MOIST_RT"] = pd.Series(weather.map(lambda value: value[2]), dtype="Float64")

    prizes: list[list[int | None]] = []
    for value in source["PRIZE_RAW"]:
        amounts = [int(number.replace(",", "")) * 10000 for number in re.findall(r"([\d,]+)\s*만원", str(value))]
        prizes.append((amounts + [None] * 5)[:5])
    for index in range(5):
        output[f"PRIZE{index + 1}_AMT"] = pd.Series([row[index] for row in prizes], dtype="Int64")

    output["START_TM"] = time_column(source["START_TM_RAW"])
    start_times = source["START_TM_RAW"].map(lambda value: clean_value(value))
    start_dt = [
        None if clean_value(rc_date) is None or start_time is None
        else pd.Timestamp(datetime.combine(parse_date_value(rc_date), datetime.strptime(start_time, "%H:%M").time()))
        for rc_date, start_time in zip(source["RC_DATE"], start_times)
    ]
    output["START_DTM"] = pd.to_datetime(pd.Series(start_dt)).dt.tz_localize("Asia/Seoul")
    return {"RC_RACE": attach_metadata(output, source)}


def table_entry(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["RC_DATE", "RC_NO", "CHUL_NO", "HR_NAME", "HR_SEX", "HR_AGE", "WG_BUDAM_RAW", "JK_NAME", "TR_NAME", "OW_NAME", "RATING_RAW"], "RC_ENTRY")
    output = source.drop(columns=["ORD_RAW", "HR_BREED", *METADATA_COLUMNS], errors="ignore").copy()
    output["RC_DT"] = date_column(source["RC_DATE"])
    output["RC_NO"] = integer_column(source["RC_NO"])
    output["CHUL_NO"] = integer_column(source["CHUL_NO"])
    output["HR_NM"] = cleaned_series(source["HR_NAME"])
    output["HR_SEX_CD"] = map_values(source["HR_SEX"], {"수": "M", "암": "F", "거": "G"}, unknown="error")
    output["HR_AGE"] = integer_column(source["HR_AGE"])
    output["BUDAM_KG"] = decimal_column(source["WG_BUDAM_RAW"])
    output["JK_NM"] = cleaned_series(source["JK_NAME"])
    output["TR_NM"] = cleaned_series(source["TR_NAME"])
    output["OW_NM"] = cleaned_series(source["OW_NAME"])
    output["RATING_VAL"] = integer_column(source["RATING_RAW"])
    output = output.drop(columns=["RC_DATE", "HR_NAME", "HR_SEX", "WG_BUDAM_RAW", "JK_NAME", "TR_NAME", "OW_NAME", "RATING_RAW"])
    return {"RC_ENTRY": attach_metadata(output, source)}


def section_seconds(raw: Any) -> list[float | None]:
    value = clean_value(raw) or ""
    value = value.ljust(49)
    result: list[float | None] = []
    for index in range(7):
        token = value[index * 7:(index + 1) * 7].strip()
        match = re.fullmatch(r"(\d+):(\d+(?:\.\d+)?)", token)
        if not token:
            result.append(None)
        elif match:
            result.append(int(match.group(1)) * 60 + float(match.group(2)))
        else:
            raise ValueError(f"Invalid fixed-width section time: {token!r}")
    return result


def table_odds(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["RC_DATE", "RC_NO", "CHUL_NO", "SECTION_TIMES_RAW", "WIN_ODDS_RAW", "PLACE_ODDS_RAW"], "RC_ODDS")
    output = source.drop(columns=["ORD_RAW", *METADATA_COLUMNS], errors="ignore").copy()
    output["RC_DT"] = date_column(source["RC_DATE"])
    output["RC_NO"] = integer_column(source["RC_NO"])
    output["CHUL_NO"] = integer_column(source["CHUL_NO"])
    sections = source["SECTION_TIMES_RAW"].map(section_seconds)
    for index in range(7):
        output[f"SECT{index + 1}_SEC"] = pd.Series(sections.map(lambda values: values[index]), dtype="Float64")
    output["WIN_ODDS"] = decimal_column(source["WIN_ODDS_RAW"])
    output["PLC_ODDS"] = decimal_column(source["PLACE_ODDS_RAW"])
    return {"RC_ODDS": attach_metadata(output.drop(columns=["RC_DATE", "SECTION_TIMES_RAW", "WIN_ODDS_RAW", "PLACE_ODDS_RAW"]), source)}


def margin(value: Any) -> tuple[float | None, str]:
    value = clean_value(value)
    if value is None:
        return None, "FIRST"
    names = {"코": "NOSE", "머리": "HEAD", "목": "NECK", "동순위": "DH", "-": "NA"}
    for label, code in names.items():
        if label in value:
            return None, code
    fraction_match = re.fullmatch(r"(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)", value)
    if fraction_match:
        whole = int(fraction_match.group(1) or 0)
        numerator = int(fraction_match.group(2))
        denominator = int(fraction_match.group(3))
        if denominator == 0:
            raise ValueError(f"Invalid margin fraction: {value!r}")
        return whole + numerator / denominator, "LEN"
    fractions = {"½": 0.5, "¼": 0.25, "¾": 0.75}
    normalized = value.replace("1½", "1.5").replace("½", ".5").replace("1¼", "1.25").replace("¼", ".25").replace("1¾", "1.75").replace("¾", ".75")
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    if match:
        return float(match.group(0)), "LEN"
    raise ValueError(f"Unrecognized margin value: {value!r}")


def table_result(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["RC_DATE", "RC_NO", "ORD_RAW", "CHUL_NO", "HR_NAME", "WG_HR_RAW", "RC_TIME_RAW", "MARGIN_RAW", "PASS_ORD_RAW"], "RC_RESULT")
    output = source.drop(columns=[*METADATA_COLUMNS], errors="ignore").copy()
    output["RC_DT"] = date_column(source["RC_DATE"])
    output["RC_NO"] = integer_column(source["RC_NO"])
    output["CHUL_NO"] = integer_column(source["CHUL_NO"])
    output["HR_NM"] = cleaned_series(source["HR_NAME"])
    ord_values = cleaned_series(source["ORD_RAW"])
    allowed_ordinals = {str(value) for value in range(1, 11)} | {"94", "95"}
    unknown_ordinals = sorted({value for value in ord_values.dropna().unique() if value not in allowed_ordinals})
    if unknown_ordinals:
        raise ValueError(f"Unmapped RC_RESULT.ORD_RAW values: {unknown_ordinals}")
    output["FINISH_ORD"] = pd.to_numeric(ord_values.where(ord_values.isin([str(i) for i in range(1, 11)])), errors="coerce").astype("Int64")
    output["ENTRY_STAT_CD"] = ord_values.map(lambda value: {None: None, "94": "EXCLUDED", "95": "SCRATCHED"}.get(value, "RAN"))

    weight_values: list[tuple[int | None, int | None]] = []
    for raw in source["WG_HR_RAW"]:
        value = clean_value(raw)
        if value is None or value == "0":
            weight_values.append((None, None))
            continue
        match = re.fullmatch(r"\s*(\d+)\s*([+-]\s*\d+)?\s*", value)
        if not match:
            raise ValueError(f"Invalid WG_HR_RAW value: {value!r}")
        weight = int(match.group(1))
        diff = int(match.group(2).replace(" ", "")) if match.group(2) else None
        weight_values.append((weight, diff))
    output["HR_WGT_KG"] = pd.Series([v[0] for v in weight_values], dtype="Int64")
    output["HR_WGT_DIFF_KG"] = pd.Series([v[1] for v in weight_values], dtype="Int64")

    def parse_race_time(value: Any) -> float | None:
        value = clean_value(value)
        if value is None or not re.search(r"\d", value):
            return None
        match = re.fullmatch(r"(\d+):(\d+(?:\.\d+)?)", value)
        if not match:
            raise ValueError(f"Invalid RC_TIME_RAW value: {value!r}")
        return int(match.group(1)) * 60 + float(match.group(2))

    output["RC_TIME_SEC"] = pd.Series(source["RC_TIME_RAW"].map(parse_race_time), dtype="Float64")
    margins = source["MARGIN_RAW"].map(margin)
    output["MARGIN_LEN"] = pd.Series(margins.map(lambda value: value[0]), dtype="Float64")
    output["MARGIN_CD"] = margins.map(lambda value: value[1])
    passes: list[list[int | None]] = []
    for raw in source["PASS_ORD_RAW"]:
        tokens = str(raw).split("-")
        tokens = (tokens + [""] * 6)[:6]
        passes.append([int(token.strip()) if token.strip().isdigit() else None for token in tokens])
    for index in range(6):
        output[f"PASS_ORD_S{index + 1}"] = pd.Series([row[index] for row in passes], dtype="Int64")
    output = output.drop(columns=["RC_DATE", "ORD_RAW", "HR_NAME", "WG_HR_RAW", "RC_TIME_RAW", "MARGIN_RAW", "PASS_ORD_RAW"])
    return {"RC_RESULT": attach_metadata(output, source)}


def table_sales(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["RC_DATE", "RC_NO", "POOL_NM", "SALES_AMT_RAW"], "RC_SALES")
    total_rows = cleaned_series(source["POOL_NM"]).eq("합계")
    mapping = renamed_table(source, {"POOL_NM": "BET_TYPE_CD", "SALES_AMT_RAW": "SALES_AMT"}, drop=())
    mapping["RC_DT"] = date_column(source["RC_DATE"])
    mapping["RC_NO"] = integer_column(source["RC_NO"])
    mapping["SALES_AMT"] = integer_column(source["SALES_AMT_RAW"])
    pool_values = cleaned_series(source["POOL_NM"])
    mapping["BET_TYPE_CD"] = pool_values.map(
        lambda value: None if value == "합계" else
        map_values(pd.Series([value]), BET_TYPE_MAP, unknown="error").iloc[0]
    )
    mapping = mapping.drop(columns="RC_DATE")
    total = mapping.loc[total_rows].copy()
    normal = mapping.loc[~total_rows].copy()
    if len(total):
        total["BET_TYPE_CD"] = pd.Series([pd.NA] * len(total), dtype="string")
    return {
        "RC_SALES": attach_metadata(normal.reset_index(drop=True), source.loc[~total_rows].reset_index(drop=True)),
        "RC_SALES_TOTAL": attach_metadata(total.reset_index(drop=True), source.loc[total_rows].reset_index(drop=True)),
    }


def table_vet(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["VET_DT_RAW", "HR_NAME", "TR_GRP_NO", "VET_PLACE_NM", "VET_NM_RAW", "REPORT_DT"], "HR_VET_HIST")
    output = pd.DataFrame({
        "VET_SEQ": pd.Series(range(1, len(source) + 1), dtype="Int64"),
        "VET_DT": date_column(source["VET_DT_RAW"]),
        "HR_NM": cleaned_series(source["HR_NAME"]),
        "TR_GRP_NO": cleaned_series(source["TR_GRP_NO"]),
        "VET_PLACE_NM": cleaned_series(source["VET_PLACE_NM"]),
        "VET_NM": cleaned_series(source["VET_NM_RAW"]),
        "REPORT_DT": date_column(source["REPORT_DT"]),
    })
    main = attach_metadata(output, source)
    bridge_rows: list[dict[str, Any]] = []
    for seq, raw_names in enumerate(source["VET_NM_RAW"], start=1):
        names = [name.strip() for name in str(raw_names).split(",") if clean_value(name) is not None]
        for name in names:
            bridge_rows.append({"VET_SEQ": seq, "VET_TYPE_NM": name})
    bridge = pd.DataFrame(bridge_rows, columns=["VET_SEQ", "VET_TYPE_NM"])
    bridge["VET_SEQ"] = bridge["VET_SEQ"].astype("Int64")
    bridge = attach_metadata(bridge, source.iloc[[row["VET_SEQ"] - 1 for row in bridge_rows]].reset_index(drop=True)) if bridge_rows else bridge
    return {"HR_VET_HIST": main, "HR_VET_TYPE_BRIDGE": bridge}


def nested_json(value: Any) -> dict[str, Any]:
    value = clean_value(value)
    if value is None:
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON object stored in Bronze: {value!r}") from error
    return decoded if isinstance(decoded, dict) else {}


def table_events(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require_columns(source, ["eventType", "announcedAt", "trackRaw", "race", "horse", "change", "reason"], "RC_CHANGE_EVENT")
    races = source["race"].map(nested_json)
    horses = source["horse"].map(nested_json)
    changes = source["change"].map(nested_json)
    output = pd.DataFrame(index=source.index)
    output["EVENT_TYPE_CD"] = cleaned_series(source["eventType"]).str.upper()
    output["ANNOUNCE_DTM"] = datetime_column(source["announcedAt"], ("%Y%m%d %H:%M", "%Y-%m-%d %H:%M:%S"))
    output["RC_DT"] = pd.Series([race.get("rcDate") for race in races]).pipe(date_column)
    output["RC_NO"] = integer_column(pd.Series([race.get("rcNo") for race in races]))
    output["CHUL_NO"] = integer_column(pd.Series([horse.get("chulNo") for horse in horses]))
    output["HR_NM"] = pd.Series([clean_value(horse.get("hrName")) for horse in horses], dtype="string")
    output["BEF_JK_NM"] = pd.Series([clean_value(change.get("before")) for change in changes], dtype="string")
    output["AFT_JK_NM"] = pd.Series([clean_value(change.get("after")) for change in changes], dtype="string")
    output["BUDAM_KG"] = pd.to_numeric(
        pd.Series([clean_value(change.get("budamRaw")) for change in changes]), errors="coerce"
    ).astype("Float64")
    output["CHG_REASON_NM"] = pd.Series([clean_value(change.get("reason")) for change in changes], dtype="string")
    output["SCRATCH_REASON_NM"] = cleaned_series(source["reason"])
    track_values = source["trackRaw"].map(weather_track)
    # Track event payloads contain track status and moisture, but no weather.
    output["TRACK_STAT_CD"] = track_values.map(lambda value: value[1])
    output["TRACK_MOIST_RT"] = pd.Series(track_values.map(lambda value: value[2]), dtype="Float64")
    output["EVENT_TYPE_CD"] = map_values(output["EVENT_TYPE_CD"], {
        "JOCKEY_CHANGE": "JOCKEY_CHANGE", "SCRATCH": "SCRATCH", "TRACK_STATUS": "TRACK_STATUS",
    }, upper=True, unknown="error")
    return {"RC_CHANGE_EVENT": attach_metadata(output, source)}


TRANSFORMS: dict[str, Callable[[pd.DataFrame], dict[str, pd.DataFrame]]] = {
    "order/bet_order.parquet": table_bet_order,
    "order/bet_ticket.parquet": table_bet_ticket,
    "member/MBR_MASTER.parquet": table_member,
    "horse/HR_WEEKLY_SNAPSHOT.parquet": horse_weekly,
    "horse/TR_WEEKLY_SNAPSHOT.parquet": trainer_weekly,
    "race/RC_RACE.parquet": table_race,
    "race/RC_ENTRY.parquet": table_entry,
    "race/RC_ODDS.parquet": table_odds,
    "race/RC_RESULT.parquet": table_result,
    "race/RC_SALES.parquet": table_sales,
    "horse/HR_VET_HIST.parquet": table_vet,
    "event/race_change_events.parquet": table_events,
}


def write_parquet(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output_path.parent, suffix=".tmp.parquet", delete=False) as file:
            temporary_path = Path(file.name)
        frame.to_parquet(temporary_path, engine="pyarrow", index=False)
        actual_rows = parquet.ParquetFile(temporary_path).metadata.num_rows
        if actual_rows != len(frame):
            raise ValueError(
                f"Silver write row count mismatch for {output_path.name}: "
                f"expected {len(frame)}, found {actual_rows}"
            )
        non_string_bad = []
        for field in parquet.ParquetFile(temporary_path).schema_arrow:
            # Silver contains typed dates and measures; this read-back validates
            # that the Parquet schema is readable and has the expected row count.
            if field.name in METADATA_COLUMNS and not (
                arrow.types.is_string(field.type) or arrow.types.is_large_string(field.type)
            ):
                non_string_bad.append(field.name)
        if non_string_bad:
            raise TypeError(f"Silver metadata columns must be strings: {non_string_bad}")
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def source_output_counts(
    source: pd.DataFrame,
    outputs: dict[str, pd.DataFrame],
    relative_path: str,
) -> None:
    bronze_rows = len(source)
    silver_rows = sum(len(frame) for frame in outputs.values())
    if relative_path == "race/RC_SALES.parquet":
        if silver_rows != bronze_rows:
            raise ValueError(f"RC_SALES split count mismatch: Bronze={bronze_rows}, Silver total={silver_rows}")
    elif relative_path == "horse/HR_VET_HIST.parquet":
        if len(outputs["HR_VET_HIST"]) != bronze_rows:
            raise ValueError(f"HR_VET_HIST row count mismatch: Bronze={bronze_rows}, Silver={len(outputs['HR_VET_HIST'])}")
    else:
        if silver_rows != bronze_rows:
            raise ValueError(f"Row count mismatch for {relative_path}: Bronze={bronze_rows}, Silver={silver_rows}")


def main() -> None:
    if not BRONZE_DIR.is_dir():
        raise FileNotFoundError(f"Bronze directory not found: {BRONZE_DIR}")
    if not SILVER_DIR.is_dir():
        SILVER_DIR.mkdir(parents=True, exist_ok=True)

    bronze_files = sorted(
        (path for path in BRONZE_DIR.rglob("*.parquet") if path.is_file()),
        key=lambda path: path.relative_to(BRONZE_DIR).as_posix().casefold(),
    )
    if not bronze_files:
        raise FileNotFoundError(f"No Bronze Parquet files found under {BRONZE_DIR}")

    seen_tables: set[str] = set()
    written_tables: set[str] = set()
    for bronze_path in bronze_files:
        relative_path = bronze_path.relative_to(BRONZE_DIR).as_posix()
        transform = TRANSFORMS.get(relative_path)
        if transform is None:
            raise ValueError(f"No Silver mapping is defined for Bronze file: {relative_path}")
        bronze_frame = pd.read_parquet(bronze_path, engine="pyarrow")
        missing_metadata = sorted(set(METADATA_COLUMNS) - set(bronze_frame.columns))
        if missing_metadata:
            raise ValueError(
                f"Bronze file {relative_path} is missing lineage columns: "
                f"{', '.join(missing_metadata)}"
            )
        outputs = transform(bronze_frame)
        source_output_counts(bronze_frame, outputs, relative_path)
        source_files = sorted(
            str(value)
            for value in bronze_frame["_SRC_FILE"].dropna().unique()
        )

        duplicate_names = seen_tables.intersection(outputs)
        if duplicate_names:
            raise ValueError(f"Duplicate Silver table names: {sorted(duplicate_names)}")
        seen_tables.update(outputs)

        for table_name, silver_frame in outputs.items():
            silver_frame = normalize_string_columns(silver_frame).reset_index(drop=True)
            output_path = SILVER_DIR / f"{table_name}.parquet"
            write_parquet(silver_frame, output_path)
            written_rows = parquet.ParquetFile(output_path).metadata.num_rows
            if written_rows != len(silver_frame):
                raise ValueError(
                    f"Silver row count mismatch for {table_name}: "
                    f"expected {len(silver_frame)}, found {written_rows}"
                )
            if table_name == "RC_SALES":
                detail = "매핑 규칙에 따라 POOL_NM='합계' 행을 RC_SALES_TOTAL로 분리"
            elif table_name == "RC_SALES_TOTAL":
                detail = "RC_SALES의 POOL_NM='합계' 행을 검증용 테이블로 분리"
            elif table_name == "HR_VET_TYPE_BRIDGE":
                detail = "VET_NM_RAW의 쉼표 구분 진료명을 분리하고 VET_SEQ로 연결"
            else:
                detail = "docs/매핑_규칙서.md의 표준 컬럼·값·타입 규칙 적용"
            append_change_record(
                source_files=source_files,
                input_file=f"data/01_bronze/{relative_path}",
                output_file=f"data/02_silver/{table_name}.parquet",
                input_rows=len(bronze_frame),
                output_rows=written_rows,
                input_columns=bronze_frame.columns.tolist(),
                output_columns=silver_frame.columns.tolist(),
                detail=detail,
            )
            written_tables.add(table_name)
            print(f"{relative_path}: {len(bronze_frame)} Bronze rows -> {table_name}: {written_rows} Silver rows")

    print(f"Silver tables written: {len(written_tables)}")


if __name__ == "__main__":
    main()
