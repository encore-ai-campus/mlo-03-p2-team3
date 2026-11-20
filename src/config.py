"""파이프라인 공통 설정 (경로, 원천 목록, 기대값).

원천 파일이 바뀌거나 늘어나면 SOURCES만 고치면 된다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN_DIR = ROOT / "data" / "00_origin"
BRONZE_DIR = ROOT / "data" / "01_bronze"
SILVER_DIR = ROOT / "data" / "02_silver"
META_DIR = ROOT / "meta"

BRONZE_LOAD_LOG = META_DIR / "bronze_load_log.csv"
SILVER_ISSUE_LOG = META_DIR / "silver_issue_log.csv"
SILVER_VALUE_MAP = META_DIR / "silver_value_map.csv"
SILVER_COLUMN_PROFILE = META_DIR / "silver_column_profile.csv"
DATA_DICTIONARY = META_DIR / "data_dictionary.csv"

TIMEZONE = "Asia/Seoul"
CSV_ENCODING = "utf-8-sig"

# 원천 목록: (원천 파일 경로[00_origin 기준], 원천 시스템, 형식, Bronze 파일 이름)
# 원천 시스템은 매핑_규칙서 3장의 원천 접두어(bet/mbr/hms/rms/vms/mongodb)를 따른다.
SOURCES = [
    {"file": "order/bet_order.csv", "system": "bet", "format": "csv", "bronze": "bet_order"},
    {"file": "order/bet_ticket.csv", "system": "bet", "format": "csv", "bronze": "bet_ticket"},
    {"file": "member/MBR_MASTER.csv", "system": "mbr", "format": "csv", "bronze": "MBR_MASTER"},
    {"file": "horse/HR_WEEKLY_SNAPSHOT.csv", "system": "hms", "format": "csv", "bronze": "HR_WEEKLY_SNAPSHOT"},
    {"file": "horse/TR_WEEKLY_SNAPSHOT.csv", "system": "hms", "format": "csv", "bronze": "TR_WEEKLY_SNAPSHOT"},
    {"file": "race/RC_RACE.csv", "system": "rms", "format": "csv", "bronze": "RC_RACE"},
    {"file": "race/RC_ENTRY.csv", "system": "rms", "format": "csv", "bronze": "RC_ENTRY"},
    {"file": "race/RC_ODDS.csv", "system": "rms", "format": "csv", "bronze": "RC_ODDS"},
    {"file": "race/RC_RESULT.csv", "system": "rms", "format": "csv", "bronze": "RC_RESULT"},
    {"file": "race/RC_SALES.csv", "system": "rms", "format": "csv", "bronze": "RC_SALES"},
    {"file": "horse/HR_VET_HIST.csv", "system": "vms", "format": "csv", "bronze": "HR_VET_HIST"},
    {"file": "event/race_change_events.jsonl", "system": "mongodb", "format": "jsonl", "bronze": "race_change_events"},
]

# 매핑_규칙서 11장: 규칙대로 적용했을 때 나와야 하는 값
EXPECTED_SILVER_ROWS = {
    "BET_ORDER": 27907,
    "BET_TICKET": 523416,
    "MBR_MASTER": 4383,
    "HR_WEEKLY_SNAPSHOT": 52642,
    "TR_WEEKLY_SNAPSHOT": 954,
    "RC_RACE": 386,
    "RC_ENTRY": 3666,
    "RC_ODDS": 3666,
    "RC_RESULT": 3666,
    "RC_SALES": 2702,
    "RC_SALES_TOTAL": 386,
    "HR_VET_HIST": 1488,
    "HR_VET_TYPE_BRIDGE": 1664,
    "RC_CHANGE_EVENT": 149,
}

# (테이블, 컬럼) → 기대 NULL 건수
EXPECTED_NULLS = {
    ("MBR_MASTER", "BIRTH_DT"): 27,
    ("RC_ODDS", "WIN_ODDS"): 22,
    ("RC_RACE", "TRACK_MOIST_RT"): 21,
    ("RC_RESULT", "FINISH_ORD"): 22,
}

# (테이블, 컬럼, 값) → 기대 건수
EXPECTED_VALUE_COUNTS = {
    ("HR_WEEKLY_SNAPSHOT", "TR_EXTERNAL_YN", "Y"): 25428,
}

EXPECTED_VET_MULTI_NAME_ROWS = 176
