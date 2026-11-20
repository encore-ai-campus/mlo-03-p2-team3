"""Gold 검증: 스타 스키마(FCT_RACE_ENTRY + 차원 4개)를 clean/에서 독립적으로 다시 계산해 확인한다.

1. 테이블마다 PK 중복 0
2. 팩트의 모든 키가 차원에 있음
3. 팩트 그레인 = 출전표 1행 (3,666), 측정값 기대값 (출주 3,644 / 우승 386 / 우승률 약 10.6%)
4. 측정값을 clean의 결과표·배당표에서 행 단위로 다시 계산해 일치
5. DIM_HORSE SCD2: 기간 겹침·빈틈 없음, 현재 버전 1개, 팩트의 말 버전 = 경주일 이전(엄격) 최근 스냅샷
6. 팩트에는 키 + 측정값만
"""
import sys

import pandas as pd

import config as C

FAILS = []
FACT_COLS = ["RACE_KEY", "CHUL_NO", "DATE_KEY", "HORSE_KEY", "TRAINER_KEY", "START_CNT", "WIN_CNT", "PLACE_CNT", "EXPECT_WIN"]


def check(ok, msg):
    print(("  O " if ok else "  X ") + msg)
    if not ok:
        FAILS.append(msg)


def main():
    g = {t: pd.read_parquet(C.GOLD_DIR / f"{t}.parquet") for t in ["DIM_DATE", "DIM_RACE", "DIM_HORSE", "DIM_TRAINER", "FCT_RACE_ENTRY"]}
    cl = {t: pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet") for t in ["RC_ENTRY", "RC_RESULT", "RC_ODDS", "RC_RACE", "HR_WEEKLY_SNAPSHOT"]}
    f, dr, dh, dt, dd = g["FCT_RACE_ENTRY"], g["DIM_RACE"], g["DIM_HORSE"], g["DIM_TRAINER"], g["DIM_DATE"]
    E = C.EXPECTED_GOLD

    print("[1] PK 중복 0")
    for name, df, pk, nat in [("DIM_DATE", dd, ["DATE_KEY"], ["FULL_DT"]), ("DIM_RACE", dr, ["RACE_KEY"], ["RC_DT", "RC_NO"]),
                              ("DIM_HORSE", dh, ["HORSE_KEY"], ["HR_NM", "VALID_FROM_DT"]), ("DIM_TRAINER", dt, ["TRAINER_KEY"], ["TR_NM"]),
                              ("FCT_RACE_ENTRY", f, ["RACE_KEY", "CHUL_NO"], ["RACE_KEY", "CHUL_NO"])]:
        check(not df.duplicated(pk).any() and not df.duplicated(nat).any() and df[pk].notna().all().all(),
              f"{name}: PK({'+'.join(pk)}) 중복 0, 자연키({'+'.join(nat)}) 중복 0, {len(df):,}행")

    print("\n[2] 팩트의 키가 모두 차원에 있음")
    for col, dim, key in [("DATE_KEY", dd, "DATE_KEY"), ("RACE_KEY", dr, "RACE_KEY"), ("HORSE_KEY", dh, "HORSE_KEY"), ("TRAINER_KEY", dt, "TRAINER_KEY")]:
        miss = int((~f[col].isin(dim[key])).sum() + f[col].isna().sum())
        check(miss == 0, f"FCT_RACE_ENTRY.{col} → {key}: 없는 키 {miss}")

    print("\n[3] 그레인과 기대값")
    k3 = ["RC_DT", "RC_NO", "CHUL_NO"]
    fk = f.merge(dr[["RACE_KEY", "RC_DT", "RC_NO"]], on="RACE_KEY")
    ent_keys = set(map(tuple, cl["RC_ENTRY"][k3].values))
    check(len(f) == E["FACT_ROWS"] and set(map(tuple, fk[k3].values)) == ent_keys, f"팩트 {len(f):,}행 = 출전표 {len(ent_keys):,}행 (1:1)")
    for m in ["START_CNT", "WIN_CNT", "PLACE_CNT"]:
        check(int(f[m].sum()) == E[m], f"SUM({m}) = {int(f[m].sum()):,} (기대 {E[m]:,})")
    rate = f.WIN_CNT.sum() / f.START_CNT.sum()
    check(abs(rate - 0.106) < 0.001, f"우승률 SUM(WIN)/SUM(START) = {rate:.2%} (기대 약 10.6%)")
    check(set(fk.DATE_KEY) <= set(dd.DATE_KEY) and (fk.DATE_KEY == fk.RC_DT.map(lambda d: int(d.strftime("%Y%m%d")))).all(),
          "DATE_KEY = 경주일")

    print("\n[4] 측정값 행 단위 재계산 (clean 결과표·배당표 기준)")
    r = fk.merge(cl["RC_RESULT"][k3 + ["ENTRY_STAT_CD", "FINISH_ORD"]], on=k3).merge(cl["RC_ODDS"][k3 + ["WIN_ODDS"]], on=k3)
    ran = r.ENTRY_STAT_CD.eq("RAN")
    check((r.START_CNT == ran.astype(int)).all(), "START_CNT = 출주(RAN)면 1, 경주제외(94)·출주취소(95)면 0")
    check((r.WIN_CNT == (ran & r.FINISH_ORD.eq(1)).astype(int)).all(), "WIN_CNT = 착순 1")
    check((r.PLACE_CNT == (ran & r.FINISH_ORD.le(3)).astype(int)).all(), "PLACE_CNT = 착순 3 이하")
    inv = (1 / r.WIN_ODDS.astype(float)).where(ran, 0.0).fillna(0.0)
    exp = inv / inv.groupby([r.RC_DT, r.RC_NO]).transform("sum")
    check(((r.EXPECT_WIN - exp).abs() < 1e-12).all(), "EXPECT_WIN = 경주 안에서 (1/단승 배당) ÷ Σ(1/단승 배당), 뛰지 않은 말 0")
    per_race = f.groupby("RACE_KEY").EXPECT_WIN.sum()
    check(((per_race - 1).abs() < 1e-9).all() and abs(f.EXPECT_WIN.sum() - f.WIN_CNT.sum()) < 1e-6,
          f"경주마다 EXPECT_WIN 합 = 1, 전체 합 {f.EXPECT_WIN.sum():.6f} ≈ 우승 {int(f.WIN_CNT.sum())}")
    check(((f.START_CNT == 0) <= (f.EXPECT_WIN == 0)).all(), "뛰지 않은 말 22두의 EXPECT_WIN = 0")
    tr = fk.merge(cl["RC_ENTRY"][k3 + ["TR_NM"]], on=k3).merge(dt[["TRAINER_KEY", "TR_NM"]], on="TRAINER_KEY", suffixes=("", "_D"))
    check((tr.TR_NM == tr.TR_NM_D).all(), "TRAINER_KEY = 출전표의 조교사 (경주 당시)")

    print("\n[5] DIM_HORSE SCD2")
    h = dh.sort_values(["HR_NM", "VALID_FROM_DT"])
    nxt = h.groupby("HR_NM").VALID_FROM_DT.shift(-1)
    gap = h[nxt.notna()]
    check(all(a + pd.Timedelta(days=1) == b for a, b in zip(pd.to_datetime(gap.VALID_TO_DT), pd.to_datetime(nxt.dropna()))),
          "말마다 버전 기간이 겹치지 않고 빈틈 없이 이어짐")
    cur = h.groupby("HR_NM").CURRENT_YN.apply(lambda s: (s == "Y").sum())
    check((cur == 1).all() and (h[h.CURRENT_YN == "Y"].VALID_TO_DT.astype(str) == "9999-12-31").all(),
          f"말 {h.HR_NM.nunique():,}두 모두 현재 버전 1개 (VALID_TO_DT = 9999-12-31)")
    check(all(pd.to_datetime(h.VALID_FROM_DT) == pd.to_datetime(h.SRC_SNAPSHOT_DT) + pd.Timedelta(days=1)),
          "VALID_FROM_DT = 버전 시작 스냅샷 다음 날")
    v = fk.merge(dh, on="HORSE_KEY")
    check((pd.to_datetime(v.VALID_FROM_DT) <= pd.to_datetime(v.RC_DT)).all() and (pd.to_datetime(v.RC_DT) <= pd.to_datetime(v.VALID_TO_DT)).all()
          and (pd.to_datetime(v.SRC_SNAPSHOT_DT) < pd.to_datetime(v.RC_DT)).all(), "팩트의 말 버전이 경주일에 유효하고, 버전 스냅샷 < 경주일")
    s = cl["HR_WEEKLY_SNAPSHOT"].assign(D=lambda q: pd.to_datetime(q.SNAPSHOT_DT)).sort_values("D")
    a = pd.merge_asof(v.assign(D=pd.to_datetime(v.RC_DT)).sort_values("D"), s, on="D", by="HR_NM", allow_exact_matches=False, suffixes=("", "_S"))
    cols = ["HR_SEX_CD", "HR_GRADE_CD", "HR_AGE", "TR_GRP_NO", "TR_NM", "OW_NM"]
    diff = sum(int((a[c].astype(str) != a[c + "_S"].astype(str)).sum()) for c in cols)
    check(diff == 0, f"말 속성(성별·등급·나이·조·조교사·마주) = 경주일 이전(엄격) 최근 스냅샷 값, 불일치 {diff}")
    e = fk.merge(cl["RC_ENTRY"][k3 + ["HR_SEX_CD", "HR_AGE"]], on=k3).merge(dh[["HORSE_KEY", "HR_SEX_CD", "HR_AGE"]], on="HORSE_KEY", suffixes=("", "_D"))
    check(((e.HR_SEX_CD == e.HR_SEX_CD_D) & (e.HR_AGE == e.HR_AGE_D)).all(), "출전표의 성별·나이 = 연결된 말 버전의 성별·나이")

    print("\n[6] 팩트 구성")
    check(list(f.columns) == FACT_COLS, "팩트 컬럼 = 키 5개 + 측정값 4개 (설명 속성·비율 없음)")

    print("\nGold 검증:", "통과" if not FAILS else f"실패 {len(FAILS)}건")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
