"""공통 차원 검증: 03_gold/common/의 차원 6개를 clean과 팀 합의 기준으로 확인한다.

1. 테이블마다 PK 중복·NULL 0, 미상 행(키 0) 정확히 1개
2. 행 수 = clean 기준 (차원 범위는 clean 전체)
3. DIM_DATE: 연속, 팩트가 참조하는 clean 날짜를 모두 포함, 범위 = 팀 합의(2026-05-16 ~ 2026-11-18)
4. DIM_HORSE SCD2: 기간 겹침·빈틈 없음, 현재 버전 1개, VALID_FROM_DT = 스냅샷 다음 날
5. 팩트와 연결: 전환한 팩트는 FK가 모두 공통 차원에 있음, 전환 전 팩트는 업무 키가 모두 공통 차원에서 찾아짐
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

COMMON_DIR = C.GOLD_DIR / "common"
EXPECTED_DATE_RANGE = (date(2026, 5, 16), date(2026, 11, 18))
KEYS = {"DIM_DATE": "DATE_KEY", "DIM_RACE": "RACE_KEY", "DIM_HORSE": "HORSE_KEY", "DIM_TRAINER": "TRAINER_KEY",
        "DIM_MEMBER": "MEMBER_KEY", "DIM_CHANNEL": "CHANNEL_KEY"}
FAILS = []


def mark(ok, msg):
    if not ok:
        FAILS.append(msg)
    print(f"  {'O' if ok else 'X'} {msg}")


def gold(path):
    return pd.read_parquet(C.GOLD_DIR / f"{path}.parquet")


def same_rows(a, b):
    """두 차원이 행·값까지 같은지 (NULL끼리 같다고 본다)."""
    a, b = a.reset_index(drop=True), b.reset_index(drop=True)
    return list(a.columns) == list(b.columns) and len(a) == len(b) and all(
        ((a[c] == b[c]) | (a[c].isna() & b[c].isna())).all() for c in a.columns)


# 팩트 FK 컬럼 → 공통 차원 (역할이 여럿인 날짜는 *_DT_KEY, *_DATE_KEY)
def common_dim_of(col):
    if col == "DATE_KEY" or col.endswith(("_DT_KEY", "_DATE_KEY")):
        return "DIM_DATE"
    return {"RACE_KEY": "DIM_RACE", "HORSE_KEY": "DIM_HORSE", "TRAINER_KEY": "DIM_TRAINER",
            "MEMBER_KEY": "DIM_MEMBER", "CHANNEL_KEY": "DIM_CHANNEL"}.get(col)


def check_converted(folder, d):
    """공통 차원으로 전환한 팩트: FK가 모두 공통 차원 키에 있는지."""
    for path in sorted(folder.glob("*.parquet")):
        if path.stem.upper().startswith(("DIM_", "BRIDGE_")):
            continue
        f = pd.read_parquet(path)
        for col in f.columns:
            dim = common_dim_of(col)
            if dim:
                miss = int((~f[col].isin(d[dim][KEYS[dim]])).sum())
                mark(miss == 0, f"{folder.name}/{path.stem}.{col} → common {dim}: 없는 키 {miss}, 미상(0) {int(f[col].eq(0).sum())}")


def before_race_entry(x):
    d = x["d"]
    for n in ["DIM_RACE", "DIM_HORSE", "DIM_TRAINER"]:
        old = gold(f"race_entry/{n}")
        mark(same_rows(d[n][d[n][KEYS[n]] > 0], old), f"race_entry {n}: 미상 행 외에는 키·값 그대로")
    old = gold("race_entry/DIM_DATE")  # 기존 177일(경주 기간)은 그대로, 범위만 넓어짐
    mark(same_rows(d["DIM_DATE"][d["DIM_DATE"].DATE_KEY.isin(old.DATE_KEY)], old),
         f"race_entry DIM_DATE: 기존 {len(old)}일은 키·값 그대로 (공통은 범위만 넓어짐)")


def before_horse_medical(x):
    d, fdates = x["d"], x["fdates"]
    hm_h = gold("horse_medical/DIM_HORSE").sort_values("HORSE_KEY")
    mark(same_rows(d["DIM_HORSE"].drop(columns="HR_NM"), hm_h.drop(columns="HR_NM"))
         and same_rows(d["DIM_HORSE"][["HR_NM"]].iloc[1:], hm_h[["HR_NM"]].iloc[1:]),
         "horse_medical DIM_HORSE: 키·값 그대로 (미상 행 HR_NM만 NULL → UNKNOWN, 팀 합의)")
    t_old = gold("horse_medical/DIM_TRAINER")
    mark(same_rows(d["DIM_TRAINER"][d["DIM_TRAINER"].TRAINER_KEY > 0], t_old), "horse_medical DIM_TRAINER: 18행 키·값 그대로")
    hm = gold("horse_medical/FCT_HORSE_MEDICAL")
    for c in ["VET_DT_KEY", "REPORT_DT_KEY"]:
        mark(bool(hm[c].isin(fdates).all()), f"horse_medical {c} 모두 DIM_DATE에 있음")


def before_race_sales(x):
    ch, fdates, race_nk, mbr = x["ch"], x["fdates"], x["race_nk"], x["mbr"]
    rs = gold("race_sales/FCT_RACE_SALES")
    mark(all(k in race_nk for k in zip(rs.RC_DT, rs.RC_NO)), "race_sales 경주(RC_DT, RC_NO) 모두 DIM_RACE에 있음")
    mark(bool(rs.DATE_KEY.astype(int).isin(fdates).all()), "race_sales DATE_KEY(숫자로 바꾸면) 모두 DIM_DATE에 있음")
    ch_nk = set(zip(ch.CHNL_CD, ch.OTB_BRANCH_NO.fillna("")))
    rs_ch = rs.CHANNEL_KEY.str.split("|", expand=True)
    mark(all(k in ch_nk for k in zip(rs_ch[0], rs_ch[1])), "race_sales 채널(CHNL_CD, OTB_BRANCH_NO) 모두 DIM_CHANNEL에 있음")
    mark(bool((rs.MEMBER_KEY.eq("NON_MEMBER") | rs.MEMBER_KEY.isin(mbr)).all()), "race_sales 회원 모두 DIM_MEMBER에 있음 (비회원 → NON_MEMBER)")
    print(f"    참고: race_sales 비회원 마권 {int(rs.MEMBER_KEY.eq('NON_MEMBER').sum()):,}행 (마권 기준)")


def before_bet_cancel(x):
    d, fdates, race_nk, mbr = x["d"], x["fdates"], x["race_nk"], x["mbr"]
    bc = gold("bet_cancel/FCT_BET_SELECTION_CANCEL_50S")
    for c in ["purchase_date_key", "cancel_date_key", "race_date_key", "snapshot_date_key"]:
        mark(bool(bc[c].isin(fdates).all()), f"bet_cancel {c} 모두 DIM_DATE에 있음 (미상 0 포함)")
    bm = gold("bet_cancel/DIM_MEMBER").set_index("member_key").member_no
    mark(bool(bc.member_key.map(bm).dropna().isin(mbr).all()), "bet_cancel 회원 모두 DIM_MEMBER에 있음")
    br = gold("bet_cancel/DIM_RACE").set_index("race_id")
    mark(all(k in race_nk for k in zip(bc.race_id.map(br.race_date).dropna(), bc.race_id.map(br.race_no).dropna().astype(int))),
         "bet_cancel 경주 모두 DIM_RACE에 있음")
    bh = gold("bet_cancel/DIM_HORSE").set_index("horse_key").horse_name
    mark(bool(bc.horse_key.map(bh).dropna().isin(set(d["DIM_HORSE"].HR_NM.dropna())).all()), "bet_cancel 말 이름 모두 DIM_HORSE에 있음")


# 전환 전 팩트별 검사. 모든 팩트가 전환되면 지워도 된다
BEFORE = {"race_entry": before_race_entry, "horse_medical": before_horse_medical,
          "race_sales": before_race_sales, "bet_cancel": before_bet_cancel}


def main():
    d = {n: pd.read_parquet(COMMON_DIR / f"{n}.parquet") for n in KEYS}
    cl = {t: pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet") for t in
          ["RC_RACE", "HR_VET_HIST", "HR_WEEKLY_SNAPSHOT", "TR_WEEKLY_SNAPSHOT", "BET_ORDER", "MBR_MASTER"]}

    print("[1] PK와 미상 행")
    for n, k in KEYS.items():
        t = d[n]
        mark(not t[k].duplicated().any() and t[k].notna().all(), f"{n}: PK {k} 중복·NULL 0")
        mark(int(t[k].eq(0).sum()) == 1 and t[k].iloc[0] == 0, f"{n}: 미상 행 {k}=0 1개")

    print("\n[2] 행 수 = clean 기준 (+ 특수 행)")
    o = cl["BET_ORDER"]
    exp = {
        "DIM_RACE": len(cl["RC_RACE"]) + 1,
        "DIM_TRAINER": cl["TR_WEEKLY_SNAPSHOT"]["TR_NM"].nunique() + 1,
        "DIM_MEMBER": len(cl["MBR_MASTER"]) + 2,  # + NON_MEMBER + UNKNOWN
        "DIM_CHANNEL": len(o.loc[o.CHNL_CD.ne("UNKNOWN"), ["CHNL_CD", "OTB_BRANCH_NO"]].drop_duplicates()) + 1,
    }
    for n, e in exp.items():
        mark(len(d[n]) == e, f"{n}: {len(d[n]):,}행 = 기대 {e:,}")
    m = d["DIM_MEMBER"]
    mark(set(m.loc[m.MEMBER_KEY > 0, "MBR_NO"].dropna()) == set(cl["MBR_MASTER"]["MBR_NO"]), "DIM_MEMBER: 회원 전원 포함")
    nm = m[m.MBR_TYPE_CD.eq("NON_MEMBER")]
    mark(len(nm) == 1 and nm.MEMBER_KEY.iloc[0] > 0, f"DIM_MEMBER: NON_MEMBER 1행, 양수 키 {nm.MEMBER_KEY.tolist()}")
    mark(int(o.MBR_NO.isna().sum()) == 4921, f"비회원 전표 {int(o.MBR_NO.isna().sum()):,}건 (전표 기준, 기대 4,921)")
    mark(int((~o.MBR_NO.dropna().isin(cl['MBR_MASTER'].MBR_NO)).sum()) == 0, "회원번호가 있는데 회원 마스터에 없는 전표 0건")
    ch = d["DIM_CHANNEL"]
    mark(int(ch.CHNL_CD.eq("OTB").sum()) == o.loc[o.CHNL_CD.eq("OTB"), "OTB_BRANCH_NO"].nunique(), f"DIM_CHANNEL: 장외 지점 {int(ch.CHNL_CD.eq('OTB').sum())}개 전부")

    print("\n[3] DIM_DATE")
    dd = d["DIM_DATE"][d["DIM_DATE"].DATE_KEY > 0]
    days = pd.to_datetime(dd.FULL_DT)
    mark(bool((days.diff().dropna() == pd.Timedelta(days=1)).all()), f"연속 {len(dd)}일")
    mark((days.min().date(), days.max().date()) == EXPECTED_DATE_RANGE,
         f"범위 {days.min().date()} ~ {days.max().date()} = 팀 합의 {EXPECTED_DATE_RANGE[0]} ~ {EXPECTED_DATE_RANGE[1]}")
    mark(bool((dd.DATE_KEY == days.dt.strftime("%Y%m%d").astype(int)).all()), "DATE_KEY = YYYYMMDD")
    used = {"경주일": cl["RC_RACE"].RC_DT, "진료일": cl["HR_VET_HIST"].VET_DT, "보고일": cl["HR_VET_HIST"].REPORT_DT,
            "스냅샷일": cl["HR_WEEKLY_SNAPSHOT"].SNAPSHOT_DT, "판매일": o.SALE_DTM.dt.date}
    for nm_, s in used.items():
        miss = (~s.dropna().isin(set(dd.FULL_DT))).sum()
        mark(miss == 0, f"{nm_} 모두 포함 (빠진 날짜 {miss})")
    race_days = set(cl["RC_RACE"].RC_DT)
    mark(bool((dd.RC_DAY_YN.eq("Y") == dd.FULL_DT.isin(race_days)).all()), f"RC_DAY_YN=Y {int(dd.RC_DAY_YN.eq('Y').sum())}일 = 경주일")

    print("\n[4] DIM_HORSE SCD2")
    h = d["DIM_HORSE"][d["DIM_HORSE"].HORSE_KEY > 0].sort_values(["HR_NM", "VALID_FROM_DT"])
    nxt = h.groupby("HR_NM").VALID_FROM_DT.shift(-1)
    mark(bool(((nxt.isna()) | (h.VALID_TO_DT == nxt.map(lambda x: x - timedelta(days=1) if pd.notna(x) else x))).all()),
         "말마다 기간이 겹치지 않고 빈틈 없이 이어짐")
    cur = h[h.CURRENT_YN.eq("Y")]
    mark(cur.HR_NM.is_unique and cur.HR_NM.nunique() == h.HR_NM.nunique() and bool(cur.VALID_TO_DT.eq(date(9999, 12, 31)).all()),
         f"말 {h.HR_NM.nunique():,}두 모두 현재 버전 1개")
    mark(bool((h.VALID_FROM_DT == h.SRC_SNAPSHOT_DT.map(lambda x: x + timedelta(days=1))).all()), "VALID_FROM_DT = 스냅샷 다음 날")

    print("\n[5] 팩트와 연결")
    print("    공통 차원으로 전환한 팩트는 FK가 모두 공통 차원에 있는지, 전환 전 팩트는 업무 키가 모두 공통 차원에서 찾아지는지 본다")
    ctx = {"d": d, "ch": ch, "m": m, "fdates": set(d["DIM_DATE"].DATE_KEY),
           "race_nk": set(zip(d["DIM_RACE"].RC_DT, d["DIM_RACE"].RC_NO)), "mbr": set(m.MBR_NO.dropna())}
    for folder in sorted(p for p in C.GOLD_DIR.iterdir() if p.is_dir() and p.name != "common"):
        own = [n for n in KEYS if (folder / f"{n}.parquet").exists()]
        if not own:
            check_converted(folder, d)
        elif folder.name in BEFORE:
            print(f"  - {folder.name}: 전환 전 (자기 차원 {len(own)}개)")
            BEFORE[folder.name](ctx)
        else:
            mark(False, f"{folder.name}: 전환 전 검사가 정의되지 않음")

    print("\n공통 차원 검증:", "통과" if not FAILS else f"불일치 {len(FAILS)}건")
    for f in FAILS:
        print("  -", f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
