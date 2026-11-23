"""Silver 품질 관리 결과(02_silver/clean/) → Gold 스타 스키마(03_gold/): 경주 출전

- 업무 프로세스: 경주 출전
- 팩트 FCT_RACE_ENTRY 그레인: 경주별 출전마 1두 (RC_DT + RC_NO + CHUL_NO), 출전표(RC_ENTRY) 1행 = 팩트 1행
- 측정값: START_CNT(출주), WIN_CNT(1착), PLACE_CNT(3착 안), EXPECT_WIN(배당 기반 예상 우승 확률)
- 차원: DIM_DATE, DIM_RACE, DIM_HORSE(SCD2), DIM_TRAINER

규칙 (팀 요청서)
1. 착순 94 = 경주제외, 95 = 출주취소 → 순위 아님, START_CNT = 0
2. 말 ID가 없어 마명(HR_NM)으로 연결
3. 말 속성은 경주일 '이전'(엄격) 가장 최근 스냅샷 기준. DIM_HORSE는 SCD2
4. 팩트에는 키 + 측정값만. 설명 속성은 차원에 둔다. 승률은 저장하지 않는다 (조회할 때 SUM으로 계산)
5. 기대값: SUM(START_CNT) = 3,644, SUM(WIN_CNT) ≈ 386, 우승률 약 10.6%

입력은 D-012에 따라 clean/만 쓴다. 대리키는 자연키로 정렬한 순번(1부터)이라 재실행해도 같다.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

GOLD_DIR = C.GOLD_DIR / "race_entry"

END_DT = date(9999, 12, 31)
DOW_NM = ["월", "화", "수", "목", "금", "토", "일"]
# SCD2 버전을 나누는 속성 (바뀌면 새 버전). 레이팅·통산 성적은 매주 바뀌어 차원에 넣지 않는다
SCD2_COLS = ["HR_SEX_CD", "HR_GRADE_CD", "HR_AGE", "TR_GRP_NO", "TR_NM", "TR_EXTERNAL_YN", "OW_NM"]
STATIC_COLS = ["HR_BIRTH_DT", "SIRE_NM", "DAM_NM"]  # 말마다 변하지 않음 (확인 완료)


def age_band(age):
    if age is None or pd.isna(age):
        return None
    age = int(age)
    return "2~3세" if age <= 3 else "4~5세" if age <= 5 else "6~7세" if age <= 7 else "8세 이상"


def read_clean(t):
    return pq.read_table(C.CLEAN_DIR / f"{t}.parquet")


def write(name, table):
    pq.write_table(table, GOLD_DIR / f"{name}.parquet")
    print(f"{name:<16} {table.num_rows:>7,}행")


def dim_date(race):
    lo, hi = race["RC_DT"].min(), race["RC_DT"].max()
    days = [lo + timedelta(days=i) for i in range((hi - lo).days + 1)]
    race_days = set(race["RC_DT"])
    return pa.table({
        "DATE_KEY": pa.array([int(d.strftime("%Y%m%d")) for d in days], pa.int32()),
        "FULL_DT": pa.array(days, pa.date32()),
        "YEAR_NO": pa.array([d.year for d in days], pa.int32()),
        "MONTH_NO": pa.array([d.month for d in days], pa.int32()),
        "DAY_NO": pa.array([d.day for d in days], pa.int32()),
        "DOW_NO": pa.array([d.isoweekday() for d in days], pa.int32()),
        "DOW_NM": pa.array([DOW_NM[d.weekday()] for d in days], pa.string()),
        "WEEK_NO": pa.array([d.isocalendar()[1] for d in days], pa.int32()),
        "RACE_DAY_YN": pa.array(["Y" if d in race_days else "N" for d in days], pa.string()),
    })


def dim_race(race_pa):
    race_pa = race_pa.sort_by([("RC_DT", "ascending"), ("RC_NO", "ascending")]).drop(["_SRC_ROW_NO"])
    return race_pa.add_column(0, "RACE_KEY", pa.array(range(1, race_pa.num_rows + 1), pa.int32()))


def dim_horse(snap):
    s = snap.sort_values(["HR_NM", "SNAPSHOT_DT"], kind="stable").reset_index(drop=True)
    sig = s[SCD2_COLS].apply(lambda col: col.map(lambda x: "∅" if pd.isna(x) else str(x))).agg("|".join, axis=1)  # 빈 값도 값으로 비교
    new_ver = s["HR_NM"].ne(s["HR_NM"].shift()) | sig.ne(sig.shift())
    v = s[new_ver].copy()
    v["VALID_FROM_DT"] = v["SNAPSHOT_DT"].map(lambda d: d + timedelta(days=1))  # 스냅샷 다음 날부터 유효 = 경주일 '이전' 스냅샷
    nxt = v.groupby("HR_NM")["VALID_FROM_DT"].shift(-1)
    v["VALID_TO_DT"] = [END_DT if pd.isna(n) else n - timedelta(days=1) for n in nxt]
    v["CURRENT_YN"] = ["Y" if d == END_DT else "N" for d in v["VALID_TO_DT"]]
    v["AGE_BAND_NM"] = v["HR_AGE"].map(age_band)
    v = v.sort_values(["HR_NM", "VALID_FROM_DT"], kind="stable").reset_index(drop=True)
    str_cols = ["HR_NM", "HR_SEX_CD", "HR_GRADE_CD", "AGE_BAND_NM", "TR_GRP_NO", "TR_NM", "TR_EXTERNAL_YN", "OW_NM", "SIRE_NM", "DAM_NM"]
    cols = {"HORSE_KEY": pa.array(range(1, len(v) + 1), pa.int32())}
    for c in ["HR_NM", "HR_SEX_CD", "HR_BIRTH_DT", "HR_AGE", "AGE_BAND_NM", "HR_GRADE_CD", "TR_GRP_NO", "TR_NM",
              "TR_EXTERNAL_YN", "OW_NM", "SIRE_NM", "DAM_NM", "SNAPSHOT_DT", "VALID_FROM_DT", "VALID_TO_DT", "CURRENT_YN"]:
        vals = [None if (x is None or (isinstance(x, float) and pd.isna(x))) else x for x in v[c].tolist()]
        typ = pa.string() if c in str_cols or c == "CURRENT_YN" else pa.int32() if c == "HR_AGE" else pa.date32()
        cols["SRC_SNAPSHOT_DT" if c == "SNAPSHOT_DT" else c] = pa.array(vals, typ)
    return pa.table(cols)


def dim_trainer(tr):
    t = tr.sort_values(["TR_NM", "SNAPSHOT_DT"], kind="stable").groupby("TR_NM", as_index=False).last()  # 값이 변하지 않음 (Type 1)
    return pa.table({
        "TRAINER_KEY": pa.array(range(1, len(t) + 1), pa.int32()),
        "TR_NM": pa.array(t["TR_NM"].tolist(), pa.string()),
        "TR_GRP_NO": pa.array(t["TR_GRP_NO"].tolist(), pa.string()),
        "TR_BIRTH_DT": pa.array(t["TR_BIRTH_DT"].tolist(), pa.date32()),
        "DEBUT_DT": pa.array(t["DEBUT_DT"].tolist(), pa.date32()),
    })


def fact(entry, res, odds, d_race, d_horse, d_trainer):
    k3 = ["RC_DT", "RC_NO", "CHUL_NO"]
    f = entry[k3 + ["HR_NM", "TR_NM"]].merge(res[k3 + ["ENTRY_STAT_CD", "FINISH_ORD"]], on=k3, how="left", validate="1:1")
    f = f.merge(odds[k3 + ["WIN_ODDS"]], on=k3, how="left", validate="1:1")
    f = f.merge(d_race[["RACE_KEY", "RC_DT", "RC_NO"]], on=["RC_DT", "RC_NO"], how="left", validate="m:1")
    f = f.merge(d_trainer[["TRAINER_KEY", "TR_NM"]], on="TR_NM", how="left", validate="m:1")

    # 말: 경주일이 버전 유효 기간 안에 드는 버전 (VALID_FROM_DT = 스냅샷 다음 날이라 '이전' 스냅샷 기준이 됨)
    hv = d_horse[["HORSE_KEY", "HR_NM", "VALID_FROM_DT", "VALID_TO_DT"]].assign(F=lambda d: pd.to_datetime(d.VALID_FROM_DT))
    f["D"] = pd.to_datetime(f["RC_DT"])
    f = pd.merge_asof(f.sort_values("D"), hv.sort_values("F"), left_on="D", right_on="F", by="HR_NM", direction="backward")
    f.loc[pd.to_datetime(f["VALID_TO_DT"]) < f["D"], "HORSE_KEY"] = pd.NA

    ran = f["ENTRY_STAT_CD"].eq("RAN")
    f["START_CNT"] = ran.astype(int)
    f["WIN_CNT"] = (ran & f["FINISH_ORD"].eq(1)).astype(int)
    f["PLACE_CNT"] = (ran & f["FINISH_ORD"].le(3)).astype(int)
    inv = (1 / f["WIN_ODDS"].astype(float)).where(ran, 0.0).fillna(0.0)  # 뛰지 않은 말은 0
    f["EXPECT_WIN"] = inv / inv.groupby([f["RC_DT"], f["RC_NO"]]).transform("sum")
    f["DATE_KEY"] = f["RC_DT"].map(lambda d: int(d.strftime("%Y%m%d")))
    f = f.sort_values(["RACE_KEY", "CHUL_NO"], kind="stable")
    return pa.table({
        "RACE_KEY": pa.array(f["RACE_KEY"].astype(int).tolist(), pa.int32()),
        "CHUL_NO": pa.array(f["CHUL_NO"].astype(int).tolist(), pa.int32()),
        "DATE_KEY": pa.array(f["DATE_KEY"].tolist(), pa.int32()),
        "HORSE_KEY": pa.array(f["HORSE_KEY"].astype("Int64").tolist(), pa.int32()),
        "TRAINER_KEY": pa.array(f["TRAINER_KEY"].astype("Int64").tolist(), pa.int32()),
        "START_CNT": pa.array(f["START_CNT"].tolist(), pa.int32()),
        "WIN_CNT": pa.array(f["WIN_CNT"].tolist(), pa.int32()),
        "PLACE_CNT": pa.array(f["PLACE_CNT"].tolist(), pa.int32()),
        "EXPECT_WIN": pa.array(f["EXPECT_WIN"].tolist(), pa.float64()),
    })


def main():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    race_pa = read_clean("RC_RACE")
    race = race_pa.to_pandas()
    entry, res, odds = (read_clean(t).to_pandas() for t in ["RC_ENTRY", "RC_RESULT", "RC_ODDS"])
    snap, tr = read_clean("HR_WEEKLY_SNAPSHOT").to_pandas(), read_clean("TR_WEEKLY_SNAPSHOT").to_pandas()

    tables = {"DIM_DATE": dim_date(race), "DIM_RACE": dim_race(race_pa), "DIM_HORSE": dim_horse(snap), "DIM_TRAINER": dim_trainer(tr)}
    tables["FCT_RACE_ENTRY"] = fact(entry, res, odds, tables["DIM_RACE"].to_pandas(), tables["DIM_HORSE"].to_pandas(),
                                    tables["DIM_TRAINER"].to_pandas())
    for name, tb in tables.items():
        write(name, tb)


if __name__ == "__main__":
    main()
