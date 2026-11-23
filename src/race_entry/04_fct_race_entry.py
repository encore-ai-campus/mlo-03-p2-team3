"""Silver 품질 관리 결과(02_silver/clean/) + 공통 차원(03_gold/common/) → Gold 팩트(03_gold/race_entry/): 경주 출전

- 업무 프로세스: 경주 출전
- 팩트 FCT_RACE_ENTRY 그레인: 경주별 출전마 1두 (RC_DT + RC_NO + CHUL_NO), 출전표(RC_ENTRY) 1행 = 팩트 1행
- 측정값: START_CNT(출주), WIN_CNT(1착), PLACE_CNT(3착 안), EXPECT_WIN_RT(배당 기반 예상 우승 확률)
- 차원: 공통 차원 DIM_DATE, DIM_RACE, DIM_HORSE(SCD2), DIM_TRAINER (src/common/04_common_dims.py, D-013 ~ D-015)

규칙 (팀 요청서)
1. 착순 94 = 경주제외, 95 = 출주취소 → 순위 아님, START_CNT = 0
2. 말 ID가 없어 마명(HR_NM)으로 연결
3. 말 속성은 경주일 '이전'(엄격) 가장 최근 스냅샷 기준: VALID_FROM_DT <= 경주일 <= VALID_TO_DT (D-015)
4. 팩트에는 키 + 측정값만. 설명 속성은 차원에 둔다. 승률은 저장하지 않는다 (조회할 때 SUM으로 계산)
5. 기대값: SUM(START_CNT) = 3,644, SUM(WIN_CNT) ≈ 386, 우승률 약 10.6%
6. 차원에서 못 찾은 키는 미상 행 0 (D-013)

입력은 D-012에 따라 clean/만 쓴다. 공통 차원을 먼저 만든 뒤 실행한다.
"""
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

GOLD_DIR = C.GOLD_DIR / "race_entry"
COMMON_DIR = C.GOLD_DIR / "common"
UNKNOWN_KEY = 0


def read_clean(t):
    return pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet")


def read_common(t):
    return pd.read_parquet(COMMON_DIR / f"{t}.parquet")


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
    f["EXPECT_WIN_RT"] = inv / inv.groupby([f["RC_DT"], f["RC_NO"]]).transform("sum")
    f["DATE_KEY"] = f["RC_DT"].map(lambda d: int(d.strftime("%Y%m%d")))
    for k in ["RACE_KEY", "HORSE_KEY", "TRAINER_KEY"]:
        f[k] = f[k].fillna(UNKNOWN_KEY)  # 차원에서 못 찾으면 미상 행 (D-013)
    f = f.sort_values(["RACE_KEY", "CHUL_NO"], kind="stable")
    return pa.table({
        "RACE_KEY": pa.array(f["RACE_KEY"].astype(int).tolist(), pa.int32()),
        "CHUL_NO": pa.array(f["CHUL_NO"].astype(int).tolist(), pa.int32()),
        "DATE_KEY": pa.array(f["DATE_KEY"].tolist(), pa.int32()),
        "HORSE_KEY": pa.array(f["HORSE_KEY"].astype(int).tolist(), pa.int32()),
        "TRAINER_KEY": pa.array(f["TRAINER_KEY"].astype(int).tolist(), pa.int32()),
        "START_CNT": pa.array(f["START_CNT"].tolist(), pa.int32()),
        "WIN_CNT": pa.array(f["WIN_CNT"].tolist(), pa.int32()),
        "PLACE_CNT": pa.array(f["PLACE_CNT"].tolist(), pa.int32()),
        "EXPECT_WIN_RT": pa.array(f["EXPECT_WIN_RT"].tolist(), pa.float64()),
    })


def main():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    entry, res, odds = (read_clean(t) for t in ["RC_ENTRY", "RC_RESULT", "RC_ODDS"])
    d_race, d_horse, d_trainer = (read_common(t) for t in ["DIM_RACE", "DIM_HORSE", "DIM_TRAINER"])
    d_race, d_horse, d_trainer = (d[d.iloc[:, 0] != UNKNOWN_KEY] for d in (d_race, d_horse, d_trainer))  # 미상 행은 연결 대상 아님
    table = fact(entry, res, odds, d_race, d_horse, d_trainer)
    pq.write_table(table, GOLD_DIR / "FCT_RACE_ENTRY.parquet")
    print(f"FCT_RACE_ENTRY   {table.num_rows:>7,}행")


if __name__ == "__main__":
    main()
