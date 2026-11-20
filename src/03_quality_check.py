"""품질 관리 검증: 처리 코드(03_quality.py)를 쓰지 않고 Silver 표준화 결과에서 직접 다시 계산해 확인한다.

1. 대사: 표준화 직후 = clean + _excluded, 각 행은 한쪽에만 (브리지는 D-011로 따로)
2. 표시·보정 건수 = 팀 기준 숫자 (config.EXPECTED_DQ)
3. 표시 컬럼이 독립 계산과 행 단위로 같은지
4. 표준화 결과는 바뀌지 않았는지 (clean의 원래 컬럼 = 표준화 결과, 보정 컬럼 제외)
5. 모든 규칙과 처리 로그에 근거 결정 ID가 있고, 결정 로그에 있는 ID인지
"""
import re
import sys

import pandas as pd

import config as C

FAILS = []


def check(ok, msg):
    print(("  O " if ok else "  X ") + msg)
    if not ok:
        FAILS.append(msg)


def main():
    tables = list(C.EXPECTED_SILVER_ROWS)
    std = {t: pd.read_parquet(C.SILVER_DIR / f"{t}.parquet") for t in tables}
    cl = {t: pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet") for t in tables}
    ex = pd.read_parquet(C.EXCLUDED_DIR / "BET_TICKET.parquet")
    log = pd.read_csv(C.DQ_LOG, dtype=str, keep_default_na=False)
    rs = pd.read_csv(C.DQ_RESULT, dtype=str, keep_default_na=False)
    E = C.EXPECTED_DQ

    print("[1] 행 수 대사 (D-008)")
    for t in tables:
        if t == "HR_VET_TYPE_BRIDGE":
            continue
        e = ex if t == "BET_TICKET" else pd.DataFrame({"_SRC_ROW_NO": []})
        a, b, s = set(cl[t]._SRC_ROW_NO), set(e._SRC_ROW_NO), set(std[t]._SRC_ROW_NO)
        check(len(std[t]) == len(cl[t]) + len(e) and not (a & b) and (a | b) == s,
              f"{t}: 표준화 {len(std[t]):,} = clean {len(cl[t]):,} + 제외 {len(e):,}, 겹침 없음")
    br, brc = std["HR_VET_TYPE_BRIDGE"], cl["HR_VET_TYPE_BRIDGE"]
    check(len(brc) == E["BRIDGE_ROWS_AFTER"] and set(brc.VET_SEQ) == set(br.VET_SEQ),
          f"HR_VET_TYPE_BRIDGE: {len(br):,} → {len(brc):,} (기준 {E['BRIDGE_ROWS_AFTER']:,}), 진료 기록 번호 집합 동일")

    print("\n[2] 완전 중복 (D-002) 독립 재계산")
    t = std["BET_TICKET"]
    biz = [c for c in t.columns if not c.startswith("_")]
    dup = t.sort_values("_SRC_ROW_NO").duplicated(biz, keep="first")
    dup_no = set(t.sort_values("_SRC_ROW_NO")[dup]._SRC_ROW_NO)
    check(dup_no == set(ex._SRC_ROW_NO) and len(dup_no) == E["EXCLUDED_DUP"], f"제외 행 = 재계산 중복 {len(dup_no):,} (기준 {E['EXCLUDED_DUP']:,})")
    kept = t.merge(ex[biz + ["KEPT_SRC_ROW_NO"]].drop_duplicates(), on=biz)
    check((kept.groupby(biz, dropna=False)._SRC_ROW_NO.min().values == kept.groupby(biz, dropna=False).KEPT_SRC_ROW_NO.first().values).all(),
          "제외 행이 가리키는 유지 행 = 같은 업무값 중 최소 _SRC_ROW_NO")
    tc = cl["BET_TICKET"]
    check(not tc.duplicated(["ORDER_NO", "TICKET_SEQ"]).any(), "clean BET_TICKET PK(전표번호 + 순번) 중복 0")

    print("\n[3] 표시·보정 컬럼 독립 재계산 (중복 제거 후 기준)")
    d = t[~t._SRC_ROW_NO.isin(dup_no)]
    o, race, entry = std["BET_ORDER"], std["RC_RACE"], std["RC_ENTRY"]
    oc = cl["BET_ORDER"]
    exp = {"INVALID_YN": set(d[d.BET_AMT == 0]._SRC_ROW_NO)}
    x = d.merge(o[["ORDER_NO", "ORDER_TYPE_CD", "SALE_DTM"]], on="ORDER_NO").merge(race[["RC_DT", "RC_NO", "START_DTM"]], on=["RC_DT", "RC_NO"])
    late = x[(x.ORDER_TYPE_CD == "CANCEL") & (x.SALE_DTM >= x.START_DTM)]
    exp["LATE_CANCEL_TICKET"] = set(late._SRC_ROW_NO)
    exp["LATE_CANCEL_ORDER"] = set(o[o.ORDER_NO.isin(late.ORDER_NO)]._SRC_ROW_NO)
    exp["HR_NM_FILLED_YN"] = set(d[d.HR_NM.isna()]._SRC_ROW_NO)
    g = d.groupby("ORDER_NO").agg(A=("BET_AMT", "sum"), N=("BET_AMT", "size"))
    j = o.merge(g, left_on="ORDER_NO", right_index=True, how="left")
    exp["HEADER_MISMATCH_YN"] = set(j[(j.TOTAL_AMT != j.A) | (j.TICKET_CNT != j.N)]._SRC_ROW_NO)
    exp["ORIG_MISSING_YN"] = set(o[(o.ORDER_TYPE_CD == "CANCEL") & o.ORIG_ORDER_NO.isna()]._SRC_ROW_NO)
    v = std["HR_VET_HIST"].assign(D=lambda q: pd.to_datetime(q.VET_DT)).sort_values("D")
    h = std["HR_WEEKLY_SNAPSHOT"].assign(D=lambda q: pd.to_datetime(q.SNAPSHOT_DT)).sort_values("D")
    mm = pd.merge_asof(v, h[["HR_NM", "D", "TR_GRP_NO"]], on="D", by="HR_NM", allow_exact_matches=False, suffixes=("", "_S"))
    exp["PRIOR_SNAPSHOT_MISSING_YN"] = set(mm[mm.TR_GRP_NO_S.isna()]._SRC_ROW_NO)
    exp["TR_GRP_MISMATCH_YN"] = set(mm[mm.TR_GRP_NO_S.notna() & (mm.TR_GRP_NO != mm.TR_GRP_NO_S)]._SRC_ROW_NO)
    got = {
        "INVALID_YN": set(tc[tc.INVALID_YN == "Y"]._SRC_ROW_NO), "LATE_CANCEL_TICKET": set(tc[tc.LATE_CANCEL_YN == "Y"]._SRC_ROW_NO),
        "LATE_CANCEL_ORDER": set(oc[oc.LATE_CANCEL_YN == "Y"]._SRC_ROW_NO), "HR_NM_FILLED_YN": set(tc[tc.HR_NM_FILLED_YN == "Y"]._SRC_ROW_NO),
        "HEADER_MISMATCH_YN": set(oc[oc.HEADER_MISMATCH_YN == "Y"]._SRC_ROW_NO), "ORIG_MISSING_YN": set(oc[oc.ORIG_MISSING_YN == "Y"]._SRC_ROW_NO),
        "PRIOR_SNAPSHOT_MISSING_YN": set(cl["HR_VET_HIST"].query("PRIOR_SNAPSHOT_MISSING_YN == 'Y'")._SRC_ROW_NO),
        "TR_GRP_MISMATCH_YN": set(cl["HR_VET_HIST"].query("TR_GRP_MISMATCH_YN == 'Y'")._SRC_ROW_NO),
    }
    for k in got:
        check(got[k] == exp[k] and len(got[k]) == E[k], f"{k}: {len(got[k]):,} (기준 {E[k]:,}), 행 단위 일치")
    check(int(((tc.INVALID_YN == "Y") & (tc.LATE_CANCEL_YN == "Y")).sum()) == 0, "0원 늦은 취소 0건 (D-004 별도 표시 대상)")

    filled = tc[tc.HR_NM_FILLED_YN == "Y"].merge(entry[["RC_DT", "RC_NO", "CHUL_NO", "HR_NM"]], on=["RC_DT", "RC_NO", "CHUL_NO"], suffixes=("", "_E"))
    check(len(filled) == E["HR_NM_FILLED_YN"] and (filled.HR_NM == filled.HR_NM_E).all() and tc.HR_NM.isna().sum() == 0,
          "보정한 마명 = 출전표 마명, clean 마명 빈칸 0")
    merged = brc[brc.VET_TYPE_MERGED_YN == "Y"]
    check(sorted(merged._SRC_ROW_NO) == [595, 664] and (merged.VET_TYPE_NM == "일·열사병").all()
          and (cl["HR_VET_HIST"].set_index("VET_SEQ").loc[[595, 664], "VET_NM"] == "일,열사병").all(),
          "진료명 통합 (D-011): 595·664번은 '일·열사병' 1행, 원문 VET_NM은 보존")

    print("\n[4] 표준화 값 보존 (보정 컬럼 외에는 clean = 표준화 결과)")
    for tname in tables:
        if tname == "HR_VET_TYPE_BRIDGE":
            continue
        a = std[tname].set_index("_SRC_ROW_NO")
        b = cl[tname].set_index("_SRC_ROW_NO").loc[:, a.columns].loc[a.index.intersection(cl[tname]._SRC_ROW_NO)]
        a = a.loc[b.index]
        cols = [c for c in a.columns if not (tname == "BET_TICKET" and c == "HR_NM")]
        same = a[cols].astype(str).equals(b[cols].astype(str))
        if tname == "BET_TICKET":
            keep = tc.HR_NM_FILLED_YN.values != "Y"
            same &= a["HR_NM"].astype(str).values[keep].tolist() == b["HR_NM"].astype(str).values[keep].tolist()
        check(same, f"{tname}: 원래 컬럼 값이 표준화 결과와 같음")

    print("\n[5] 근거 결정 ID")
    known = set(re.findall(r"\| (D-\d{3}|MR-\d+) \|", (C.META_DIR / "decision_log.md").read_text(encoding="utf-8")))
    check(rs.DECISION_ID.ne("").all() and set(rs.DECISION_ID) <= known, f"규칙 {len(rs)}개 모두 결정 로그에 있는 근거 ID를 가짐")
    check(log.RULE_ID.ne("").all() and log.DECISION_ID.ne("").all() and set(log.DECISION_ID) <= known and log.BRONZE_FILE.ne("").all()
          and log.SRC_ROW_NO.ne("").all(), f"처리 로그 {len(log):,}행 모두 규칙 ID·결정 ID·Bronze 경로·원천 행 번호를 가짐")
    zero_rules = rs[rs.ACTION == "CHECK"]
    check((zero_rules.FINAL_CNT.astype(int) == 0).all(), f"확인용 규칙 {len(zero_rules)}개 위반 0")

    print("\n품질 검증:", "통과" if not FAILS else f"실패 {len(FAILS)}건")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
