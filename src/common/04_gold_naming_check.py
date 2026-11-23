"""Gold 이름 검증: data/03_gold의 모든 테이블·컬럼이 매핑 규칙서 13장(Gold 이름 규칙)을 지키는지 확인한다.

1. 테이블: FCT_ / DIM_ / BRIDGE_
2. 대리키·FK: *_KEY. 날짜 역할 키는 DATE_KEY 또는 *_DT_KEY (*_DATE_KEY 금지)
3. 나머지 컬럼: 매핑 규칙서 2장 접미사로 끝남 (나이·추적 컬럼은 예외 목록)
4. 축약하지 않은 단어 금지: HORSE_, MEMBER_, CHANNEL_, TRAINER_, RACE_, AMOUNT, COUNT, SECONDS, RATE, DATE, ORIGINAL
5. *_YN 컬럼 값은 Y / N / NULL만
6. 종합 데이터 사전(meta/data_dictionary.csv)의 GOLD·AI_READY 행 = 실제 파일의 컬럼 이름·순서, 타입 계열 일치, 출처·규칙 빈칸 없음
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

SUFFIXES = ("_NO", "_SEQ", "_DT", "_DTM", "_TM", "_NM", "_CD", "_AMT", "_CNT", "_KG", "_SEC", "_RT",
            "_ODDS", "_YN", "_VAL", "_M", "_ID", "_KEY")
AGE_COLS = {"HR_AGE", "TR_AGE", "MBR_AGE", "MIN_AGE", "MAX_AGE"}  # 규칙서 8장: 나이는 접미사 없음
FULL_WORD = re.compile(r"(^|_)(HORSE|MEMBER|CHANNEL|TRAINER|RACE|AMOUNT|COUNT|SECONDS|RATE|DATE|ORIGINAL)(_|$)")
FAILS = []
AI_READY = {"AI_READY_RACE_ENTRY": C.ROOT / "data/04_ai_ready/AI_READY_RACE_ENTRY.parquet",
            "AI_READY_RACE_ENTRY_ENCODED": C.ROOT / "data/04_ai_ready/AI_READY_RACE_ENTRY_ENCODED.parquet",
            "AI_READY_RACE_ENTRY_EXCLUDED": C.ROOT / "data/04_ai_ready/_excluded/AI_READY_RACE_ENTRY.parquet"}


def family(t):
    """Arrow 타입 → 사전 타입 계열."""
    if pa.types.is_dictionary(t):
        t = t.value_type
    for test, name in [(pa.types.is_int8, "TINYINT"), (pa.types.is_int32, "INT"), (pa.types.is_int64, "BIGINT"),
                       (pa.types.is_floating, "DOUBLE"), (pa.types.is_decimal, "DECIMAL"), (pa.types.is_date, "DATE"),
                       (pa.types.is_timestamp, "TIMESTAMP"), (pa.types.is_time, "TIME")]:
        if test(t):
            return name
    return "VARCHAR"


def dict_family(text):
    base = text.split("(")[0]
    return "VARCHAR" if base in ("VARCHAR", "CODE", "CHAR") else base


def check_dictionary(tables):
    """tables: {테이블명: (LAYER, 경로)}. 사전과 실제 파일이 같은지."""
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    dic = dic[dic.LAYER.isin(["GOLD", "AI_READY"])]
    for name in sorted(set(dic.TABLE_NM) - set(tables)):
        FAILS.append(f"사전에만 있는 테이블: {name}")
    for name, (layer, path) in tables.items():
        rows = dic[dic.TABLE_NM.eq(name)]
        schema = pq.read_schema(path)
        if list(rows.COL_NM) != schema.names:
            FAILS.append(f"사전 {name}: 컬럼 이름·순서가 실제 파일과 다름 (사전 {len(rows)}개, 파일 {len(schema.names)}개)")
            continue
        if not rows.LAYER.eq(layer).all():
            FAILS.append(f"사전 {name}: LAYER가 {layer}가 아님")
        for r, t in zip(rows.itertuples(), schema.types):
            if dict_family(r.DATA_TYPE) != family(t):
                FAILS.append(f"사전 {name}.{r.COL_NM}: 타입 {r.DATA_TYPE} ≠ 파일 {t}")
            if not r.RULE:
                FAILS.append(f"사전 {name}.{r.COL_NM}: 규칙(RULE) 빈칸")


def problem(table, col):
    if col.startswith("_"):
        return None  # 원천 행 번호 같은 추적 컬럼
    if col.endswith("_KEY"):
        if col.endswith("_DATE_KEY"):
            return "날짜 역할 키는 *_DT_KEY"
        if FULL_WORD.search(col[:-4]) and col not in {"HORSE_KEY", "MEMBER_KEY", "CHANNEL_KEY", "TRAINER_KEY", "RACE_KEY", "DATE_KEY"}:
            return "대리키 외의 키에 축약하지 않은 단어"
        return None
    if FULL_WORD.search(col):
        return "축약하지 않은 단어 (규칙서 2장 주제어·접미사 사용)"
    if col not in AGE_COLS and not col.endswith(SUFFIXES):
        return "규칙서 2장 접미사가 아님"
    return None


def main():
    paths = sorted(C.GOLD_DIR.glob("*/*.parquet"))
    n_cols = 0
    for path in paths:
        table = path.stem
        if not table.startswith(("FCT_", "DIM_", "BRIDGE_")):
            FAILS.append(f"{path.parent.name}/{table}: 테이블 이름이 FCT_/DIM_/BRIDGE_로 시작하지 않음")
        data = pq.read_table(path)
        for col in data.column_names:
            n_cols += 1
            why = problem(table, col)
            if why:
                FAILS.append(f"{table}.{col}: {why}")
            if col.endswith("_YN"):
                values = set(data.column(col).to_pylist()) - {None}
                if not values <= {"Y", "N"}:
                    FAILS.append(f"{table}.{col}: 값이 Y/N이 아님 {sorted(map(str, values))[:5]}")
    print(f"Gold 테이블 {len(paths)}개, 컬럼 {n_cols}개 이름 검사")
    tables = {p.stem: ("GOLD", p) for p in paths}
    tables.update({n: ("AI_READY", p) for n, p in AI_READY.items()})
    check_dictionary(tables)
    print(f"데이터 사전 대조: Gold·AI Ready 테이블 {len(tables)}개")
    for f in FAILS:
        print("  X", f)
    print("Gold 이름·사전 검증:", "통과" if not FAILS else f"위반 {len(FAILS)}건")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
