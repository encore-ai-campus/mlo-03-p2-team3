"""Silver 품질 관리 결과(02_silver/clean/) → Gold 공통 차원(03_gold/common/)

네 팩트(race_entry, horse_medical, race_sales, bet_cancel)가 함께 쓰는 차원 6개를 만든다.
팀 합의 (2026-11-23)
- 대리키: 업무 키로 정렬한 순번(1부터). 같은 clean이면 항상 같은 키. 원천이 바뀌면 공통 차원과 팩트를 함께 다시 만든다
- 미상 행: 모든 차원에서 키 0, 이름 UNKNOWN, 나머지 컬럼 NULL
- 날짜 키: YYYYMMDD 정수. 범위는 팩트가 참조하는 clean 날짜의 최소~최대(연속)
- 컬럼 이름: 대문자. 시각: 시간대 없는 KST
- 차원 범위: 팩트에 나온 값만이 아니라 clean 전체
- DIM_HORSE: SCD2. 스냅샷 다음 날부터 유효, 연결 조건은 VALID_FROM_DT <= 기준일 <= VALID_TO_DT
- DIM_MEMBER: 회원 + NON_MEMBER(회원번호 빈칸 = 실제 비회원, 별도 양수 키) + UNKNOWN(0)

입력은 D-012에 따라 clean/만 쓴다.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

COMMON_DIR = C.GOLD_DIR / "common"

UNKNOWN_KEY = 0
END_DT = date(9999, 12, 31)
DOW_NM = ["월", "화", "수", "목", "금", "토", "일"]
# SCD2 버전을 나누는 속성 (바뀌면 새 버전). 레이팅·통산 성적은 매주 바뀌어 차원에 넣지 않는다
SCD2_COLS = ["HR_SEX_CD", "HR_GRADE_CD", "HR_AGE", "TR_GRP_NO", "TR_NM", "TR_EXTERNAL_YN", "OW_NM"]
CHNL_NM = {"APP": "온라인", "ONSITE": "현장", "OTB": "장외발매소"}


def read_clean(t):
    return pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet")


def none_if_na(values):
    return [None if (x is None or (not isinstance(x, str) and pd.isna(x))) else x for x in values]


def with_unknown(schema, rows, key, extra=None):
    """키 0 미상 행을 맨 앞에 붙인다. 나머지 컬럼은 NULL (extra로 일부만 채움)."""
    unknown = {c: None for c in schema.names}
    unknown[key] = UNKNOWN_KEY
    unknown.update(extra or {})
    cols = {c: [unknown[c]] + none_if_na(rows[c].tolist()) for c in schema.names}
    return pa.table(cols, schema=schema)


def dim_date(clean):
    days_used = pd.concat([
        clean["RC_RACE"]["RC_DT"],
        clean["HR_VET_HIST"]["VET_DT"], clean["HR_VET_HIST"]["REPORT_DT"],
        clean["HR_WEEKLY_SNAPSHOT"]["SNAPSHOT_DT"],
        clean["BET_ORDER"]["SALE_DTM"].dt.date,
    ]).dropna()
    lo, hi = days_used.min(), days_used.max()
    days = [lo + timedelta(days=i) for i in range((hi - lo).days + 1)]
    race_days = set(clean["RC_RACE"]["RC_DT"])
    rows = pd.DataFrame({
        "DATE_KEY": [int(d.strftime("%Y%m%d")) for d in days],
        "FULL_DT": days,
        "YEAR_NO": [d.year for d in days],
        "MONTH_NO": [d.month for d in days],
        "DAY_NO": [d.day for d in days],
        "DOW_NO": [d.isoweekday() for d in days],
        "DOW_NM": [DOW_NM[d.weekday()] for d in days],
        "WEEK_NO": [d.isocalendar()[1] for d in days],
        "RC_DAY_YN": ["Y" if d in race_days else "N" for d in days],
    })
    schema = pa.schema([("DATE_KEY", pa.int32()), ("FULL_DT", pa.date32()), ("YEAR_NO", pa.int32()),
                        ("MONTH_NO", pa.int32()), ("DAY_NO", pa.int32()), ("DOW_NO", pa.int32()),
                        ("DOW_NM", pa.string()), ("WEEK_NO", pa.int32()), ("RC_DAY_YN", pa.string())])
    return with_unknown(schema, rows, "DATE_KEY", {"DOW_NM": "UNKNOWN"})


def dim_race(race):
    r = race.sort_values(["RC_DT", "RC_NO"], kind="stable").drop(columns=["_SRC_ROW_NO"]).reset_index(drop=True)
    r.insert(0, "RACE_KEY", range(1, len(r) + 1))
    src = pq.read_schema(C.CLEAN_DIR / "RC_RACE.parquet")
    schema = pa.schema([("RACE_KEY", pa.int32())] + [src.field(c) for c in r.columns[1:]])
    return with_unknown(schema, r, "RACE_KEY", {"RC_TITLE_NM": "UNKNOWN"})


def age_band(age):
    if age is None or pd.isna(age):
        return None
    age = int(age)
    return "2~3세" if age <= 3 else "4~5세" if age <= 5 else "6~7세" if age <= 7 else "8세 이상"


def dim_horse(snap):
    s = snap.sort_values(["HR_NM", "SNAPSHOT_DT"], kind="stable").reset_index(drop=True)
    sig = s[SCD2_COLS].apply(lambda col: col.map(lambda x: "∅" if pd.isna(x) else str(x))).agg("|".join, axis=1)  # 빈 값도 값으로 비교
    v = s[s["HR_NM"].ne(s["HR_NM"].shift()) | sig.ne(sig.shift())].copy()
    v["VALID_FROM_DT"] = v["SNAPSHOT_DT"].map(lambda d: d + timedelta(days=1))  # 스냅샷 다음 날부터 유효
    nxt = v.groupby("HR_NM")["VALID_FROM_DT"].shift(-1)
    v["VALID_TO_DT"] = [END_DT if pd.isna(n) else n - timedelta(days=1) for n in nxt]
    v["CURRENT_YN"] = ["Y" if d == END_DT else "N" for d in v["VALID_TO_DT"]]
    v["AGE_GROUP_NM"] = v["HR_AGE"].map(age_band)
    v = v.sort_values(["HR_NM", "VALID_FROM_DT"], kind="stable").reset_index(drop=True)
    v["HORSE_KEY"] = range(1, len(v) + 1)
    v = v.rename(columns={"SNAPSHOT_DT": "SRC_SNAPSHOT_DT"})
    s_, d_, i_ = pa.string(), pa.date32(), pa.int32()
    schema = pa.schema([("HORSE_KEY", i_), ("HR_NM", s_), ("HR_SEX_CD", s_), ("HR_BIRTH_DT", d_), ("HR_AGE", i_),
                        ("AGE_GROUP_NM", s_), ("HR_GRADE_CD", s_), ("TR_GRP_NO", s_), ("TR_NM", s_),
                        ("TR_EXTERNAL_YN", s_), ("OW_NM", s_), ("SIRE_NM", s_), ("DAM_NM", s_),
                        ("SRC_SNAPSHOT_DT", d_), ("VALID_FROM_DT", d_), ("VALID_TO_DT", d_), ("CURRENT_YN", s_)])
    return with_unknown(schema, v, "HORSE_KEY", {"HR_NM": "UNKNOWN", "CURRENT_YN": "N"})


def dim_trainer(tr):
    t = tr.sort_values(["TR_NM", "SNAPSHOT_DT"], kind="stable").groupby("TR_NM", as_index=False).last()  # 값이 변하지 않음 (Type 1)
    t.insert(0, "TRAINER_KEY", range(1, len(t) + 1))
    schema = pa.schema([("TRAINER_KEY", pa.int32()), ("TR_NM", pa.string()), ("TR_GRP_NO", pa.string()),
                        ("TR_BIRTH_DT", pa.date32()), ("DEBUT_DT", pa.date32())])
    return with_unknown(schema, t, "TRAINER_KEY", {"TR_NM": "UNKNOWN"})


def dim_member(mbr):
    m = mbr.sort_values("MBR_NO", kind="stable").reset_index(drop=True)
    m.insert(0, "MEMBER_KEY", range(1, len(m) + 1))
    m["MBR_TYPE_CD"] = "MEMBER"
    non_member = {"MEMBER_KEY": len(m) + 1, "MBR_TYPE_CD": "NON_MEMBER"}  # 회원번호 빈칸 = 실제 비회원 (전표 기준)
    m = pd.concat([m, pd.DataFrame([non_member])], ignore_index=True)
    schema = pa.schema([("MEMBER_KEY", pa.int32()), ("MBR_NO", pa.string()), ("MBR_TYPE_CD", pa.string()),
                        ("BIRTH_DT", pa.date32()), ("JOIN_DT", pa.date32()), ("REGION_CD", pa.string()),
                        ("MBR_GRADE_CD", pa.string()), ("MBR_STAT_CD", pa.string())])
    return with_unknown(schema, m, "MEMBER_KEY", {"MBR_TYPE_CD": "UNKNOWN"})


def dim_channel(order):
    ch = order[["CHNL_CD", "OTB_BRANCH_NO"]].drop_duplicates()
    ch = ch[ch["CHNL_CD"].ne("UNKNOWN")]  # 채널 빈칸(UNKNOWN)은 키 0 미상 행으로
    ch = ch.sort_values(["CHNL_CD", "OTB_BRANCH_NO"], kind="stable", na_position="first").reset_index(drop=True)
    ch.insert(0, "CHANNEL_KEY", range(1, len(ch) + 1))
    ch["CHNL_NM"] = ch["CHNL_CD"].map(CHNL_NM)
    if ch["CHNL_NM"].isna().any():
        raise ValueError(f"채널 코드표에 없는 값: {sorted(ch.loc[ch.CHNL_NM.isna(), 'CHNL_CD'].unique())}")
    schema = pa.schema([("CHANNEL_KEY", pa.int32()), ("CHNL_CD", pa.string()), ("OTB_BRANCH_NO", pa.string()),
                        ("CHNL_NM", pa.string())])
    return with_unknown(schema, ch, "CHANNEL_KEY", {"CHNL_CD": "UNKNOWN", "CHNL_NM": "미상"})


def build():
    clean = {t: read_clean(t) for t in ["RC_RACE", "HR_VET_HIST", "HR_WEEKLY_SNAPSHOT", "TR_WEEKLY_SNAPSHOT",
                                        "BET_ORDER", "MBR_MASTER"]}
    return {
        "DIM_DATE": dim_date(clean),
        "DIM_RACE": dim_race(clean["RC_RACE"]),
        "DIM_HORSE": dim_horse(clean["HR_WEEKLY_SNAPSHOT"]),
        "DIM_TRAINER": dim_trainer(clean["TR_WEEKLY_SNAPSHOT"]),
        "DIM_MEMBER": dim_member(clean["MBR_MASTER"]),
        "DIM_CHANNEL": dim_channel(clean["BET_ORDER"]),
    }


def main():
    COMMON_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in build().items():
        pq.write_table(table, COMMON_DIR / f"{name}.parquet")
        print(f"{name:<12} {table.num_rows:>6,}행")


if __name__ == "__main__":
    main()
