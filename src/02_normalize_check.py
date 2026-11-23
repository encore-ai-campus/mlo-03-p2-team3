"""Silver 검증: 매핑_규칙서 11장 기대값과 비교하고, 원천값이 기록 없이 사라지지 않았는지 확인한다.

기대값과 다르면 숫자를 맞추지 않고 차이를 그대로 출력한다.
"""
import sys

import pandas as pd

import config as C

BRONZE_OF = {  # Silver 테이블 → Bronze 파일
    "BET_ORDER": "bet_order", "BET_TICKET": "bet_ticket", "MBR_MASTER": "MBR_MASTER",
    "HR_WEEKLY_SNAPSHOT": "HR_WEEKLY_SNAPSHOT", "TR_WEEKLY_SNAPSHOT": "TR_WEEKLY_SNAPSHOT",
    "RC_RACE": "RC_RACE", "RC_ENTRY": "RC_ENTRY", "RC_ODDS": "RC_ODDS", "RC_RESULT": "RC_RESULT",
    "RC_SALES": "RC_SALES", "RC_SALES_TOTAL": "RC_SALES", "HR_VET_HIST": "HR_VET_HIST",
    "HR_VET_TYPE_BRIDGE": "HR_VET_HIST", "RC_CHANGE_EVENT": "race_change_events",
}
FAILS = []


def mark(ok, msg):
    if not ok:
        FAILS.append(msg)
    return "O" if ok else "X"


def main():
    silver = {t: pd.read_parquet(C.SILVER_DIR / f"{t}.parquet") for t in C.EXPECTED_SILVER_ROWS}
    bronze = {b: pd.read_parquet(C.BRONZE_DIR / f"{b}.parquet") for b in set(BRONZE_OF.values())}
    issues = pd.read_csv(C.SILVER_ISSUE_LOG, dtype=str, keep_default_na=False)
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    prof = pd.read_csv(C.SILVER_COLUMN_PROFILE, keep_default_na=False)

    # 1. 행 수
    print("[1] 행 수 (기대값: 매핑_규칙서 11장)")
    print(f"  {'테이블':<20} {'기대':>8} {'Silver':>8} {'Bronze':>8}  결과")
    for t, exp in C.EXPECTED_SILVER_ROWS.items():
        n, nb = len(silver[t]), len(bronze[BRONZE_OF[t]])
        print(f"  {t:<20} {exp:>8,} {n:>8,} {nb:>8,}  {mark(n == exp, f'{t} 행 수 {n} ≠ 기대 {exp}')}")

    # 2. 행 보존: Silver의 _SRC_ROW_NO가 Bronze 행과 1:1인지
    print("\n[2] 행 보존 (Bronze 행이 빠짐·중복 없이 Silver에 있는지)")
    for t, b in BRONZE_OF.items():
        if t in ("RC_SALES", "RC_SALES_TOTAL", "HR_VET_TYPE_BRIDGE"):
            continue
        same = sorted(silver[t]["_SRC_ROW_NO"]) == sorted(bronze[b]["_SRC_ROW_NO"])
        print(f"  {t:<20} {mark(same, f'{t} 행 보존 실패')}")
    sales = pd.concat([silver["RC_SALES"]["_SRC_ROW_NO"], silver["RC_SALES_TOTAL"]["_SRC_ROW_NO"]])
    ok = sorted(sales) == sorted(bronze["RC_SALES"]["_SRC_ROW_NO"])
    print(f"  RC_SALES + RC_SALES_TOTAL = Bronze RC_SALES {mark(ok, 'RC_SALES 분리 행 보존 실패')}")
    vet = bronze["HR_VET_HIST"]["VET_NM_RAW"].str.strip()
    items = vet.map(lambda x: len([n for n in x.split(",") if n.strip()]) if x else 0).sum()
    n_br = len(silver["HR_VET_TYPE_BRIDGE"])
    print(f"  HR_VET_TYPE_BRIDGE 행 {n_br:,} = 진료명 항목 수 {items:,} {mark(n_br == items, '브리지 항목 수 불일치')}")

    # 3. 변환 실패 · 코드표 밖 값
    print("\n[3] 변환 실패 / 코드표 밖 값 (기대값: 0건)")
    for code, label in [("PARSE_FAIL", "변환 실패"), ("OUT_OF_CODE", "코드표 밖 값")]:
        x = issues[issues.ISSUE_CD == code]
        print(f"  {label}: {len(x):,}건 {mark(len(x) == 0, f'{label} {len(x)}건')}")
        for (t, c), g in x.groupby(["TABLE_NM", "COL_NM"]):
            print(f"    - {t}.{c}: {len(g):,}건, 예) {g.RAW_VAL.head(3).tolist()}")
    dt_cols = dic[dic.DATA_TYPE.isin(["DATE", "TIMESTAMP", "TIME"])]
    dt_fail = issues[(issues.ISSUE_CD == "PARSE_FAIL") &
                     issues.set_index(["TABLE_NM", "COL_NM"]).index.isin(dt_cols.set_index(["TABLE_NM", "COL_NM"]).index)]
    print(f"  그중 날짜·일시 변환 실패: {len(dt_fail):,}건")

    # 4. NULL · 값 건수 기대값
    print("\n[4] NULL / 값 건수 (기대값: 매핑_규칙서 11장)")
    for (t, c), exp in C.EXPECTED_NULLS.items():
        n = int(silver[t][c].isna().sum())
        print(f"  {t}.{c} NULL {n:>6,} / 기대 {exp:>6,} {mark(n == exp, f'{t}.{c} NULL {n} ≠ {exp}')}")
    for (t, c, v), exp in C.EXPECTED_VALUE_COUNTS.items():
        n = int(silver[t][c].eq(v).sum())
        print(f"  {t}.{c}={v} {n:>6,} / 기대 {exp:>6,} {mark(n == exp, f'{t}.{c}={v} {n} ≠ {exp}')}")
    multi = int(vet.str.contains(",").sum())
    exp = C.EXPECTED_VET_MULTI_NAME_ROWS
    print(f"  HR_VET_HIST 진료명 여러 개 {multi:>6,} / 기대 {exp:>6,} {mark(multi == exp, '진료명 여러 개 건수 불일치')}")
    races = silver["RC_SALES_TOTAL"].groupby(["RC_DT", "RC_NO"]).size()
    ok = len(races) == len(silver["RC_RACE"]) and races.eq(1).all()
    print(f"  RC_SALES_TOTAL 경주마다 1행 {mark(ok, 'RC_SALES_TOTAL 경주당 1행 아님')}")

    # 5. 원천값 기록 보존: 1:1 매핑 컬럼에서 '원천에 값이 있었는데 Silver에서 NULL'인 건수 = 이슈 로그 건수
    print("\n[5] 원천값 보존 (값이 있던 칸이 NULL이 되면 전부 이슈 로그에 있어야 함)")
    used = dic[dic.COL_NM != "(제외)"]
    one_to_one = used.groupby(["TABLE_NM", "SRC_COL"]).filter(lambda g: len(g) == 1)
    bad = []
    for r in one_to_one.itertuples():
        b = bronze[BRONZE_OF[r.TABLE_NM]]
        if r.SRC_COL not in b.columns:
            continue
        rows = b.set_index("_SRC_ROW_NO").loc[silver[r.TABLE_NM]["_SRC_ROW_NO"], r.SRC_COL]
        had_val = rows.str.strip().ne("").values  # '-----' 같은 '값 없음' 표시도 원천값으로 보고 기록 여부를 본다
        lost = int((had_val & silver[r.TABLE_NM][r.COL_NM].isna().values).sum())
        logged = int(((issues.TABLE_NM == r.TABLE_NM) & (issues.COL_NM == r.COL_NM)).sum())
        if lost != logged:
            bad.append(f"{r.TABLE_NM}.{r.COL_NM}: NULL로 바뀐 원천값 {lost} / 로그 {logged}")
    print(f"  점검 컬럼 {len(one_to_one)}개, 불일치 {len(bad)}개 {mark(not bad, '원천값 보존 불일치')}")
    for m in bad:
        print("    -", m)

    # 6. 모든 Bronze 컬럼이 데이터 사전에 (사용 또는 제외로) 기록됐는지
    print("\n[6] Bronze 컬럼 사용 기록 (데이터 사전에 없는 원천 컬럼)")
    missing = []
    for t, b in BRONZE_OF.items():
        cols = [c for c in bronze[b].columns if not c.startswith("_") and c != "RAW_JSON"]
        srcs = set(dic[dic.TABLE_NM == t].SRC_COL.str.split(r" \+ ").explode())
        if t in ("RC_SALES_TOTAL", "HR_VET_TYPE_BRIDGE"):
            continue
        missing += [f"{t}.{c}" for c in cols if c not in srcs]
    print(f"  {len(missing)}개 {mark(not missing, '데이터 사전 누락 컬럼')} {missing if missing else ''}")

    print("\n[참고] 규칙상 NULL로 둔 원천값 (이슈 로그 RULE_NULL, 원천값 보존)")
    rn = issues[issues.ISSUE_CD == "RULE_NULL"].groupby(["TABLE_NM", "COL_NM", "NOTE"]).size()
    for (t, c, note), n in rn.items():
        print(f"  {t}.{c:<16} {n:>6,}건  {note}")

    print("\nSilver 검증:", "통과" if not FAILS else f"불일치 {len(FAILS)}건")
    for f in FAILS:
        print("  -", f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
