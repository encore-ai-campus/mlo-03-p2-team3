"""Gold 팩트 4개 + 공통 차원 (+ 취소 피처용 clean) → AI Ready Data(04_ai_ready/): 출전마 3등 이내 예측

- 행 단위: 실제로 출주한 말 1두 (FCT_RACE_ENTRY 중 START_CNT = 1, 3,644행). 출주하지 않은 22행은 _excluded에 사유와 함께 보존
- 정답: PLACE_YN = 착순 3 이내면 1 (FCT_RACE_ENTRY.PLACE_CNT)
- 예측 시점: 경주 출발 시각(DIM_RACE.START_DTM). 그 이후에 생기거나 알 수 있는 정보는 피처에 넣지 않는다
- 분할: 경주일 < 2026-10-10 → TRAIN, 이후 → TEST (날짜 기준, 섞지 않음)

피처 출처 (팀 합의)
- 원주 race_entry: 말 버전(경주일 기준 SCD2) 나이·성별·등급, 조교사, 경주 조건, 출전 두수, 같은 말의 경주일 이전 성적
- 세은 horse_medical: 진료일과 보고일이 모두 경주일 이전인 진료만. 30일·90일 진료 횟수, 90일 파행 진료 여부.
  말은 HR_NM으로 연결 (HORSE_KEY는 버전마다 달라서). 말 키 0(이전 스냅샷 없음) 71건은 말을 특정할 수 없어 쓰지 않는다
- 희정 race_sales: SALE_DTM < START_DTM, INVALID_YN = 'N', SOLD·CANCEL만 경주별로 집계해 RACE_KEY로 연결
- 은빈 bet_cancel: 구매 당시 만 50~59세 회원의 단승 구매와 그 구매의 출발 전 취소를 경주 + 출전 번호별로 집계.
  Gold 취소 팩트는 출발 후 취소까지 합친 값이라 출발 전 취소만 보려고 clean 전표·마권(D-012 공용 입력)에서 계산한다

배당(EXPECT_WIN)은 피처가 아니라 비교 기준선이라 BASE_ 접두어로 따로 둔다 (최종 배당이라 관측 시각을 모름).
"""
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/config.py
import config as C  # noqa: E402

OUT_DIR = C.ROOT / "data" / "04_ai_ready"
COMMON = C.GOLD_DIR / "common"
SPLIT_DT = pd.Timestamp("2026-10-10")
LAMENESS = "파행"  # DIM_VET_TYPE 이름에 '파행'이 들어간 유형 (기타 파행, 좌전지파행 등)
CATEGORICAL = ["HR_SEX_CD", "HR_GRADE_CD", "TRAINER_KEY", "RC_GRADE_CD", "WEATHER_CD", "TRACK_STAT_CD"]

FEATURES = [
    # race_entry (원주)
    "HR_AGE", "HR_SEX_CD", "HR_GRADE_CD", "TRAINER_KEY", "RC_DIST_M", "RC_GRADE_CD", "WEATHER_CD", "TRACK_STAT_CD",
    "FIELD_CNT", "PRIOR_START_CNT", "PRIOR_WIN_CNT", "PRIOR_PLACE_CNT", "PRIOR_PLACE_RATE", "DAYS_SINCE_LAST_RACE",
    # horse_medical (세은)
    "VET_CNT_30D", "VET_CNT_90D", "LAMENESS_90D_YN",
    # race_sales (희정)
    "SALES_AMT", "SOLD_TICKET_CNT", "CANCEL_AMT", "CANCEL_RATE", "AVG_TICKET_AMT",
    # bet_cancel (은빈)
    "WIN_50S_PURCHASE_GROUP_CNT", "WIN_50S_CANCEL_GROUP_CNT", "WIN_50S_PURCHASE_AMT", "WIN_50S_CANCEL_AMT",
    "WIN_50S_CANCEL_AMT_RATE",
]
ID_COLS = ["RACE_KEY", "CHUL_NO", "DATE_KEY", "HORSE_KEY", "SPLIT_CD"]
LABEL = "PLACE_YN"
BASELINE = "BASE_EXPECT_WIN"


def gold(path):
    return pd.read_parquet(C.GOLD_DIR / path)


def clean(t):
    return pd.read_parquet(C.CLEAN_DIR / f"{t}.parquet")


def key_to_dt(s):
    return pd.to_datetime(s.astype(str), format="%Y%m%d")


def entry_base():
    """출전 팩트 + 경주·말 차원. 출주하지 않은 말은 따로 돌려준다."""
    f = gold("race_entry/FCT_RACE_ENTRY.parquet")
    race = pd.read_parquet(COMMON / "DIM_RACE.parquet")
    horse = pd.read_parquet(COMMON / "DIM_HORSE.parquet")
    f = f.merge(race[["RACE_KEY", "RC_DT", "START_DTM", "RC_DIST_M", "RC_GRADE_CD", "WEATHER_CD", "TRACK_STAT_CD"]],
                on="RACE_KEY", how="left", validate="m:1")
    f = f.merge(horse[["HORSE_KEY", "HR_NM", "HR_AGE", "HR_SEX_CD", "HR_GRADE_CD"]], on="HORSE_KEY", how="left", validate="m:1")
    f["RC_DT"] = pd.to_datetime(f["RC_DT"])
    f["FIELD_CNT"] = f.groupby("RACE_KEY")["CHUL_NO"].transform("size")  # 출전표 두수 (출발 전 공개)
    return f


def prior_form(f):
    """같은 말(HR_NM)의 이번 경주일 '이전' 경주 성적. 같은 날 경주는 넣지 않는다."""
    daily = (f.groupby(["HR_NM", "RC_DT"], as_index=False)[["START_CNT", "WIN_CNT", "PLACE_CNT"]].sum()
             .sort_values(["HR_NM", "RC_DT"]))
    g = daily.groupby("HR_NM")
    for c, out in [("START_CNT", "PRIOR_START_CNT"), ("WIN_CNT", "PRIOR_WIN_CNT"), ("PLACE_CNT", "PRIOR_PLACE_CNT")]:
        daily[out] = g[c].cumsum() - daily[c]
    ran_dt = daily["RC_DT"].where(daily["START_CNT"] > 0)
    daily["PREV_RAN_DT"] = ran_dt.groupby(daily["HR_NM"]).shift(1)
    daily["PREV_RAN_DT"] = daily.groupby("HR_NM")["PREV_RAN_DT"].ffill()  # 직전에 실제로 뛴 경주일
    daily["DAYS_SINCE_LAST_RACE"] = (daily["RC_DT"] - daily["PREV_RAN_DT"]).dt.days
    daily["PRIOR_PLACE_RATE"] = (daily["PRIOR_PLACE_CNT"] / daily["PRIOR_START_CNT"]).where(daily["PRIOR_START_CNT"] > 0)
    cols = ["PRIOR_START_CNT", "PRIOR_WIN_CNT", "PRIOR_PLACE_CNT", "PRIOR_PLACE_RATE", "DAYS_SINCE_LAST_RACE"]
    return daily[["HR_NM", "RC_DT"] + cols]


def medical(f):
    """진료일·보고일 모두 경주일 이전인 진료. 진료 횟수는 브리지 조인 전 팩트에서 센다."""
    m = gold("horse_medical/FCT_HORSE_MEDICAL.parquet")
    horse = pd.read_parquet(COMMON / "DIM_HORSE.parquet")
    m = m[m["HORSE_KEY"] != 0].merge(horse[["HORSE_KEY", "HR_NM"]], on="HORSE_KEY", validate="m:1")
    m["VET_DT"], m["REPORT_DT"] = key_to_dt(m["VET_DT_KEY"]), key_to_dt(m["REPORT_DT_KEY"])
    br = gold("horse_medical/BRIDGE_HR_VET_TYPE.parquet").merge(gold("horse_medical/DIM_VET_TYPE.parquet"), on="VET_TYPE_KEY")
    lame = set(br.loc[br["VET_TYPE_NM"].str.contains(LAMENESS), "VET_SEQ"])
    m["LAME"] = m["VET_SEQ"].isin(lame)

    e = f[["RACE_KEY", "CHUL_NO", "HR_NM", "RC_DT"]].drop_duplicates()
    j = e.merge(m[["HR_NM", "VET_DT", "REPORT_DT", "VET_CNT", "LAME"]], on="HR_NM")
    j = j[(j["VET_DT"] < j["RC_DT"]) & (j["REPORT_DT"] < j["RC_DT"])]
    days = (j["RC_DT"] - j["VET_DT"]).dt.days
    j = j.assign(V30=j["VET_CNT"].where(days <= 30, 0), V90=j["VET_CNT"].where(days <= 90, 0), L90=(j["LAME"] & (days <= 90)))
    a = j.groupby(["RACE_KEY", "CHUL_NO"]).agg(VET_CNT_30D=("V30", "sum"), VET_CNT_90D=("V90", "sum"), L=("L90", "any")).reset_index()
    a["LAMENESS_90D_YN"] = a.pop("L").map({True: "Y", False: "N"})
    return a


def sales():
    """희정 정의: 출발 전, 0원 제외, SOLD·CANCEL만 경주별 집계."""
    s = gold("race_sales/race_sales.parquet")[["RACE_KEY", "SALE_DTM", "INVALID_YN", "TICKET_STAT_CD", "BET_AMT"]]
    race = pd.read_parquet(COMMON / "DIM_RACE.parquet")[["RACE_KEY", "START_DTM"]]
    s = s.merge(race, on="RACE_KEY", validate="m:1")
    s = s[(s["SALE_DTM"] < s["START_DTM"]) & s["INVALID_YN"].eq("N") & s["TICKET_STAT_CD"].isin(["SOLD", "CANCEL"])]
    sold, canc = s["TICKET_STAT_CD"].eq("SOLD"), s["TICKET_STAT_CD"].eq("CANCEL")
    s = s.assign(SA=s["BET_AMT"].where(sold, 0).astype("int64"), SC=sold.astype(int), CA=(-s["BET_AMT"]).where(canc, 0).astype("int64"))
    a = s.groupby("RACE_KEY").agg(SALES_AMT=("SA", "sum"), SOLD_TICKET_CNT=("SC", "sum"), CANCEL_AMT=("CA", "sum")).reset_index()
    a = race[["RACE_KEY"]].merge(a, on="RACE_KEY", how="left")
    a[["SALES_AMT", "SOLD_TICKET_CNT", "CANCEL_AMT"]] = a[["SALES_AMT", "SOLD_TICKET_CNT", "CANCEL_AMT"]].fillna(0).astype("int64")
    a["CANCEL_RATE"] = a["CANCEL_AMT"] / a["SALES_AMT"].where(a["SALES_AMT"] > 0)
    a["AVG_TICKET_AMT"] = a["SALES_AMT"] / a["SOLD_TICKET_CNT"].where(a["SOLD_TICKET_CNT"] > 0)
    return a


def full_age(birth, at):
    b, d = pd.to_datetime(birth), at.dt.normalize()
    return d.dt.year - b.dt.year - ((d.dt.month < b.dt.month) | ((d.dt.month == b.dt.month) & (d.dt.day < b.dt.day))).astype(int)


def cancel_50s():
    """은빈 정의: 구매 당시 만 50~59세의 단승 구매, 그 구매를 가리키는 출발 전 취소. 0원·VOID 제외."""
    t, o, mb, rc = clean("BET_TICKET"), clean("BET_ORDER"), clean("MBR_MASTER"), clean("RC_RACE")
    x = t.merge(o[["ORDER_NO", "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM"]], on="ORDER_NO", validate="m:1")
    x = x.merge(rc[["RC_DT", "RC_NO", "START_DTM"]], on=["RC_DT", "RC_NO"], validate="m:1")
    x = x[x["INVALID_YN"].eq("N") & x["TICKET_STAT_CD"].ne("VOID") & x["MBR_NO"].notna()]

    p = x[x["ORDER_TYPE_CD"].eq("SALE") & x["BET_TYPE_CD"].eq("WIN") & (x["SALE_DTM"] < x["START_DTM"])]
    p = p.merge(mb[["MBR_NO", "BIRTH_DT"]], on="MBR_NO", validate="m:1")
    p = p[full_age(p["BIRTH_DT"], p["SALE_DTM"]).between(50, 59)]

    k = ["RC_DT", "RC_NO", "CHUL_NO"]
    grp = ["ORDER_NO"] + k  # 구매 묶음 = 원전표 + 경주 + 출전 번호
    pg = p.groupby(grp + ["MBR_NO"], as_index=False).agg(P_DTM=("SALE_DTM", "min"), P_AMT=("BET_AMT", "sum"))

    # 출발 전 단승 취소만 본다 (같은 전표의 연승·복승 취소가 섞이지 않게 단승만)
    c = x[x["ORDER_TYPE_CD"].eq("CANCEL") & x["BET_TYPE_CD"].eq("WIN") & (x["SALE_DTM"] < x["START_DTM"])]
    # 원구매에 연결되는 취소: 원전표가 같은 회원의 '출발 전' SALE 전표이고 같은 말에 단승 마권이 있음.
    # 출발 후 판매는 예측 시점에 없던 거래라 연결 후보에서 뺀다 (출발 후 거래가 출발 전 판정을 바꾸지 않게)
    sale_win = t.merge(o[["ORDER_NO", "ORDER_TYPE_CD", "MBR_NO", "SALE_DTM"]], on="ORDER_NO", validate="m:1")
    sale_win = sale_win.merge(rc[["RC_DT", "RC_NO", "START_DTM"]], on=["RC_DT", "RC_NO"], validate="m:1")
    sale_win = sale_win[sale_win["ORDER_TYPE_CD"].eq("SALE") & sale_win["BET_TYPE_CD"].eq("WIN")
                        & (sale_win["SALE_DTM"] < sale_win["START_DTM"])][["ORDER_NO", "MBR_NO"] + k].drop_duplicates()
    c = c.merge(sale_win.rename(columns={"ORDER_NO": "ORIG_ORDER_NO"}).assign(LINKABLE=True), on=["ORIG_ORDER_NO", "MBR_NO"] + k, how="left")
    c["LINKABLE"] = c["LINKABLE"].fillna(False).astype(bool)
    linked = c[c["LINKABLE"]].merge(pg.rename(columns={"ORDER_NO": "ORIG_ORDER_NO"}), on=["ORIG_ORDER_NO", "MBR_NO"] + k)

    # 출발 전 거래만으로 다시 판정 (은빈 님 Gold의 판정 기준을 출발 전 거래에 적용)
    bad = set()
    over = linked.assign(A=linked["BET_AMT"].abs()).groupby(["ORIG_ORDER_NO"] + k).agg(A=("A", "sum"), P=("P_AMT", "first"))
    bad |= set(over.index[over["A"] > over["P"]])  # 출발 전 취소액 > 구매액
    bad |= set(map(tuple, linked.loc[linked["SALE_DTM"] < linked["P_DTM"], ["ORIG_ORDER_NO"] + k].values))  # 구매보다 이른 취소
    # 같은 회원·말인데 원구매에 연결되지 않는 출발 전 취소가 그 구매 뒤에 있으면, 어느 구매의 취소인지 불확실
    loose = c[~c["LINKABLE"]].merge(pg.rename(columns={"ORDER_NO": "P_ORDER_NO"}), on=["MBR_NO"] + k)
    bad |= set(map(tuple, loose.loc[loose["SALE_DTM"] >= loose["P_DTM"], ["P_ORDER_NO"] + k].values))
    c = linked[~pd.Series(list(map(tuple, linked[["ORIG_ORDER_NO"] + k].values)), index=linked.index).isin(bad)]

    pa_ = p.groupby(k).agg(WIN_50S_PURCHASE_GROUP_CNT=("ORDER_NO", "nunique"), WIN_50S_PURCHASE_AMT=("BET_AMT", "sum"))
    ca_ = c.assign(A=c["BET_AMT"].abs()).groupby(k).agg(WIN_50S_CANCEL_GROUP_CNT=("ORIG_ORDER_NO", "nunique"), WIN_50S_CANCEL_AMT=("A", "sum"))
    a = pa_.join(ca_, how="outer").reset_index()
    a["RC_DT"] = pd.to_datetime(a["RC_DT"])
    return a


def build():
    f = entry_base()
    excluded = f[f["START_CNT"] == 0][["RACE_KEY", "CHUL_NO", "DATE_KEY", "HORSE_KEY"]].assign(
        EXCLUDE_REASON="NOT_STARTED", EXCLUDE_NOTE="경주제외(94)·출주취소(95): 뛰지 않아 3등 이내 정답이 없음")

    x = f.merge(prior_form(f), on=["HR_NM", "RC_DT"], how="left", validate="m:1")
    x = x[x["START_CNT"] == 1]
    x = x.merge(medical(f), on=["RACE_KEY", "CHUL_NO"], how="left", validate="1:1")
    x[["VET_CNT_30D", "VET_CNT_90D"]] = x[["VET_CNT_30D", "VET_CNT_90D"]].fillna(0)
    x["LAMENESS_90D_YN"] = x["LAMENESS_90D_YN"].fillna("N")
    x = x.merge(sales(), on="RACE_KEY", how="left", validate="m:1")
    x = x.merge(cancel_by_race_key(), on=["RACE_KEY", "CHUL_NO"], how="left", validate="1:1")
    cnt = ["WIN_50S_PURCHASE_GROUP_CNT", "WIN_50S_CANCEL_GROUP_CNT", "WIN_50S_PURCHASE_AMT", "WIN_50S_CANCEL_AMT"]
    x[cnt] = x[cnt].fillna(0)
    x["WIN_50S_CANCEL_AMT_RATE"] = x["WIN_50S_CANCEL_AMT"] / x["WIN_50S_PURCHASE_AMT"].where(x["WIN_50S_PURCHASE_AMT"] > 0)

    x[LABEL] = x["PLACE_CNT"]
    x[BASELINE] = x["EXPECT_WIN"]
    x["SPLIT_CD"] = (x["RC_DT"] < SPLIT_DT).map({True: "TRAIN", False: "TEST"})
    x = x.sort_values(["RACE_KEY", "CHUL_NO"], kind="stable").reset_index(drop=True)
    return x[ID_COLS + [LABEL, BASELINE] + FEATURES], excluded.sort_values(["RACE_KEY", "CHUL_NO"]).reset_index(drop=True)


def cancel_by_race_key():
    """은빈 피처를 공통 DIM_RACE의 RACE_KEY로 바꿔 경주 + 출전 번호로 붙일 수 있게 한다."""
    race = pd.read_parquet(COMMON / "DIM_RACE.parquet")[["RACE_KEY", "RC_DT", "RC_NO"]]
    race["RC_DT"], race["RC_NO"] = pd.to_datetime(race["RC_DT"]), race["RC_NO"].astype("Int64")
    a = cancel_50s()
    a["RC_NO"] = a["RC_NO"].astype("Int64")
    a = a.merge(race, on=["RC_DT", "RC_NO"], validate="m:1")
    return a.drop(columns=["RC_DT", "RC_NO"])


def encode(t):
    """모델 입력용: 범주형은 원-핫(0/1), Y/N은 1/0, 비율·간격의 NULL은 0 + 결측 표시 컬럼."""
    e = t.copy()
    e["LAMENESS_90D_YN"] = e["LAMENESS_90D_YN"].eq("Y").astype("int8")
    for c in ["PRIOR_PLACE_RATE", "DAYS_SINCE_LAST_RACE", "CANCEL_RATE", "AVG_TICKET_AMT", "WIN_50S_CANCEL_AMT_RATE"]:
        e[c + "_NA"] = e[c].isna().astype("int8")
        e[c] = e[c].fillna(0)
    for c in CATEGORICAL:
        vals = sorted(e[c].astype(str).unique())  # 전체 기간 값 목록을 고정 순서로 (값 자체는 출발 전 공개 정보)
        for v in vals:
            e[f"{c}__{v}"] = e[c].astype(str).eq(v).astype("int8")
        e = e.drop(columns=c)
    return e


def write(df, path):
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table, excluded = build()
    write(table, OUT_DIR / "AI_READY_RACE_ENTRY.parquet")
    write(encode(table), OUT_DIR / "AI_READY_RACE_ENTRY_ENCODED.parquet")
    (OUT_DIR / "_excluded").mkdir(exist_ok=True)
    write(excluded, OUT_DIR / "_excluded" / "AI_READY_RACE_ENTRY.parquet")
    n = table["SPLIT_CD"].value_counts()
    print(f"AI_READY_RACE_ENTRY  {len(table):,}행 (TRAIN {n.get('TRAIN', 0):,} / TEST {n.get('TEST', 0):,}), 제외 {len(excluded)}행")


if __name__ == "__main__":
    main()
