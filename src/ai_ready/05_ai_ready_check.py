"""AI Ready 검증: 생성 코드와 다른 경로(가능하면 clean/에서 직접)로 다시 계산해 확인한다.

1. 행 수 대사: 출주 3,644 + 제외 22 = 출전표 3,666, 행마다 한쪽에만, PK 중복 0
2. 정답 PLACE_YN = clean 결과표의 착순 3 이내 (뛴 말만)
3. 분할: TRAIN 경주일 < 2026-10-10 ≤ TEST 경주일
4. 누수: 결과 컬럼 없음, 과거 성적·진료·매출·취소가 모두 예측 시점(경주일 / 출발 시각) 이전 정보로만 다시 계산됨
5. 팀 숫자: 매출 1,903,091,700원 / 507,383장 / 출발 전 취소 36,902,100원, 취소 피처는 Gold 취소 팩트와 대사
6. 인코딩 테이블: 같은 행 순서, NULL 0, 숫자형만, 원-핫은 행마다 정확히 1개
7. TEST 기준선: 경주마다 3두를 무작위로 / 배당 인기순으로 골랐을 때 실제 3등 이내 비율 (31.0% / 52.4%), 배당 AUC 0.749
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

OUT = C.ROOT / "data" / "04_ai_ready"
SPLIT_DT = pd.Timestamp("2026-10-10")
BASELINE = "BASE_EXPECT_WIN"
FAILS = []


def check(ok, msg):
    print(("  O " if ok else "  X ") + msg)
    if not ok:
        FAILS.append(msg)


def clean(t):
    return pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet")


def same(a, b):
    """NULL끼리는 같다고 보고, 실수는 1e-9까지 같다고 본다."""
    a, b = pd.Series(a).reset_index(drop=True).astype(float), pd.Series(b).reset_index(drop=True).astype(float)
    return int((~(((a - b).abs() < 1e-9) | (a.isna() & b.isna()))).sum())


def main():
    t = pd.read_parquet(OUT / "AI_READY_RACE_ENTRY.parquet")
    enc = pd.read_parquet(OUT / "AI_READY_RACE_ENTRY_ENCODED.parquet")
    exc = pd.read_parquet(OUT / "_excluded" / "AI_READY_RACE_ENTRY.parquet")
    race = pd.read_parquet(C.GOLD_DIR / "common" / "DIM_RACE.parquet")[["RACE_KEY", "RC_DT", "RC_NO", "START_DTM"]]
    race = race[race.RACE_KEY != 0].assign(RC_DT=lambda d: pd.to_datetime(d.RC_DT), RC_NO=lambda d: d.RC_NO.astype(int))
    k3 = ["RC_DT", "RC_NO", "CHUL_NO"]
    x = t.merge(race, on="RACE_KEY", how="left", validate="m:1")  # 행 순서 유지

    ent = clean("RC_ENTRY").assign(RC_DT=lambda d: pd.to_datetime(d.RC_DT))
    res = clean("RC_RESULT").assign(RC_DT=lambda d: pd.to_datetime(d.RC_DT))
    er = ent[k3 + ["HR_NM"]].merge(res[k3 + ["ENTRY_STAT_CD", "FINISH_ORD"]], on=k3, validate="1:1")
    er["RAN"] = er.ENTRY_STAT_CD.eq("RAN")
    er["PLACE"] = (er.RAN & er.FINISH_ORD.le(3)).astype(int)
    er["WIN"] = (er.RAN & er.FINISH_ORD.eq(1)).astype(int)

    print("[1] 행 수 대사")
    ran_n, all_n = int(er.RAN.sum()), len(er)
    check(len(t) == ran_n == 3644, f"AI Ready {len(t):,}행 = clean 출주 {ran_n:,}행")
    check(len(exc) == all_n - ran_n == 22 and exc.EXCLUDE_REASON.eq("NOT_STARTED").all(), f"제외 {len(exc)}행 = 출주하지 않은 말 (사유 기록)")
    keys = set(map(tuple, t[["RACE_KEY", "CHUL_NO"]].values)); ekeys = set(map(tuple, exc[["RACE_KEY", "CHUL_NO"]].values))
    check(not (keys & ekeys) and len(keys) + len(ekeys) == all_n == 3666, f"유지 {len(keys):,} + 제외 {len(ekeys)} = 출전표 {all_n:,}, 겹침 0")
    check(not t.duplicated(["RACE_KEY", "CHUL_NO"]).any(), "PK(RACE_KEY + CHUL_NO) 중복 0")

    print("\n[2] 정답")
    lab = x[k3].merge(er[k3 + ["PLACE", "RAN"]], on=k3, how="left")
    check(lab.RAN.all() and (lab.PLACE.values == t.PLACE_YN.values).all(), f"PLACE_YN = clean 착순 3 이내 ({t.PLACE_YN.mean():.1%})")

    print("\n[3] 분할")
    tr, te = x[x.SPLIT_CD == "TRAIN"], x[x.SPLIT_CD == "TEST"]
    check(tr.RC_DT.max() < SPLIT_DT <= te.RC_DT.min() and len(tr) + len(te) == len(t),
          f"TRAIN {len(tr):,} (~{tr.RC_DT.max().date()}) / TEST {len(te):,} ({te.RC_DT.min().date()}~), 날짜가 겹치지 않음")

    print("\n[4] 누수")
    leak = {"FINISH_ORD", "WIN_CNT", "PLACE_CNT", "START_CNT", "EXPECT_WIN", "ENTRY_STAT_CD", "WIN_ODDS", "PLC_ODDS"}
    check(not (leak & set(t.columns)), "결과·배당 컬럼이 피처에 없음 (배당은 BASE_EXPECT_WIN 기준선으로만)")

    # 과거 성적: 행마다 같은 말의 '이전 날짜' 경주만 루프로 다시 센다
    hist = {n: g.sort_values("RC_DT") for n, g in er.groupby("HR_NM")}
    xr = x.merge(ent[k3 + ["HR_NM"]], on=k3, how="left")
    rows = []
    for r in xr.itertuples():
        h = hist[r.HR_NM]; p = h[h.RC_DT < r.RC_DT]; ran = p[p.RAN]
        rows.append((int(ran.shape[0]), int(p.WIN.sum()), int(p.PLACE.sum()),
                     p.PLACE.sum() / ran.shape[0] if len(ran) else None, (r.RC_DT - ran.RC_DT.max()).days if len(ran) else None))
    pf = pd.DataFrame(rows, columns=["S", "W", "P", "R", "D"])
    d = same(pf.S, t.PRIOR_START_CNT) + same(pf.W, t.PRIOR_WIN_CNT) + same(pf.P, t.PRIOR_PLACE_CNT) + same(pf.R, t.PRIOR_PLACE_RATE) + same(pf.D, t.DAYS_SINCE_LAST_RACE)
    check(d == 0, f"과거 성적 5개 = 경주일 이전 경주만으로 다시 센 값, 불일치 {d}")

    # 진료: clean 진료 이력에서 직접 (이전 스냅샷 없는 71건은 Gold 말 키 0이라 제외)
    v = clean("HR_VET_HIST")
    v = v[v.PRIOR_SNAPSHOT_MISSING_YN.eq("N")].assign(VD=lambda q: pd.to_datetime(q.VET_DT), RD=lambda q: pd.to_datetime(q.REPORT_DT))
    br = clean("HR_VET_TYPE_BRIDGE"); lame = set(br[br.VET_TYPE_NM.str.contains("파행")].VET_SEQ)
    vh = {n: g for n, g in v.groupby("HR_NM")}
    c30, c90, l90 = [], [], []
    for r in xr.itertuples():
        g = vh.get(r.HR_NM, v.iloc[0:0]); g = g[(g.VD < r.RC_DT) & (g.RD < r.RC_DT)]
        dd = (r.RC_DT - g.VD).dt.days
        c30.append(int((dd <= 30).sum())); c90.append(int((dd <= 90).sum())); l90.append("Y" if g[dd <= 90].VET_SEQ.isin(lame).any() else "N")
    d = same(c30, t.VET_CNT_30D) + same(c90, t.VET_CNT_90D) + int((pd.Series(l90).values != t.LAMENESS_90D_YN.values).sum())
    check(d == 0, f"진료 3개 = 진료일·보고일 모두 경주일 이전인 clean 진료로 다시 센 값, 불일치 {d} (90일 진료 있음 {sum(c > 0 for c in c90):,}행)")
    check(int(v.RD.ge(v.VD).sum()) == len(v), "보고일 ≥ 진료일 (보고일 조건이 더 엄격함을 확인)")

    # 매출: clean 마권·전표에서 직접
    tk, od = clean("BET_TICKET"), clean("BET_ORDER")
    s = tk.merge(od[["ORDER_NO", "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM"]], on="ORDER_NO", validate="m:1")
    s = s.assign(RC_DT=pd.to_datetime(s.RC_DT)).merge(race, on=["RC_DT", "RC_NO"], validate="m:1")
    pre = s[(s.SALE_DTM < s.START_DTM) & s.INVALID_YN.eq("N")]
    sold, canc = pre[pre.TICKET_STAT_CD.eq("SOLD")], pre[pre.TICKET_STAT_CD.eq("CANCEL")]
    a = pd.DataFrame({"SA": sold.groupby("RACE_KEY").BET_AMT.sum(), "SC": sold.groupby("RACE_KEY").size(),
                      "CA": -canc.groupby("RACE_KEY").BET_AMT.sum()}).fillna(0)
    m = x[["RACE_KEY"]].join(a, on="RACE_KEY").fillna(0)
    d = same(m.SA, t.SALES_AMT) + same(m.SC, t.SOLD_TICKET_CNT) + same(m.CA, t.CANCEL_AMT)
    d += same(m.CA / m.SA.where(m.SA > 0), t.CANCEL_RATE) + same(m.SA / m.SC.where(m.SC > 0), t.AVG_TICKET_AMT)
    check(d == 0, f"매출 5개 = 출발 전 clean 마권으로 다시 센 값, 불일치 {d}")
    u = t.drop_duplicates("RACE_KEY")
    check((int(u.SALES_AMT.sum()), int(u.SOLD_TICKET_CNT.sum()), int(u.CANCEL_AMT.sum())) == (1903091700, 507383, 36902100),
          f"희정 님 숫자: 발매액 {int(u.SALES_AMT.sum()):,}원, {int(u.SOLD_TICKET_CNT.sum()):,}장, 출발 전 취소 {int(u.CANCEL_AMT.sum()):,}원")
    late = s[s.TICKET_STAT_CD.eq("CANCEL") & (s.SALE_DTM >= s.START_DTM)]
    check(len(late) == C.EXPECTED_DQ["LATE_CANCEL_TICKET"], f"출발 시각 이후·동시 취소 {len(late):,}행은 매출 피처에서 빠짐 (D-004 늦은 취소와 같은 수)")

    # 취소: 출발 전 거래만으로 다시 판정한 값. Gold 취소 팩트(전체 기간 판정)와 대사
    g = pd.read_parquet(C.GOLD_DIR / "bet_cancel" / "FCT_BET_SELECTION_CANCEL_50S.parquet").merge(t[["RACE_KEY", "CHUL_NO"]], on=["RACE_KEY", "CHUL_NO"])
    vg = g[g.CANCEL_LABEL_STATUS.eq("VERIFIED_CANCEL")]
    pure = vg[vg.LATE_CANCEL_DETAIL_COUNT.eq(0)]
    mixed = vg[vg.LATE_CANCEL_DETAIL_COUNT.gt(0)]
    unres = g[g.CANCEL_LABEL_STATUS.eq("AMBIGUOUS") & g.EXCLUSION_REASONS.str.contains("UNRESOLVED_CANCEL_CONTEXT")
              & ~g.EXCLUSION_REASONS.str.contains("CANCEL_EXCEEDS_PURCHASE") & g.CANCEL_TRANSACTION_COUNT.gt(0)]
    got_cnt, got_amt = int(t.WIN_50S_CANCEL_GROUP_CNT.sum()), int(t.WIN_50S_CANCEL_AMT.sum())
    check((got_cnt, got_amt) == (905, 3812500), f"은빈 님 숫자: 출발 전 확인 취소 {got_cnt:,}묶음 {got_amt:,}원 (기대 905묶음 3,812,500원)")
    check(len(pure) <= got_cnt <= len(pure) + len(mixed) + len(unres) and int(pure.VERIFIED_CANCEL_AMOUNT_KRW.sum()) <= got_amt,
          f"Gold 확인 취소 중 출발 전만 있는 {len(pure):,}묶음 {int(pure.VERIFIED_CANCEL_AMOUNT_KRW.sum()):,}원은 모두 포함, "
          f"나머지는 출발 전·후가 섞인 {len(mixed)}묶음의 출발 전 부분과 연결 불확실 {len(unres)}묶음 중 출발 전에는 문제없는 묶음")
    pt = pure.groupby(["RACE_KEY", "CHUL_NO"]).VERIFIED_CANCEL_AMOUNT_KRW.sum()
    bad = int((t.set_index(["RACE_KEY", "CHUL_NO"]).WIN_50S_CANCEL_AMT.reindex(pt.index) < pt).sum())
    check(bad == 0, f"말마다 취소액 ≥ Gold의 출발 전 확인 취소액, 미달 {bad}")
    check(int((t.WIN_50S_CANCEL_AMT > t.WIN_50S_PURCHASE_AMT).sum()) == 0 and int((t.WIN_50S_CANCEL_GROUP_CNT > t.WIN_50S_PURCHASE_GROUP_CNT).sum()) == 0,
          "말마다 취소액 ≤ 구매액, 취소 묶음 수 ≤ 구매 묶음 수")
    nz = t[t.WIN_50S_PURCHASE_AMT > 0]
    check(t.WIN_50S_CANCEL_AMT_RATE.isna().sum() == int((t.WIN_50S_PURCHASE_AMT == 0).sum()) and nz.WIN_50S_CANCEL_AMT_RATE.notna().all(),
          f"구매 없는 말 {int((t.WIN_50S_PURCHASE_AMT == 0).sum())}두만 취소율 NULL")

    print("\n[5] 인코딩 테이블")
    check(len(enc) == len(t) and (enc[["RACE_KEY", "CHUL_NO"]].values == t[["RACE_KEY", "CHUL_NO"]].values).all(), "행 수·순서가 같음")
    feat = enc.drop(columns=["SPLIT_CD"])
    check(int(feat.isna().sum().sum()) == 0 and all(pd.api.types.is_numeric_dtype(feat[c]) for c in feat), f"NULL 0, 숫자형만 ({feat.shape[1]}컬럼)")
    for c in ["HR_SEX_CD", "HR_GRADE_CD", "TRAINER_KEY", "RC_GRADE_CD", "WEATHER_CD", "TRACK_STAT_CD"]:
        oh = enc[[k for k in enc if k.startswith(c + "__")]]
        check((oh.sum(axis=1) == 1).all(), f"{c}: 원-핫 {oh.shape[1]}개, 행마다 정확히 1")

    print("\n[6] TEST 기준선 (경주마다 3두를 골랐을 때 실제 3등 이내 비율)")
    # 배당은 AI Ready의 BASE_EXPECT_WIN이 아니라 clean 배당표의 단승 배당(낮을수록 인기)으로 다시 고른다
    odds = clean("RC_ODDS").assign(RC_DT=lambda d: pd.to_datetime(d.RC_DT))[k3 + ["WIN_ODDS"]]
    b = x.loc[x.SPLIT_CD == "TEST", k3 + ["RACE_KEY", "PLACE_YN", BASELINE]].merge(odds, on=k3, how="left", validate="1:1")
    g = b.groupby("RACE_KEY")
    rand = float((g.PLACE_YN.sum() / g.size()).mean())  # 무작위 3두: 한 두가 맞을 확률 = 3등 이내 두수 / 출주 두수
    b = b.sort_values(["RACE_KEY", "WIN_ODDS", "CHUL_NO"])
    top = b.groupby("RACE_KEY").head(3)
    tie = int(b.groupby("RACE_KEY").WIN_ODDS.apply(lambda s: len(s) > 3 and s.iloc[2] == s.iloc[3]).sum())
    r = b[BASELINE].rank()  # AUC: 3등 이내 말의 배당 확률이 아닌 말보다 높을 확률 (순위 합 공식)
    n1 = int(b.PLACE_YN.sum()); n0 = len(b) - n1
    auc = float((r[b.PLACE_YN == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
    check(g.ngroups == 77 and len(b) == 749 and g.PLACE_YN.sum().eq(3).all(), f"TEST {g.ngroups}경주 {len(b)}두, 경주마다 3등 이내 정확히 3두")
    check(round(b.PLACE_YN.mean(), 3) == 0.308, f"TEST 전체 3등 이내 비율 {b.PLACE_YN.mean():.1%} (기대 30.8%)")
    check(round(rand, 3) == 0.310, f"무작위 3두: 평균 {rand:.1%} 적중 (기대 31.0%)")
    check(tie == 0 and int(top.PLACE_YN.sum()) == 121 and len(top) == 231,
          f"배당 인기 상위 3두: {int(top.PLACE_YN.sum())}/{len(top)} = {top.PLACE_YN.mean():.1%} 적중 (기대 121/231 = 52.4%, 3·4위 배당 같은 경주 {tie})")
    check(round(auc, 3) == 0.749, f"배당 확률의 AUC {auc:.3f} (기대 0.749)")

    print("\nAI Ready 검증:", "통과" if not FAILS else f"실패 {len(FAILS)}건")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
