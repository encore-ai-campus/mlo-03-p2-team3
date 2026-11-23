"""Gold 이름 검증: data/03_gold의 모든 테이블·컬럼이 매핑 규칙서 13장(Gold 이름 규칙)을 지키는지 확인한다.

1. 테이블: FCT_ / DIM_ / BRIDGE_
2. 대리키·FK: *_KEY. 날짜 역할 키는 DATE_KEY 또는 *_DT_KEY (*_DATE_KEY 금지)
3. 나머지 컬럼: 매핑 규칙서 2장 접미사로 끝남 (나이·추적 컬럼은 예외 목록)
4. 축약하지 않은 단어 금지: HORSE_, MEMBER_, CHANNEL_, TRAINER_, RACE_, AMOUNT, COUNT, SECONDS, RATE, DATE, ORIGINAL
5. *_YN 컬럼 값은 Y / N / NULL만
"""
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

SUFFIXES = ("_NO", "_SEQ", "_DT", "_DTM", "_TM", "_NM", "_CD", "_AMT", "_CNT", "_KG", "_SEC", "_RT",
            "_ODDS", "_YN", "_VAL", "_M", "_ID", "_KEY")
AGE_COLS = {"HR_AGE", "TR_AGE", "MBR_AGE", "MIN_AGE", "MAX_AGE"}  # 규칙서 8장: 나이는 접미사 없음
FULL_WORD = re.compile(r"(^|_)(HORSE|MEMBER|CHANNEL|TRAINER|RACE|AMOUNT|COUNT|SECONDS|RATE|DATE|ORIGINAL)(_|$)")
FAILS = []


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
    print(f"Gold 테이블 {len(paths)}개, 컬럼 {n_cols}개 검사")
    for f in FAILS:
        print("  X", f)
    print("Gold 이름 검증:", "통과" if not FAILS else f"위반 {len(FAILS)}건")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
