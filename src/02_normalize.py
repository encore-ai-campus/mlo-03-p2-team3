"""Bronze Parquet -> flat Silver, deterministic audit and Markdown reports.

Standalone: copy this file and install pandas/pyarrow. Use --help for paths;
use --spec JSON for a different schema. No origin files are read.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9), "KST")
NULL_MARKERS = {"", "-----"}
BET = {"WIN":"WIN", "단승":"WIN", "단식":"WIN", "PLC":"PLC", "연승":"PLC", "연식":"PLC",
       "QNL":"QNL", "복승":"QNL", "복식":"QNL", "복연":"QPL", "쌍식":"EXA", "삼복":"TRI", "삼쌍":"TLA",
       "QPL":"QPL", "EXA":"EXA", "TRI":"TRI", "TLA":"TLA"}
SEX = {"수":"M", "암":"F", "거":"G"}
WEATHER = {"맑음":"CLEAR", "흐림":"CLOUDY", "비":"RAIN", "안개":"FOG"}
TRACK = {"건조":"DRY", "양호":"GOOD", "다습":"MOIST", "포화":"SATURATED", "불량":"SLOPPY"}
REGION = {"서울특별시":"서울", "부산광역시":"부산", "대구광역시":"대구", "인천광역시":"인천",
          "광주광역시":"광주", "대전광역시":"대전", "울산광역시":"울산", "경기도":"경기",
          "경상북도":"경북", "경상남도":"경남", "전라북도":"전북", "전라남도":"전남",
          "충청북도":"충북", "충청남도":"충남", "강원도":"강원", "제주특별자치도":"제주"}
EXPECTED = {"BET_ORDER":27907, "BET_TICKET":523416, "MBR_MASTER":4383, "HR_WEEKLY_SNAPSHOT":52642,
            "TR_WEEKLY_SNAPSHOT":954, "RC_RACE":386, "RC_ENTRY":3666, "RC_ODDS":3666,
            "RC_RESULT":3666, "RC_SALES":2702, "RC_SALES_TOTAL":386, "HR_VET_HIST":1488,
            "HR_VET_TYPE_BRIDGE":1664, "RC_CHANGE_EVENT":149}


class ConversionError(ValueError):
    def __init__(self, message, code="PARSE_FAIL"):
        super().__init__(message)
        self.code = code


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value in NULL_MARKERS else value


def display(value):
    if value is None:
        return "NULL"
    if isinstance(value, tuple):
        return json.dumps([display(v) for v in value], ensure_ascii=False)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value)


def arrow_type(name):
    types = {"string":pa.string(), "int32":pa.int32(), "int64":pa.int64(),
             "date32":pa.date32(), "timestamp":pa.timestamp("ms", tz="Asia/Seoul"), "time":pa.time32("ms")}
    if name.startswith("decimal("):
        match = re.fullmatch(r"decimal\((\d+),(\d+)\)", name)
        if not match:
            raise ValueError(f"Invalid decimal type: {name}")
        return pa.decimal128(int(match[1]), int(match[2]))
    if name not in types:
        raise ValueError(f"Unsupported type: {name}")
    return types[name]


def integer(value):
    number = Decimal(value.replace(",", ""))
    if not number.is_finite() or number != number.to_integral_value():
        raise ConversionError("정수가 아닌 값")
    return int(number)


def cast(value, kind):
    if value is None:
        return None
    if kind == "string":
        return str(value)
    if kind in {"int32", "int64"}:
        number = integer(str(value))
        bits = 32 if kind == "int32" else 64
        if not -(2**(bits-1)) <= number < 2**(bits-1):
            raise ConversionError("정수 범위 초과")
        return number
    if kind.startswith("decimal("):
        typ = arrow_type(kind)
        number = Decimal(str(value).replace(",", ""))
        if not number.is_finite():
            raise ConversionError("유한 소수가 아님")
        quantized = number.quantize(Decimal(1).scaleb(-typ.scale))
        if number != quantized or abs(quantized) >= Decimal(10) ** (typ.precision-typ.scale):
            raise ConversionError("소수 정밀도/범위 초과; 반올림하지 않음")
        return quantized
    if kind == "date32":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        for pattern,regex in (("%Y%m%d",r"\d{8}"),("%Y-%m-%d",r"\d{4}-\d{2}-\d{2}"),
                              ("%Y.%m.%d",r"\d{4}\.\d{2}\.\d{2}"),("%Y/%m/%d",r"\d{4}/\d{2}/\d{2}")):
            if not re.fullmatch(regex,str(value)):
                continue
            try:
                return datetime.strptime(str(value), pattern).date()
            except ValueError:
                pass
        raise ConversionError("날짜 형식/값 오류")
    if kind == "timestamp":
        if isinstance(value, datetime):
            return value.replace(tzinfo=KST) if value.tzinfo is None else value.astimezone(KST)
        for pattern,regex in (("%Y-%m-%d %H:%M:%S",r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"),
                              ("%Y%m%d%H%M%S",r"\d{14}"),("%Y%m%d %H:%M",r"\d{8} \d{2}:\d{2}")):
            if not re.fullmatch(regex,str(value)):
                continue
            try:
                return datetime.strptime(str(value), pattern).replace(tzinfo=KST)
            except ValueError:
                pass
        raise ConversionError("일시 형식/값 오류")
    if kind == "time":
        for pattern,regex in (("%H:%M:%S",r"\d{2}:\d{2}:\d{2}"),("%H:%M",r"\d{2}:\d{2}")):
            if not re.fullmatch(regex,str(value)):
                continue
            try:
                return datetime.strptime(str(value), pattern).time()
            except ValueError:
                pass
        raise ConversionError("시각 형식/값 오류")
    raise ValueError(f"Unsupported type: {kind}")


def seconds(value):
    match = re.fullmatch(r"(\d+):([0-5]\d(?:\.\d+)?)", value)
    if not match:
        raise ConversionError("분:초 형식 오류")
    return Decimal(match[1]) * 60 + Decimal(match[2])


def mapped(value, mapping):
    if value not in mapping:
        raise ConversionError(f"코드표 밖 값: {value}", "OUT_OF_CODE")
    return mapping[value]


def convert(raw, rule):
    """Return (typed value, NULL classification). Failed conversions are logged by caller."""
    op = rule.get("op", "text")
    values = tuple(clean(v) for v in raw) if isinstance(raw, tuple) else (clean(raw),)
    value = values[0]
    missing = "SOURCE_NULL" if raw is None else "MARKER_NULL" if isinstance(raw,str) and raw.strip()=="-----" else "EMPTY"
    note = ""
    if op == "margin_code":
        text = "" if value is None else value
        if text in {"", "코", "머리", "목", "동순위", "-"}:
            value = {"":"FIRST", "코":"NOSE", "머리":"HEAD", "목":"NECK", "동순위":"DH", "-":"NA"}[text]
        else:
            margin_number(text)
            value = "LEN"
    elif op == "channel":
        if value is None:
            value = "UNKNOWN"
        elif re.fullmatch(r"OTB(0[1-9]|[12]\d|3[0-7])", value):
            value = "OTB"
        else:
            value = mapped(value, {"ONSITE":"ONSITE", "APP":"APP"})
    elif op == "branch":
        if value is not None and re.fullmatch(r"OTB(0[1-9]|[12]\d|3[0-7])", value):
            value = value[3:]
        elif value is None or value in {"ONSITE", "APP"}:
            value, note = None, "NOT_OTB"
        else:
            raise ConversionError("지점 코드표 밖 값", "OUT_OF_CODE")
    elif op == "external":
        value = "Y" if value == "외부마" else "N"
    elif value is None:
        return None, missing
    elif op == "text":
        pass
    elif op == "upper":
        value = value.upper()
    elif op == "map":
        value = mapped(value, rule["mapping"])
    elif op == "region":
        value = mapped(value, {**{v:v for v in REGION.values()}, **REGION})
    elif op == "grade":
        value = mapped(value, {**{f"제{i}":str(i) for i in range(1,7)}, "미":"NONE"})
    elif op == "tr_name":
        if value == "외부마":
            value, note = None, "EXTERNAL_HORSE"
    elif op == "intro_amount" or op == "intro_type":
        if value == "자가생산":
            value, note = (None, "SELF_BRED") if op == "intro_amount" else ("자가생산", "")
        else:
            match = re.fullmatch(r"([\d,]+)천원\(([^()]+)\)", value)
            if not match:
                raise ConversionError("도입 가격 형식 오류")
            value = integer(match[1])*1000 if op == "intro_amount" else match[2].strip()
    elif op in {"race_grade", "burden_type"}:
        match = re.fullmatch(r"제([1-6])등급(핸디캡|별정A)?|제(OPEN)", value)
        if not match:
            raise ConversionError("경주 등급 코드표 밖 값", "OUT_OF_CODE")
        if op == "race_grade":
            value = match[1] or "OPEN"
        else:
            value = {"핸디캡":"HANDICAP", "별정A":"SPECIAL_A", None:None}[match[2]]
            note = "NO_BURDEN_TYPE" if value is None else ""
    elif op in {"horse_class", "race_title"}:
        match = re.fullmatch(r"(?:핸디캡\s*)?(제주마)(.*)", value)
        if not match:
            raise ConversionError("경주 조건 형식 오류")
        value = match[1] if op == "horse_class" else match[2].strip()
        if op == "race_title" and value in {"", "일반"}:
            value, note = None, "GENERAL_RACE"
    elif op in {"weather", "track", "moisture", "event_track", "event_moisture"}:
        if op.startswith("event_"):
            match = re.fullmatch(r"(건조|양호|다습|포화|불량)\s*(?:\(\s*(\d+(?:\.\d+)?)%\))?", value)
            if not match:
                raise ConversionError("이벤트 주로 형식 오류")
            value = mapped(match[1], TRACK) if op == "event_track" else match[2]
        else:
            match = re.fullmatch(r"날씨:\s*(맑음|흐림|비|안개)\s+주로:\s*(건조|양호|다습|포화|불량)\s*(?:\(\s*(\d+(?:\.\d+)?)%\))?", value)
            if not match:
                raise ConversionError("날씨/주로 형식 오류")
            value = mapped(match[1], WEATHER) if op == "weather" else mapped(match[2], TRACK) if op == "track" else match[3]
        note = "NO_MOISTURE" if value is None else ""
    elif op == "prize":
        amounts = re.findall(r"([\d,]+)만원", value)
        if len(amounts) != 5:
            raise ConversionError("순위상금 5개 형식 오류")
        value = integer(amounts[rule["index"]])*10000
    elif op == "digits":
        pattern = rule["pattern"]
        match = re.fullmatch(pattern, value)
        if not match:
            raise ConversionError("단위 포함 정수 형식 오류")
        value = match[1]
    elif op == "start_datetime":
        if any(v is None for v in values):
            return None, "MISSING_COMPONENT"
        value = datetime.combine(cast(values[0], "date32"), cast(values[1], "time"), tzinfo=KST)
    elif op in {"finish", "entry_status"}:
        number = integer(value)
        if number in {94,95}:
            value, note = (None, "NOT_RAN") if op == "finish" else ({94:"EXCLUDED",95:"SCRATCHED"}[number], "")
        elif 1 <= number <= 10:
            value = number if op == "finish" else "RAN"
        else:
            raise ConversionError("출전 상태 코드표 밖 값", "OUT_OF_CODE")
    elif op in {"weight", "weight_diff"}:
        match = re.fullmatch(r"(\d+)([+-]\d+)?", value)
        if not match:
            raise ConversionError("마체중 형식 오류")
        if int(match[1]) == 0:
            value, note = None, "NOT_RAN_WEIGHT"
        else:
            value = match[1] if op == "weight" else match[2]
            note = "FIRST_MEASUREMENT" if value is None else ""
    elif op == "seconds":
        if value in {"경주제외", "출주취소"}:
            value, note = None, "NOT_RAN"
        else:
            value = seconds(value)
    elif op == "section":
        # Do not trim the whole field before fixed-width slicing.
        original = str(raw)
        if len(original) > 49 or len(original) < 1:
            raise ConversionError("구간 고정폭 길이 오류")
        part = clean(original.ljust(49)[rule["index"]*7:(rule["index"]+1)*7])
        value = None if part is None else seconds(part)
        note = "NO_SECTION" if value is None else ""
    elif op == "pass_order":
        parts = value.split("-")
        if len(parts) != 6:
            if values[1] in {"94","95"} and all(not p.strip() for p in parts):
                return None, "D-NORM-001_NO_RUN_RECORD"
            raise ConversionError("통과 순위 6개 위치 형식 오류")
        value = clean(parts[rule["index"]])
        note = "NO_PASS_POSITION" if value is None else ""
    elif op == "margin_length":
        if value in {"코", "머리", "목", "동순위", "-"}:
            value, note = None, "NON_NUMERIC_MARGIN"
        else:
            value = margin_number(value)
    else:
        raise ValueError(f"Unknown operation: {op}")
    value = cast(value, rule["type"])
    if value is not None and "allowed" in rule and value not in rule["allowed"]:
        raise ConversionError(f"코드표 밖 값: {value}", "OUT_OF_CODE")
    return value, note


def margin_number(value):
    match = re.fullmatch(r"(\d+)?([½¼¾])?", value)
    if not match or not any(match.groups()):
        raise ConversionError("착차 형식 오류")
    return Decimal(match[1] or "0") + {None:Decimal(0), "½":Decimal('.5'), "¼":Decimal('.25'), "¾":Decimal('.75')}[match[2]]


def column(source, target, kind="string", op="text", **options):
    return dict(source=source, target=target, type=kind, op=op, **options)


def default_specs():
    c = column
    def identity(names, kind="string"):
        return [c(n,n,kind) for n in names.split()]
    def basic_race():
        return [c("RC_DATE","RC_DT","date32"), c("RC_NO","RC_NO","int32")]
    def performance():
        return [c(f"{prefix}_{suffix}", f"{prefix}_{target}", "int32")
                for prefix in ("TOT","Y1") for suffix,target in (("RC_CNT","RC_CNT"),("1ST","1ST_CNT"),("2ND","2ND_CNT"),("3RD","3RD_CNT"))]
    specs = {
      "BET_ORDER": dict(input="bet_order", columns=[
        c("order_no","ORDER_NO"),c("order_type_cd","ORDER_TYPE_CD",allowed=["SALE","CANCEL"]),
        c("orig_order_no","ORIG_ORDER_NO"),c("member_no","MBR_NO",op="upper"),
        c("channel_cd","CHNL_CD",op="channel"),c("channel_cd","OTB_BRANCH_NO",op="branch"),
        c("sale_dtm","SALE_DTM","timestamp"),c("biz_date","BIZ_DT","date32"),
        c("ticket_cnt","TICKET_CNT","int32"),c("total_amt","TOTAL_AMT","int64")]),
      "BET_TICKET": dict(input="bet_ticket",drop=["unit_amt"],columns=[
        c("order_no","ORDER_NO"),c("ticket_seq","TICKET_SEQ","int32"),c("rc_date","RC_DT","date32"),
        c("rc_no","RC_NO","int32"),c("bet_type_cd","BET_TYPE_CD",op="map",mapping=BET),
        c("chul_no","CHUL_NO","int32"),c("hr_name","HR_NM"),c("chul_no2","CHUL_NO2","int32"),
        c("hr_name2","HR_NM2"),c("ticket_cnt","UNIT_CNT","int32"),c("bet_amt","BET_AMT","int32"),
        c("ticket_status","TICKET_STAT_CD",op="upper",allowed=["SOLD","CANCEL","VOID"])]),
      "MBR_MASTER": dict(input="MBR_MASTER",columns=[c("MBR_NO","MBR_NO"),c("BIRTH_DT","BIRTH_DT","date32"),
        c("JOIN_DT","JOIN_DT","date32"),c("REGION_NM","REGION_CD",op="region"),
        c("MBR_GRADE_CD","MBR_GRADE_CD",allowed=["VIP","GOLD","NORMAL"]),
        c("MBR_STAT_CD","MBR_STAT_CD",allowed=["10","20","90"])]),
      "HR_WEEKLY_SNAPSHOT": dict(input="HR_WEEKLY_SNAPSHOT",drop=["PRD_NM"],columns=[
        c("SNAPSHOT_DT","SNAPSHOT_DT","date32"),c("HR_NAME","HR_NM"),c("SEX_NM","HR_SEX_CD",op="map",mapping=SEX),
        c("BIRTH_RAW","HR_BIRTH_DT","date32"),c("AGE_RAW","HR_AGE","int32"),c("GRADE_RAW","HR_GRADE_CD",op="grade"),
        c("TR_GRP_NO","TR_GRP_NO"),c("TR_NAME","TR_NM",op="tr_name"),c("TR_NAME","TR_EXTERNAL_YN",op="external"),
        c("OW_NAME","OW_NM"),*performance(),c("PRIZE_AMT_RAW","PRIZE_AMT","int64"),
        c("RATING_RAW","RATING_VAL","int32"),c("INTRO_PRICE_RAW","INTRO_AMT","int64",op="intro_amount"),
        c("INTRO_PRICE_RAW","INTRO_TYPE_NM",op="intro_type"),c("SIRE_NAME","SIRE_NM"),c("DAM_NAME","DAM_NM")]),
      "TR_WEEKLY_SNAPSHOT": dict(input="TR_WEEKLY_SNAPSHOT",columns=[c("SNAPSHOT_DT","SNAPSHOT_DT","date32"),
        c("TR_NAME","TR_NM"),c("GRP_NO","TR_GRP_NO"),c("BIRTH_RAW","TR_BIRTH_DT","date32"),
        c("AGE_RAW","TR_AGE","int32"),c("DEBUT_RAW","TR_DEBUT_DT","date32"),*performance()]),
      "RC_RACE": dict(input="RC_RACE",drop=["TITLE_RAW","RC_DOW","DIVIDEND_RAW"],columns=[*basic_race(),
        c("MEET_NM","MEET_CD",op="map",mapping={"제주":"JEJU"}),
        c("RC_DAY_RAW","RC_DAY_SEQ","int32",op="digits",pattern=r"제\s*(\d+)일"),
        c("RC_DIST_RAW","RC_DIST_M","int32",op="digits",pattern=r"(\d+)M"),
        c("RANK_RAW","RC_GRADE_CD",op="race_grade"),c("RANK_RAW","BUDAM_TYPE_CD",op="burden_type"),
        c("RC_COND_RAW","HR_CLASS_NM",op="horse_class"),c("RC_COND_RAW","RC_TITLE_NM",op="race_title"),
        c("WEATHER_TRACK_RAW","WEATHER_CD",op="weather"),c("WEATHER_TRACK_RAW","TRACK_STAT_CD",op="track"),
        c("WEATHER_TRACK_RAW","TRACK_MOIST_RT","decimal(5,1)",op="moisture"),
        *[c("PRIZE_RAW",f"PRIZE{i+1}_AMT","int64",op="prize",index=i) for i in range(5)],
        c("START_TM_RAW","START_TM","time"),c(["RC_DATE","START_TM_RAW"],"START_DTM","timestamp",op="start_datetime")]),
      "RC_ENTRY": dict(input="RC_ENTRY",drop=["ORD_RAW","HR_BREED"],columns=[*basic_race(),
        c("CHUL_NO","CHUL_NO","int32"),c("HR_NAME","HR_NM"),c("HR_SEX","HR_SEX_CD",op="map",mapping=SEX),
        c("HR_AGE","HR_AGE","int32"),c("WG_BUDAM_RAW","BUDAM_KG","decimal(4,1)"),
        c("JK_NAME","JK_NM"),c("TR_NAME","TR_NM"),c("OW_NAME","OW_NM"),c("RATING_RAW","RATING_VAL","int32")]),
      "RC_ODDS": dict(input="RC_ODDS",drop=["ORD_RAW"],columns=[*basic_race(),c("CHUL_NO","CHUL_NO","int32"),
        *[c("SECTION_TIMES_RAW",f"SECT{i+1}_SEC","decimal(5,1)",op="section",index=i) for i in range(7)],
        c("WIN_ODDS_RAW","WIN_ODDS","decimal(6,1)"),c("PLACE_ODDS_RAW","PLC_ODDS","decimal(6,1)")]),
      "RC_RESULT": dict(input="RC_RESULT",columns=[*basic_race(),
        c("ORD_RAW","FINISH_ORD","int32",op="finish"),c("ORD_RAW","ENTRY_STAT_CD",op="entry_status"),
        c("CHUL_NO","CHUL_NO","int32"),c("HR_NAME","HR_NM"),c("WG_HR_RAW","HR_WGT_KG","int32",op="weight"),
        c("WG_HR_RAW","HR_WGT_DIFF_KG","int32",op="weight_diff"),c("RC_TIME_RAW","RC_TIME_SEC","decimal(5,1)",op="seconds"),
        c("MARGIN_RAW","MARGIN_LEN","decimal(5,2)",op="margin_length"),c("MARGIN_RAW","MARGIN_CD",op="margin_code"),
        *[c(["PASS_ORD_RAW","ORD_RAW"],f"PASS_ORD_S{i+1}","int32",op="pass_order",index=i) for i in range(6)]]),
      "RC_SALES": dict(input="RC_SALES",split_sales=True,columns=[*basic_race(),
        c("POOL_NM","BET_TYPE_CD",op="map",mapping=BET),c("SALES_AMT_RAW","SALES_AMT","int64")]),
      "HR_VET_HIST": dict(input="HR_VET_HIST",bridge=True,columns=[c("VET_DT_RAW","VET_DT","date32"),
        c("HR_NAME","HR_NM"),c("TR_GRP_NO","TR_GRP_NO"),c("VET_PLACE_NM","VET_PLACE_NM"),
        c("VET_NM_RAW","VET_NM"),c("REPORT_DT","REPORT_DT","date32")]),
      "RC_CHANGE_EVENT": dict(input="race_change_events",columns=[
        c("eventType","EVENT_TYPE_CD",allowed=["JOCKEY_CHANGE","SCRATCH","TRACK_STATUS"]),
        c("announcedAt","ANNOUNCE_DTM","timestamp"),c("race.rcDate","RC_DT","date32"),
        c("race.rcNo","RC_NO","int32"),c("horse.chulNo","CHUL_NO","int32"),c("horse.hrName","HR_NM"),
        c("change.before","BEF_JK_NM"),c("change.after","AFT_JK_NM"),
        c("change.budamRaw","BUDAM_KG","decimal(4,1)"),c("change.reason","CHG_REASON_NM"),
        c("reason","SCRATCH_REASON_NM"),c("trackRaw","TRACK_STAT_CD",op="event_track"),
        c("trackRaw","TRACK_MOIST_RT","decimal(5,1)",op="event_moisture")])}
    return specs


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_values(table, path):
    parent, *children = path.split(".")
    if parent not in table.column_names:
        raise ValueError(f"Missing source column: {path}")
    values = table[parent].to_pylist()
    for child in children:
        values = [value.get(child) if isinstance(value, dict) else None for value in values]
    return values


def source_label(source):
    return " + ".join(source) if isinstance(source, list) else source


def rule_id(rule):
    op = rule.get("op", "text")
    if op == "pass_order":
        return "MAP-07;D-NORM-001"
    if op in {"text", "upper"}:
        return "MAP-01;MAP-02;MAP-04;MAP-05;MAP-10"
    return "MAP-01;MAP-04;MAP-06;MAP-07;MAP-10"


class Audit:
    def __init__(self):
        self.dictionary = []
        self.changes = []
        self.issues = []
        self.sources = []
        self.outputs = {}

    def apply(self, name, source_table, indexes, rules, bronze_relative, audit_raw_values=None):
        result = {}
        for rule in rules:
            label = source_label(rule["source"])
            if isinstance(rule["source"], list):
                arrays = [source_values(source_table, path) for path in rule["source"]]
                raw_values = [tuple(values[i] for values in arrays) for i in indexes]
            else:
                values = source_values(source_table, rule["source"])
                raw_values = [values[i] for i in indexes]
            @lru_cache(maxsize=100000)
            def evaluate(raw):
                try:
                    return (*convert(raw, rule), "")
                except (ConversionError, ValueError, InvalidOperation, OverflowError) as exc:
                    return None, getattr(exc, "code", "PARSE_FAIL"), str(exc)
            typed = []
            changed = Counter()
            trim_count = 0
            type_count = 0
            issue_counts = Counter()
            null_reasons = Counter()
            target = rule["target"]
            for i, raw in zip(indexes, raw_values):
                value, reason, error = evaluate(raw)
                audit_raw = raw if audit_raw_values is None else audit_raw_values[i]
                typed.append(value)
                if not isinstance(raw, tuple) and isinstance(raw,str) and raw != raw.strip():
                    trim_count += 1
                if value is not None and type(raw) is not type(value):
                    type_count += 1
                if display(audit_raw) != display(value) or (audit_raw is None) != (value is None):
                    changed[(display(audit_raw), display(value), value is None)] += 1
                if value is None:
                    null_reasons[reason or "SOURCE_NULL"] += 1
                if reason in {"PARSE_FAIL", "OUT_OF_CODE"}:
                    issue_counts[reason] += 1
                # Any non-empty original value that becomes NULL remains traceable.
                nonempty = any(x is not None and str(x).strip() != "" for x in raw) if isinstance(raw,tuple) else raw is not None and str(raw).strip() != ""
                if error or (value is None and nonempty):
                    self.issues.append(dict(table=name, source_column=label, standard_column=target,
                                            source_row_no=i+1, bronze_file=bronze_relative,
                                            raw_value=display(audit_raw), issue_code=reason if error else "RULE_NULL",
                                            reason=error or reason, rule_id=rule_id(rule)))
            result[target] = pa.array(typed, type=arrow_type(rule["type"]))
            self.dictionary.append(dict(table=name, source_column=label, standard_column=target,
                                        operation=rule.get("audit_operation",rule.get("op", "text")), standard_type=str(arrow_type(rule["type"])),
                                        source_rows=len(indexes), rename_rows=len(indexes) if label != target else 0,
                                        type_changed_rows=type_count, value_changed_rows=sum(changed.values()),
                                        trim_rows=trim_count, null_rows=sum(value is None for value in typed),
                                        parse_fail_rows=issue_counts["PARSE_FAIL"], out_of_code_rows=issue_counts["OUT_OF_CODE"],
                                        null_reasons=json.dumps(dict(sorted(null_reasons.items())),ensure_ascii=False),
                                        rule_id=rule_id(rule), rule=json.dumps(rule,ensure_ascii=False,sort_keys=True)))
            for (raw, value, is_null), count in sorted(changed.items()):
                self.changes.append(dict(table=name, source_column=label, standard_column=target,
                                         raw_value=raw, standard_value=value, count=count, standard_is_null=is_null, rule_id=rule_id(rule)))
        return result

    def derived(self, name, target, kind, values, source, operation):
        self.dictionary.append(dict(table=name, source_column=source, standard_column=target,
                                    operation=operation, standard_type=str(arrow_type(kind)), source_rows=len(values),
                                    rename_rows=0, type_changed_rows=0, value_changed_rows=0, trim_rows=0,
                                    null_rows=sum(v is None for v in values), parse_fail_rows=0, out_of_code_rows=0,
                                    null_reasons="{}", rule_id="TRACE-01", rule=operation))
        return pa.array(values, type=arrow_type(kind))

    def excluded(self, name, source_table, columns):
        for name_in in columns:
            self.dictionary.append(dict(table=name,source_column=name_in,standard_column="(제외)",
                                        operation="exclude_column",standard_type="—",source_rows=source_table.num_rows,
                                        rename_rows=0,type_changed_rows=0,value_changed_rows=0,trim_rows=0,null_rows=0,
                                        parse_fail_rows=0,out_of_code_rows=0,null_reasons="{}",rule_id="MAP-09",
                                        rule="규칙서 9장: Silver 컬럼에서 제외; Bronze 원천값 보존"))


def add_trace(audit, name, arrays, original, indexes, relative, vet=False):
    if vet:
        arrays["VET_SEQ"] = audit.derived(name,"VET_SEQ","int32",[i+1 for i in indexes],"Bronze 행 번호","1-based source row number")
    arrays["_SRC_ROW_NO"] = audit.derived(name,"_SRC_ROW_NO","int64",[i+1 for i in indexes],"Bronze 행 번호","1-based source row number")
    arrays["_SRC_BRONZE_FILE"] = audit.derived(name,"_SRC_BRONZE_FILE","string",[relative]*len(indexes),"Bronze 상대 경로","relative path from input root")
    return pa.table(arrays)


def preflight(input_root, output_root, meta_root, docs_root, specs):
    roots = [Path(p).resolve() for p in (input_root, output_root, meta_root, docs_root)]
    input_root, output_root, meta_root, docs_root = roots
    if not input_root.is_dir():
        raise ValueError(f"Missing Bronze folder: {input_root}")
    for a in roots:
        for b in roots:
            if a != b and (a in b.parents or b in a.parents):
                raise ValueError("입력/출력/meta/docs 경로는 서로 겹칠 수 없습니다.")
    if len(set(roots)) != 4:
        raise ValueError("입력/출력/meta/docs는 서로 다른 폴더여야 합니다.")
    candidates = sorted(input_root.rglob("*.parquet"))
    planned = []
    inputs = set()
    outputs = set()
    for name, spec in specs.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"Invalid table name: {name}")
        matches = [p for p in candidates if p.stem == spec["input"]]
        if len(matches) != 1:
            raise ValueError(f"{name}: 입력 파일 이름 {spec['input']}은 정확히 한 번 있어야 합니다: {matches}")
        source = matches[0]
        if input_root not in source.resolve().parents or source in inputs:
            raise ValueError(f"잘못된 경로 또는 중복 입력: {source}")
        inputs.add(source)
        schema = pq.read_schema(source)
        columns = spec["columns"]
        targets = [r["target"] for r in columns]
        if len(set(targets)) != len(targets) or any(not re.fullmatch(r"[A-Z][A-Z0-9_]*",t) for t in targets):
            raise ValueError(f"중복/잘못된 출력 컬럼: {name}")
        reserved = {"_SRC_ROW_NO","_SRC_BRONZE_FILE"}
        if spec.get("bridge"):
            reserved.add("VET_SEQ")
        if reserved.intersection(targets):
            raise ValueError(f"추적 키 이름 충돌: {name}")
        if set(spec.get("drop",[])) - set(schema.names):
            raise ValueError(f"{name}: 제외 설정에 원천에 없는 컬럼이 있습니다.")
        covered = set(spec.get("drop", [])) | {"source_file","ingested_at"}
        for rule in columns:
            arrow_type(rule["type"])
            paths = rule["source"] if isinstance(rule["source"],list) else [rule["source"]]
            for path in paths:
                parent = path.split(".")[0]
                if parent not in schema.names:
                    raise ValueError(f"{name}: 원천 컬럼 없음: {path}")
                covered.add(parent)
        uncovered = set(schema.names) - covered
        if uncovered:
            raise ValueError(f"{name}: 미매핑 원천 컬럼: {sorted(uncovered)}. columns 또는 drop에 명시하세요.")
        names = [name] + (["RC_SALES_TOTAL"] if spec.get("split_sales") else []) + (["HR_VET_TYPE_BRIDGE"] if spec.get("bridge") else [])
        if outputs.intersection(names):
            raise ValueError(f"출력 테이블 이름 충돌: {names}")
        outputs.update(names)
        planned.append((name,spec,source))
    if set(candidates) != inputs:
        raise ValueError(f"규칙에 없는 Bronze 파일: {sorted(set(candidates)-inputs)}")
    stale = [p.name for p in output_root.rglob("*.parquet") if p.parent != output_root or p.stem not in outputs] if output_root.exists() else []
    if stale:
        raise ValueError(f"이전/다른 규칙의 출력이 있습니다. 별도 출력 폴더를 지정하세요: {stale}")
    return planned


def build_table(name, spec, original, relative, audit):
    rules = list(spec["columns"])
    covered = {path for r in rules for path in (r["source"] if isinstance(r["source"],list) else [r["source"]])}
    if "source_file" in original.column_names and "source_file" not in covered:
        rules.append(column("source_file","SOURCE_FILE"))
    if "ingested_at" in original.column_names and "ingested_at" not in covered:
        rules.append(column("ingested_at","INGESTED_AT","timestamp"))
    targets = [r["target"] for r in rules]
    if len(set(targets)) != len(targets):
        raise ValueError(f"출처 컬럼과 출력 이름 충돌: {name}")
    indexes = list(range(original.num_rows))
    total_indexes = []
    if spec.get("split_sales"):
        pool = source_values(original,"POOL_NM")
        total_indexes = [i for i,v in enumerate(pool) if clean(v) == "합계"]
        indexes = [i for i,v in enumerate(pool) if clean(v) != "합계"]
    arrays = audit.apply(name,original,indexes,rules,relative)
    outputs = {name:add_trace(audit,name,arrays,original,indexes,relative,vet=bool(spec.get("bridge")))}
    audit.excluded(name,original,spec.get("drop",[]))
    if spec.get("split_sales"):
        total_name = "RC_SALES_TOTAL"
        total_rules = [r for r in rules if r["source"] != "POOL_NM"]
        total_arrays = audit.apply(total_name,original,total_indexes,total_rules,relative)
        outputs[total_name] = add_trace(audit,total_name,total_arrays,original,total_indexes,relative)
        audit.dictionary.append(dict(table=total_name,source_column="POOL_NM",standard_column="(행 분리)",
            operation="split_total_rows",standard_type="—",source_rows=len(total_indexes),rename_rows=0,type_changed_rows=0,
            value_changed_rows=0,trim_rows=0,null_rows=0,parse_fail_rows=0,out_of_code_rows=0,null_reasons="{}",
            rule_id="MAP-03;MAP-10",rule="POOL_NM='합계' 행은 RC_SALES_TOTAL로 이동; 행 제거 없음"))
    if spec.get("bridge"):
        bridge_name = "HR_VET_TYPE_BRIDGE"
        # Each token keeps its source row. Empty tokens are not silently discarded.
        vet_values = source_values(original,"VET_NM_RAW")
        rows = []
        token_no = []
        tokens = []
        for i,value in enumerate(vet_values):
            if clean(value) is None:
                continue
            for j,token in enumerate(str(value).split(","),1):
                if clean(token) is None:
                    raise ValueError(f"진료명 빈 항목: {relative}:{i+1}")
                rows.append(i)
                token_no.append(j)
                tokens.append(token)
        token_table = pa.table({"VET_NM_RAW":tokens})
        token_rules = [column("VET_NM_RAW","VET_TYPE_NM",audit_operation="comma_split_and_trim")]
        token_arrays = audit.apply(bridge_name,token_table,list(range(len(tokens))),token_rules,relative,
                                   audit_raw_values=[vet_values[i] for i in rows])
        # Correct source-row attribution in token-level audit entries.
        for issue in audit.issues:
            if issue["table"] == bridge_name:
                issue["source_row_no"] = rows[issue["source_row_no"]-1]+1
        token_arrays["VET_SEQ"] = audit.derived(bridge_name,"VET_SEQ","int32",[i+1 for i in rows],"VET_NM_RAW","parent VET_SEQ")
        token_arrays["VET_TYPE_SEQ"] = audit.derived(bridge_name,"VET_TYPE_SEQ","int32",token_no,"VET_NM_RAW","1-based comma token position")
        for source_col,target in (("source_file","SOURCE_FILE"),("ingested_at","INGESTED_AT")):
            if source_col in original.column_names:
                raw_values = source_values(original,source_col)
                kind = "timestamp" if source_col == "ingested_at" else "string"
                vals = [cast(clean(raw_values[i]),kind) for i in rows]
                token_arrays[target] = audit.derived(bridge_name,target,kind,vals,source_col,"inherit parent trace")
        outputs[bridge_name] = add_trace(audit,bridge_name,token_arrays,original,rows,relative)
    return outputs


def check_outputs(outputs, sources, audit, reference=False):
    checks = []
    def check(name,expected,actual):
        checks.append(dict(check=name,expected=expected,actual=actual,passed=expected==actual))
    for source in sources:
        name = source["table"]
        original = pq.read_table(source["path"])
        base = outputs[name]
        tables = [base] + ([outputs["RC_SALES_TOTAL"]] if source["split_sales"] else [])
        row_ids = [n for table in tables for n in table["_SRC_ROW_NO"].to_pylist()]
        check(name+" input/output rows",original.num_rows,sum(t.num_rows for t in tables))
        check(name+" each input row once",True,sorted(row_ids)==list(range(1,original.num_rows+1)))
        for table in tables:
            check(name+" source file trace",True,all(v==source["relative"] for v in table["_SRC_BRONZE_FILE"].to_pylist()))
            if "SOURCE_FILE" in table.column_names and "source_file" in original.column_names:
                raw = original["source_file"].to_pylist()
                check(name+" original file trace",True,all(v==clean(raw[i-1]) for v,i in zip(table["SOURCE_FILE"].to_pylist(),table["_SRC_ROW_NO"].to_pylist())))
        if source["bridge"]:
            bridge = outputs["HR_VET_TYPE_BRIDGE"]
            raw = original["VET_NM_RAW"].to_pylist()
            expected_tokens = [(i+1,j+1,clean(token)) for i,v in enumerate(raw) if clean(v) is not None
                               for j,token in enumerate(str(v).split(","))]
            actual_tokens = list(zip(bridge["VET_SEQ"].to_pylist(),bridge["VET_TYPE_SEQ"].to_pylist(),bridge["VET_TYPE_NM"].to_pylist()))
            check("bridge item count",len(expected_tokens),bridge.num_rows)
            check("bridge item/order/parent equality",True,expected_tokens==actual_tokens)
            check("bridge parents exist",True,set(bridge["VET_SEQ"].to_pylist()) <= set(base["VET_SEQ"].to_pylist()))
        check(name+" Bronze unchanged",source["sha256"],digest(source["path"]))
    for name,table in outputs.items():
        check(name+" column naming",True,all(re.fullmatch(r"_?[A-Z][A-Z0-9_]*",col) is not None for col in table.column_names))
        check(name+" timezones",True,all(field.type.tz=="Asia/Seoul" for field in table.schema if pa.types.is_timestamp(field.type)))
    failures = sum(d["parse_fail_rows"] for d in audit.dictionary)
    outside = sum(d["out_of_code_rows"] for d in audit.dictionary)
    check("PARSE_FAIL",0,failures)
    check("OUT_OF_CODE",0,outside)
    if reference:
        for name,expected in EXPECTED.items():
            check(name+" reference rows",expected,outputs[name].num_rows if name in outputs else -1)
        for name,col,expected in [("MBR_MASTER","BIRTH_DT",27),("RC_ODDS","WIN_ODDS",22),
                                  ("RC_ODDS","PLC_ODDS",22),("RC_RACE","TRACK_MOIST_RT",21),
                                  ("RC_RESULT","FINISH_ORD",22)]:
            check(name+"."+col+" reference NULL",expected,outputs[name][col].null_count)
        check("external horse Y",25428,pc.sum(pc.equal(outputs["HR_WEEKLY_SNAPSHOT"]["TR_EXTERNAL_YN"],"Y")).as_py())
        sales = outputs["RC_SALES_TOTAL"].select(["RC_DT","RC_NO"]).to_pandas()
        check("sales totals unique race",386,len(sales.drop_duplicates()))
        check("multiple diagnoses source rows",176,sum(1 for count in Counter(outputs["HR_VET_TYPE_BRIDGE"]["VET_SEQ"].to_pylist()).values() if count>1))
    return checks


def markdown_table(headers,rows):
    def escape(value):
        # repr-like JSON quoting preserves leading/trailing spaces in value examples.
        return str(value).replace("|","&#124;").replace("\r","").replace("\n","<br>")
    return "\n".join(["| "+" | ".join(map(escape,headers))+" |",
                       "| "+" | ".join("---" for _ in headers)+" |"]+
                      ["| "+" | ".join(map(escape,row))+" |" for row in rows])


def document_path(path,base):
    try:
        return os.path.relpath(path,base).replace(os.sep,"/")
    except ValueError:  # Windows paths on different drives
        return Path(path).as_posix()


def report_documents(audit,outputs,checks,input_root,output_root,reference,meta_root,docs_root,is_default):
    errors = [row for row in checks if not row["passed"]]
    by_column = {}
    for entry in audit.changes:
        by_column.setdefault((entry["table"],entry["standard_column"]),[]).append(entry)
    labels = {
        "text":"TRIM·빈값 처리 후 지정 타입 변환", "upper":"TRIM·대문자·코드 확인",
        "map":"원천값을 명시된 표준 코드로 매핑", "region":"지역명을 공용 약칭으로 매핑",
        "grade":"말 등급을 표준 코드로 매핑", "tr_name":"외부마 표시를 NULL로 분리",
        "external":"외부마 여부 Y/N 생성", "channel":"OTB 지점 분리·채널 코드화·빈값 UNKNOWN",
        "branch":"OTB 지점번호 분리·앞자리 0 보존", "intro_amount":"도입 가격 분리·천원→원",
        "intro_type":"도입 유형 분리", "race_grade":"경주 등급 분리", "burden_type":"부담 방식 분리",
        "horse_class":"경주 조건에서 마종 분리", "race_title":"경주명 분리·일반 경주는 NULL",
        "weather":"날씨 원문을 코드로 분리", "track":"주로 상태 원문을 코드로 분리",
        "moisture":"함수율 분리·표시 없으면 NULL", "event_track":"이벤트 주로 상태 코드화",
        "event_moisture":"이벤트 함수율 분리", "prize":"순위상금 분리·만원→원",
        "digits":"규정된 단위 표현에서 정수 추출", "start_datetime":"경주일과 출발 시각을 KST 일시로 결합",
        "finish":"착순 분리·94/95는 NULL", "entry_status":"출전 상태 코드 분리",
        "weight":"마체중 분리·미출전 0은 NULL", "weight_diff":"체중 증감 분리·첫 측정/미출전 NULL",
        "seconds":"분:초를 초로 환산·미출전 표현 NULL", "section":"7글자 고정폭 위치별 구간→초",
        "pass_order":"통과 순위 6개 위치 분리·기록 없는 위치 NULL",
        "margin_length":"숫자·분수 착차를 소수로 변환", "margin_code":"착차 유형 코드화·빈값 FIRST",
        "comma_split_and_trim":"원천 진료명을 쉼표로 분리·항목 공백 제거",
        "exclude_column":"규칙서 9장에 따라 컬럼 제외·Bronze 보존",
        "split_total_rows":"합계 행을 별도 테이블로 분리·입력 행 보존",
        "1-based source row number":"Bronze의 1부터 시작하는 행 번호",
        "relative path from input root":"입력 루트 기준 Bronze 상대 경로",
        "parent VET_SEQ":"부모 진료 이력의 VET_SEQ 연결",
        "1-based comma token position":"진료명 항목의 1부터 시작하는 순번",
        "inherit parent trace":"부모 진료 이력의 출처 상속"
    }
    summary = []
    for row in audit.dictionary:
        entries = sorted(by_column.get((row["table"],row["standard_column"]),[]),key=lambda r:(-r["count"],r["raw_value"],r["standard_value"]))
        examples = []
        for entry in entries[:4]:
            raw = json.dumps(entry["raw_value"],ensure_ascii=False)
            new = "NULL" if entry.get("standard_is_null") else json.dumps(entry["standard_value"],ensure_ascii=False)
            examples.append(f"`{raw}` → `{new}` ({entry['count']:,})")
        action = f"{labels.get(row['operation'],row['operation'])}; {row['standard_type']}"
        if row["source_column"] != row["standard_column"]:
            action += "; 이름/파생 매핑"
        if examples:
            action += "<br>"+"<br>".join(examples)
        if len(entries)>4:
            action += f"<br>그 외 {len(entries)-4:,}개 값 변환은 전체 CSV 참조"
        summary.append([row["table"],f"`{row['source_column']}`",f"`{row['standard_column']}`",action,
                        f"{row['source_rows']:,}",f"{row['rename_rows']:,}",f"{row['type_changed_rows']:,}",f"{row['value_changed_rows']:,}",f"{row['null_rows']:,}"])
    changes = """# Silver 변경 내역과 건수

[Silver 기록](SILVER.md) · [Silver 컬럼](SILVER_COLUMNS.md) · [사용법](silver_usage.md)

## 집계 기준

| 항목 | 의미 |
| --- | --- |
| 대상 행 | 해당 출력 컬럼에 적용한 입력 행 수. 매출 본문/합계는 분리한 행만 집계 |
| 이름/파생 매핑 행 | 원천명과 표준명이 다르거나 여러 원천을 조합한 행 수 |
| 타입 변경 행 | NULL이 아닌 출력 중 Python 값 타입이 원천 타입과 달라진 행 수 |
| 값 변경 행 | 타입 표시를 제외한 원천/표준 표시값이 다르거나 NULL 여부가 달라진 행 수 |
| NULL 행 | 변환 후 해당 컬럼의 NULL 수. 누락 필드/원천 빈값/규칙상 NULL 포함 |
| 예시의 (N) | 정확히 그 원천값 → 표준값으로 바뀐 행 수. 따옴표 안 공백도 원천값의 일부 |

각 컬럼의 집계는 겹칠 수 있으므로 전체 행 수처럼 더하지 않습니다. 이름 변경만 있거나 문자열 `1`이 정수 1로 바뀌어 표시값이 같으면 값 변경은 0일 수 있습니다.
복합 원천은 배열 형태로 표시합니다. 예시는 빈도 상위 4개이고, **전체 원천값별 변환 건수**는 [silver_value_changes.csv](../meta/silver_value_changes.csv)에 모두 기록합니다.
변환 실패로 NULL이 된 행과 원천에 값이 있던 규칙상 NULL 행은 [silver_issue_log.csv](../meta/silver_issue_log.csv)에서 원천 행 번호와 값을 확인합니다.

## 테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 건수

""" + markdown_table(["테이블","원천컬럼","표준컬럼","바꾼내용·원천값 → 표준값 (건수)","대상 행","이름/파생 매핑 행","타입 변경 행","값 변경 행","NULL 행"],summary)
    # Small-domain code replacements are all shown, rather than only samples.
    code_ops = {"map","upper","region","grade","channel","branch","external","entry_status","margin_code","race_grade","burden_type"}
    code_columns = {(d["table"],d["standard_column"]) for d in audit.dictionary if d["operation"] in code_ops}
    code_rows = [[r["table"],r["source_column"],r["standard_column"],
                  f"`{json.dumps(r['raw_value'],ensure_ascii=False)}` → `{'NULL' if r.get('standard_is_null') else r['standard_value']}` ({r['count']:,})"]
                 for r in audit.changes if (r["table"],r["standard_column"]) in code_columns]
    changes += "\n\n## 코드·명칭 매핑의 전체 변경값별 건수\n\n"+markdown_table(["테이블","원천컬럼","표준컬럼","변경값 (건수)"],code_rows)+"\n"
    columns = "# Silver 컬럼 사전\n\n[작업 기록](SILVER.md) · [변경 건수](SILVER_CHANGES.md) · [사용법](silver_usage.md)\n\n실제 생성한 Parquet 스키마와 집계입니다. 타임스탬프는 Asia/Seoul(KST), 금액은 원, 거리 m, 무게 kg, 시간 길이는 초입니다.\n"
    for name,table in outputs.items():
        dictionary = {r["standard_column"]:r for r in audit.dictionary if r["table"]==name}
        rows = []
        for field in table.schema:
            rule = dictionary[field.name]
            vals = table[field.name].slice(0,3).to_pylist()
            example = "; ".join(display(v) for v in vals)
            rows.append([f"`{field.name}`",f"`{field.type}`",rule["source_column"],labels.get(rule["operation"],rule["operation"]),
                         f"{table[field.name].null_count:,}",rule["null_reasons"],f"`{example}`",rule["rule_id"]])
        columns += f"\n## {name}\n\n저장 파일명: `{name}.parquet`, **{table.num_rows:,}행**.\n\n"+markdown_table(["표준컬럼","실제 타입","원천컬럼/생성 근거","처리","NULL 수","NULL 이유별 건수","처음 3행 예시","규칙 ID"],rows)+"\n"
    totals = [[name,f"{table.num_rows:,}",table.num_columns] for name,table in outputs.items()]
    rec = [[r["table"],f"{r['rows']:,}",
            f"{outputs[r['table']].num_rows+(outputs['RC_SALES_TOTAL'].num_rows if r['split_sales'] else 0):,}",
            "본문+합계" if r["split_sales"] else "1:1", "일치"] for r in audit.sources]
    null_codes = Counter(issue["issue_code"] for issue in audit.issues)
    basis = "[mapping_rules.md](../meta/mapping_rules.md)의 이름·타입·코드·복합값·분리 규칙" if is_default else "사용자가 --spec으로 지정한 JSON 규칙; 기본 공용 규칙을 자동 혼합하지 않음"
    code_path = Path(__file__).resolve()
    code_link = document_path(code_path,docs_root)
    code_description = f"[02_normalize.py]({code_link})"
    checker = code_path.with_name("02_normalize_check.py")
    if checker.exists():
        checker_link = document_path(checker,docs_root)
        code_description += f", [02_normalize_check.py]({checker_link})"
    main = f"""# Silver 단계 기록 (표준화)

[변경 내역·건수](SILVER_CHANGES.md) · [컬럼 사전](SILVER_COLUMNS.md) · [사용법](silver_usage.md) · [데이터 안내](DATA_GUIDE.md)

## 처리 결과

| 항목 | 결과 |
| --- | --- |
| 상태 | {'검증 실패: 아래 확인' if errors else '표준화·검증 완료'} |
| 코드 | {code_description} |
| 입력 | `{input_root}`; Bronze만 읽으며 origin은 읽지 않음 |
| 출력 | `{output_root}` 바로 아래 Parquet {len(outputs)}개; 하위 폴더 없음 |
| 근거 | {basis} |
| 파일 개수 | {len(audit.sources)}개 원천에서 {len(outputs)}개 표준 테이블 생성; 기본 공용 규칙은 사용자 확인에 따라 14개 파일 |
| 행 삭제 | 없음. 중복·전표/마권 불일치는 후속 품질 관리 대상으로 보존 |
| 추적 | SOURCE_FILE, INGESTED_AT(KST), _SRC_ROW_NO(1부터), _SRC_BRONZE_FILE(Bronze 상대 경로) |
| 검증 | {len(checks)}개 중 {len(checks)-len(errors)}개 통과; PARSE_FAIL {sum(r['parse_fail_rows'] for r in audit.dictionary):,}건, OUT_OF_CODE {sum(r['out_of_code_rows'] for r in audit.dictionary):,}건 |
| 규칙서 고정 기대값 비교 | {'수행' if reference else '미수행; 일반 입력 데이터에는 고정 건수를 강제하지 않음'} |

## 출력 테이블

{markdown_table(['테이블 / 파일명 (.parquet)','행 수','컬럼 수'],totals)}

## 입력 행 보존 대사

{markdown_table(['Bronze 대응 테이블','Bronze 행 수','Silver 대응 행 수','대사 방식','결과'],rec)}

HR_VET_TYPE_BRIDGE는 원천 진료명에서 분리한 항목 수와 대사하며 부모 VET_SEQ와 항목 순서를 검증합니다.
원천 테이블의 보존 대사와 별개로 브리지 행이 추가되므로, 14개 파일의 전체 행 합을 원천 행 수와 직접 비교하지 않습니다.

## 기본 공용 규칙의 표준화 내용

다른 --spec을 지정하면 아래 기본 도메인 규칙을 자동 적용하지 않습니다. 실제 적용 내용은 해당 실행의 컬럼 사전·변경 내역을 확인합니다.

| 구분 | 적용 내용 |
| --- | --- |
| 이름 | 공용 UPPER_SNAKE 매핑. 전표 ticket_cnt → TICKET_CNT, 마권 ticket_cnt → UNIT_CNT |
| 날짜/일시 | 혼합 날짜를 date32, 일시를 timestamp[ms, Asia/Seoul], 시각을 time32[ms]로 변환 |
| 숫자 | 건수 int32, 지정 금액 int64, 소수 decimal128. 정밀도 초과 시 반올림하지 않고 실패 |
| 문자열/빈값 | TRIM, 빈 문자열·공백·----- → NULL. 착차 빈칸 FIRST, 채널 빈칸 UNKNOWN은 규칙 예외 |
| 코드 | 승식·상태·채널·지역·성별·등급·날씨·주로 등을 코드화; 코드표 밖 값은 로그와 실패 검증 |
| 복합값 | 체중/증감, 분:초, 분수 착차, 구간 위치, 순위상금, 경주 조건, 도입가격 분리 |
| 매출 | POOL_NM=합계 행을 RC_SALES_TOTAL로 분리; 실제 분리 행 수는 출력·대사 표 참조 |
| 진료명 | VET_NM 원문 유지, VET_SEQ로 개별 진료명 브리지 연결 |
| JSON | 이벤트 중첩 필드를 평탄화; 이벤트별 없는 필드는 NULL 유지 |
| 제외 컬럼 | 규칙서 9장 컬럼은 Silver에서 제외. Bronze와 데이터 사전에 원천·사유 보존 |

상세 내용과 **테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 건수**는 [SILVER_CHANGES.md](SILVER_CHANGES.md)에 기록했습니다.
이 문서는 실행 코드가 실제 집계에서 생성합니다. 다른 데이터를 실행하면 건수도 해당 입력 기준으로 다시 계산됩니다.

## 기록 파일

| 파일 | 내용 |
| --- | --- |
| [data_dictionary.csv](../meta/data_dictionary.csv) | 원천·표준 컬럼/타입·적용 규칙·건수·제외 사유 |
| [silver_value_changes.csv](../meta/silver_value_changes.csv) | 원천값 → 표준값별 전체 변경 건수 |
| [silver_issue_log.csv](../meta/silver_issue_log.csv) | 원천 행 번호·Bronze 파일·NULL/실패 원천값·사유·규칙 ID |
| [silver_column_profile.csv](../meta/silver_column_profile.csv) | 컬럼별 NULL·TRIM·타입·값 변경·실패 집계 |
| [silver_validation.json](../meta/silver_validation.json) | 입력/출력 해시·규칙·검증 결과 |
| [normalization_decisions.csv](../meta/normalization_decisions.csv) | 규칙서 밖 원문 표현의 해석 근거 |

이슈 로그는 컬럼 단위 기록이므로 한 입력 행에 여러 로그가 있을 수 있습니다. 이슈 코드별 기록 수: `{json.dumps(dict(sorted(null_codes.items())),ensure_ascii=False)}`.
원천값이 있던 규칙상 NULL은 실패와 구분해 RULE_NULL로 보존합니다. 원천 자체의 빈 문자열과 선택 필드 누락은 컬럼 프로파일에 집계합니다.

## 추가 해석과 확인할 점

| 결정 ID | 관측 원문·조건 | 적용 해석·보존 |
| --- | --- | --- |
| D-NORM-001 | 미출전(ORD_RAW=94/95)이고 PASS_ORD_RAW의 구분자 사이에 숫자가 전혀 없는 '-  -  -  -' | 6개 통과 위치 모두 기록 없음(NULL); 원천과 NULL 사유 보존. 팀 공용 규칙서에 이 표현을 명시할지 검토 필요 |
| TYPE-01 | 규칙서의 DECIMAL 컬럼에 정밀도 미지정 | 기록/구간/함수율 (5,1), 착차 (5,2), JSON 부담중량 (4,1)로 명시. 값이 정확히 표현되지 않으면 실패 |

품질 정제·중복 제거·Gold는 수행하지 않았습니다. 다음 단계에서 행을 제외하면 근거 결정 ID와 별도 제외 데이터를 남겨야 합니다.

## 검증 결과

{markdown_table(['검증 항목','기대','실제','결과'],[[r['check'],r['expected'],r['actual'],'통과' if r['passed'] else '실패'] for r in checks])}

## 변경 이력

| 일자 (KST) | 작업 | 결과 |
| --- | --- | --- |
| 2026-11-20 | Bronze 입력 기반 표준화·분리·추적·변환 건수 집계 구현 | Silver 평면 저장, docs·meta 실제 수치 기록 |
"""
    documents = {"SILVER.md":main,"SILVER_COLUMNS.md":columns,"SILVER_CHANGES.md":changes,
                 "silver_usage.md":usage_document(code_link,checker.exists())}
    meta_link = document_path(meta_root,docs_root)
    for filename,text in documents.items():
        text = text.replace("](../meta/",f"]({meta_link}/")
        if not (docs_root/"DATA_GUIDE.md").exists():
            text = text.replace(" · [데이터 안내](DATA_GUIDE.md)","")
        documents[filename] = text
    return documents


def save_csv(path,rows,headers):
    pd.DataFrame(rows,columns=headers).to_csv(path,index=False,encoding="utf-8-sig",lineterminator="\n")


def write_if_different(staged,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists() and digest(staged)==digest(destination):
        return "unchanged"
    staged.replace(destination)
    return "written"


def run(input_root=ROOT/"data/01_bronze", output_root=ROOT/"data/02_silver",
        meta_root=ROOT/"meta", docs_root=ROOT/"docs", specs=None, reference=False):
    input_root,output_root,meta_root,docs_root = [Path(p).resolve() for p in (input_root,output_root,meta_root,docs_root)]
    is_default = specs is None
    specs = default_specs() if specs is None else specs
    if not specs:
        raise ValueError("변환 규칙이 비어 있습니다.")
    jobs = preflight(input_root,output_root,meta_root,docs_root,specs)
    audit = Audit()
    outputs = {}
    for name,spec,source in jobs:
        before = digest(source)
        original = pq.read_table(source)
        relative = source.relative_to(input_root).as_posix()
        audit.sources.append(dict(table=name,path=str(source),relative=relative,rows=original.num_rows,
                                  sha256=before,split_sales=bool(spec.get("split_sales")),bridge=bool(spec.get("bridge"))))
        outputs.update(build_table(name,spec,original,relative,audit))
        print(f"normalized {name}: {original.num_rows:,} source rows",flush=True)
    checks = check_outputs(outputs,audit.sources,audit,reference=reference)
    # Stage all files before publishing any result. Validation failures publish diagnostics only.
    meta_root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".silver-stage-",dir=meta_root.parent) as temporary:
        stage = Path(temporary)
        report = dict(input_root=str(input_root),output_root=str(output_root),
                      code_sha256=digest(__file__),specs_sha256=hashlib.sha256(json.dumps(specs,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                      reference_checked=reference,sources=audit.sources,outputs={},checks=checks,
                      status="passed" if all(c["passed"] for c in checks) else "failed")
        for name,table in outputs.items():
            path = stage/(name+".parquet")
            pq.write_table(table,path,compression="snappy")
            if not pq.read_table(path).equals(table):
                raise RuntimeError(f"Parquet roundtrip failed: {name}")
            report["outputs"][name] = dict(rows=table.num_rows,columns=table.column_names,sha256=digest(path))
        for source in audit.sources:
            if digest(source["path"]) != source["sha256"]:
                raise RuntimeError(f"Bronze changed while processing: {source['path']}")
        meta_root.mkdir(parents=True,exist_ok=True)
        dict_headers = ["table","source_column","standard_column","operation","standard_type","source_rows","rename_rows","type_changed_rows","value_changed_rows","trim_rows","null_rows","parse_fail_rows","out_of_code_rows","null_reasons","rule_id","rule"]
        save_csv(stage/"data_dictionary.csv",audit.dictionary,dict_headers)
        save_csv(stage/"silver_column_profile.csv",audit.dictionary,[h for h in dict_headers if h!="rule"])
        save_csv(stage/"silver_value_changes.csv",audit.changes,["table","source_column","standard_column","raw_value","standard_value","count","standard_is_null","rule_id"])
        save_csv(stage/"silver_issue_log.csv",audit.issues,["table","source_column","standard_column","source_row_no","bronze_file","raw_value","issue_code","reason","rule_id"])
        decision_rows = [dict(decision_id="D-NORM-001",scope="RC_RESULT.PASS_ORD_RAW",condition="ORD_RAW in 94/95; all dash-separated tokens empty",decision="all six pass positions NULL; no source row removed",source_rows=len({(i["bronze_file"],i["source_row_no"]) for i in audit.issues if i["reason"]=="D-NORM-001_NO_RUN_RECORD"}),status="implementation interpretation; team rule wording review pending")]
        save_csv(stage/"normalization_decisions.csv",decision_rows,["decision_id","scope","condition","decision","source_rows","status"])
        (stage/"silver_validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if report["status"]=="failed":
            for name in ("silver_issue_log.csv","silver_column_profile.csv","silver_validation.json"):
                write_if_different(stage/name,meta_root/name)
            failed = [c for c in checks if not c["passed"]]
            raise RuntimeError("검증 실패; Silver는 저장하지 않음: "+json.dumps(failed,ensure_ascii=False))
        documents = report_documents(audit,outputs,checks,input_root,output_root,reference,meta_root,docs_root,is_default)
        for name,table in outputs.items():
            status = write_if_different(stage/(name+".parquet"),output_root/(name+".parquet"))
            print(f"{status}: {name}.parquet ({table.num_rows:,})",flush=True)
        for path in sorted(stage.glob("*.csv")):
            write_if_different(path,meta_root/path.name)
        write_if_different(stage/"silver_validation.json",meta_root/"silver_validation.json")
        docs_root.mkdir(parents=True,exist_ok=True)
        for name,text in documents.items():
            path = stage/name
            path.write_text(text.rstrip()+"\n",encoding="utf-8")
            write_if_different(path,docs_root/name)
    return report


def usage_document(code_link,has_checker):
    text = r"""# Silver 표준화 사용법

[작업 기록](SILVER.md) · [변경 내역·건수](SILVER_CHANGES.md) · [컬럼 사전](SILVER_COLUMNS.md)

## 1. 준비와 입력

| 항목 | 설정 |
| --- | --- |
| 실행 파일 | [02_normalize.py](CODE_LINK) |
| 입력 | Bronze Parquet만 사용. origin CSV/JSONL을 다시 읽지 않음 |
| 기본 입력 경로 | 프로젝트 루트/data/01_bronze; 하위 폴더까지 검색 |
| 기본 출력 경로 | 프로젝트 루트/data/02_silver; 모든 파일을 바로 아래 저장 |
| 기본 규칙 | mapping_rules.md의 공용 규칙을 코드로 정의한 default_specs() |
| config.py 관계 | Bronze용 설정과 별개. Silver 경로는 아래 실행 인자로 지정 |
| 의존 패키지 | Python 3.12 이상, pandas, pyarrow |

프로젝트 루트에서 전용 가상환경을 사용합니다. 패키지가 없다면 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install pandas pyarrow
```

## 2. 현재 프로젝트 실행

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --check-reference
```

`--check-reference`는 공용 규칙서 11장의 이 데이터셋 고정 행 수·NULL 수를 추가 검증합니다.
다른 시기·다른 크기의 입력에서는 이 옵션을 생략하고 입력 대비 보존·변환·추적 검증을 사용합니다.

| 처리 | 내용 |
| --- | --- |
| 입력 확인 | 규칙별 입력 파일명(stem)이 하나씩 있는지 확인. 경로 중첩·미매핑 컬럼·파일 충돌 차단 |
| 표준화 | 이름·타입·값·단위·날짜 형식 변환. 행 정렬/삭제/중복 제거 없음 |
| 출처 | SOURCE_FILE·INGESTED_AT을 유지/타입 변환, 원천 행 번호와 Bronze 상대 경로 추가 |
| 테이블 분리 | RC_SALES 합계 분리, 진료명 브리지 생성: 기본 규칙은 14개 파일 |
| 대사 | 각 입력 행이 대응 테이블에 정확히 한 번 존재하는지 확인. 브리지는 항목 수·순서·부모 연결 확인 |
| 임시 저장 검증 | Parquet 왕복 값·스키마 비교 후 저장. 검증 실패 시 Silver를 저장하지 않고 진단 기록 남김 |
| 보고서 | meta의 데이터 사전·전체 변경값별 건수·NULL 사유와 docs의 실제 결과 표 생성 |

## 3. 다른 프로젝트에서 같은 규칙 사용

02_normalize.py는 config.py 등 다른 프로젝트 소스 파일을 import하지 않습니다.
이 파일을 다른 프로젝트로 복사하고 pandas/pyarrow를 설치한 뒤, 입력·출력·메타·문서 경로를 지정할 수 있습니다.
기본 규칙을 그대로 쓰려면 같은 원천 컬럼과 파일명이 필요합니다. 경마와 무관한 데이터까지 동일한 코드표로 추정 변환하지 않습니다.

```powershell
python 02_normalize.py --input-root "D:/other/data/01_bronze" --output-root "D:/other/data/02_silver" --meta-root "D:/other/meta" --docs-root "D:/other/docs"
```

| 인자 | 의미 |
| --- | --- |
| --input-root | Bronze 루트; .parquet 재귀 검색 |
| --output-root | 평면 Silver 저장 폴더 |
| --meta-root | 데이터 사전·변환 건수·이슈·검증 이력 경로 |
| --docs-root | 자동 생성되는 단계·컬럼·변경·사용법 문서 경로 |
| --spec | 다른 원천 구조에 사용할 JSON 규칙 파일 |
| --check-reference | 현재 공용 데이터셋의 고정 기대값 검증 |
| --dump-default-spec | 기본 규칙을 JSON으로 내보내고 종료 |

4개 경로는 서로 겹치지 않게 지정합니다. 입력 파일명은 하위 폴더가 달라도 규칙별로 유일해야 합니다.
규칙에 없는 입력 파일이나 출력 폴더에 남은 다른 테이블이 있으면 자동 삭제하지 않고 중단하므로 별도 경로를 사용합니다.

## 4. 다른 컬럼·코드표는 JSON으로 지정

기본 규칙을 파일로 꺼내 수정하려면 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --dump-default-spec meta/normalize_rules.json
```

새 구조라면 아래처럼 별도 규칙을 작성합니다. 이 예시는 person.parquet의 gender 컬럼이 실제로 `2`/`1`을 뜻한다고 정의한 경우에만 사용합니다.

```json
{
  "tables": {
    "PERSON": {
      "input": "person",
      "columns": [
        {"source": "gender", "target": "SEX_CD", "type": "string", "op": "map", "mapping": {"2": "F", "1": "M"}}
      ],
      "drop": []
    }
  }
}
```

| 규칙 필드 | 의미 |
| --- | --- |
| tables의 키 | 출력 테이블명·파일명. UPPER_SNAKE |
| input | 입력 Parquet 파일명에서 확장자를 제외한 이름 |
| columns[].source | 원천 컬럼명. JSON struct 하위는 race.rcDate처럼 점으로 표현 |
| columns[].target | 표준 컬럼명. UPPER_SNAKE |
| columns[].type | string, int32, int64, date32, timestamp, time, decimal(p,s) |
| columns[].op | text(TRIM·빈값), upper, map 등 변환. 날짜/숫자 타입은 text에서도 type에 맞게 변환 |
| mapping | map 연산의 명시적 원천값 → 표준값 사전 |
| allowed | NULL을 제외한 허용 출력 코드 목록; 필요 시 지정 |
| drop | Silver에서 의도적으로 제외할 원천 컬럼명. 제외 사유가 데이터 사전에 기록됨 |

원천 컬럼을 columns 또는 drop에 모두 명시해야 합니다. Bronze의 source_file과 ingested_at은 있으면 자동 추적 매핑하므로 생략할 수 있습니다.

```powershell
python 02_normalize.py --input-root "D:/other/data/01_bronze" --output-root "D:/other/data/02_silver" --meta-root "D:/other/meta" --docs-root "D:/other/docs" --spec "D:/other/meta/person_rules.json"
```

기본 경마 코드표에는 숫자 `2` → F 규칙이 없습니다. 위 JSON처럼 명시한 규칙에서만 변환하며, `2`가 5행이면 보고서에 `2 → F (5)`로 집계합니다.

## 5. 보고서 확인과 재실행

| 확인 대상 | 볼 내용 |
| --- | --- |
| SILVER.md | 테이블별 행 수·보존 대사·검증 결과 |
| SILVER_CHANGES.md | 테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 대상·이름·타입·값 변경 건수 |
| SILVER_COLUMNS.md | 실제 컬럼·Arrow 타입·NULL 이유·처음 3행 예시 |
| meta/silver_value_changes.csv | 전체 원천값 → 표준값별 변경 건수. 값이 많은 항목도 생략 없이 기록 |
| meta/silver_issue_log.csv | 값이 있던 원천이 NULL로 바뀐 사유, 실패·코드표 밖 값, 원천 행 번호 |
| meta/silver_validation.json | 입력/출력 SHA-256과 검증 결과 |

같은 입력·규칙·코드·옵션으로 재실행하면 Parquet과 집계 결과가 같습니다. 동일 파일은 덮어쓰지 않습니다.
실행 시각은 Silver 본문에 추가하지 않으며 Bronze에서 받은 최초 수집 시각을 사용합니다.

검증 도구가 함께 있다면 저장된 결과를 읽기만 하여 다시 검사합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize_check.py --check-reference
```

독립 실행에 필요한 파일은 02_normalize.py 하나이며, 02_normalize_check.py는 선택적인 재검증 도구입니다.
코드·규칙·입력이 바뀌면 표준화를 먼저 재실행해야 현재 결과의 해시와 맞습니다.

## 범위와 오류 처리

| 사항 | 동작 |
| --- | --- |
| 중복·전표/마권 불일치·이상값 | 이번에는 정제하지 않음. 입력 행 유지 |
| 빈값·규칙상 NULL | 공용 표준화 규칙에 따른 변환. 원천은 Bronze에 남기고 NULL 이유 기록 |
| 날짜·숫자 변환 실패 / 코드표 밖 | PARSE_FAIL / OUT_OF_CODE 진단 기록, 검증 실패로 Silver 저장 중단. 행을 골라 제외하지 않음 |
| 규칙서에 없는 원문 해석 | 별도 결정 ID와 적용 조건 기록. 통과기록 없음 해석은 SILVER.md 참조 |
| PermissionError | 결과 파일의 읽기 핸들을 닫고 재실행 |
| 메모리 | 파일 전체와 변환 로그를 메모리에서 처리하므로 대용량은 메모리 필요 |

현재 단계는 **표준화**입니다. 품질 관리와 행 제외는 별도 단계에서 근거 결정 ID·유지/제외 데이터·건수 대사와 함께 수행합니다.
"""
    return text.replace("CODE_LINK",code_link).strip()+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root",type=Path,default=ROOT/"data/01_bronze")
    parser.add_argument("--output-root",type=Path,default=ROOT/"data/02_silver")
    parser.add_argument("--meta-root",type=Path,default=ROOT/"meta")
    parser.add_argument("--docs-root",type=Path,default=ROOT/"docs")
    parser.add_argument("--spec",type=Path,help="JSON: {tables: {TABLE: {input, columns, drop}}}")
    parser.add_argument("--check-reference",action="store_true",help="Check the fixed counts in mapping_rules.md section 11")
    parser.add_argument("--dump-default-spec",type=Path,help="Export reusable default JSON spec and exit")
    args = parser.parse_args()
    if args.dump_default_spec:
        args.dump_default_spec.parent.mkdir(parents=True,exist_ok=True)
        args.dump_default_spec.write_text(json.dumps({"tables":default_specs()},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return
    specs = json.loads(args.spec.read_text(encoding="utf-8-sig"))["tables"] if args.spec else None
    report = run(args.input_root,args.output_root,args.meta_root,args.docs_root,specs=specs,reference=args.check_reference)
    print(f"Validated {len(report['checks'])} checks; {len(report['outputs'])} Silver tables.")


if __name__ == "__main__":
    main()
