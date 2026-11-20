"""Build the race sales star schema from quality-managed Silver Parquet files.

Run from any directory: python src/build_gold_sales.py
Only data/03_gold is written. No Silver row is discarded by this step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data" / "02_silver" / "clean"
GOLD = ROOT / "data" / "03_gold"

BET_TYPES = {
    "WIN": "단승", "PLC": "연승", "QNL": "복승", "QPL": "복연승",
    "EXA": "쌍승", "TRI": "삼복승", "TLA": "삼쌍승",
}
POOL_NAMES = {
    "WIN": "단식", "PLC": "연식", "QNL": "복식", "QPL": "복연",
    "EXA": "쌍식", "TRI": "삼복", "TLA": "삼쌍",
}
WEATHER_NAMES = {
    "CLEAR": "맑음", "CLOUDY": "흐림", "RAIN": "비", "FOG": "안개",
}
WEEKDAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")
TICKET_STATUSES = {"SOLD": "정상 발매", "CANCEL": "발매 취소", "VOID": "무효"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_key(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    require(not frame[columns].isna().any().any(), f"{name}: null PK {columns}")
    require(not frame.duplicated(columns).any(), f"{name}: duplicate PK {columns}")


def race_key(frame: pd.DataFrame) -> pd.Series:
    require(not frame[["RC_DT", "RC_NO"]].isna().any().any(), "null race key")
    return frame["RC_DT"].astype(str) + "|" + frame["RC_NO"].astype(str)


def channel_key(frame: pd.DataFrame) -> pd.Series:
    require(not frame["CHNL_CD"].isna().any(), "null channel code")
    return frame["CHNL_CD"].astype(str) + "|" + frame["OTB_BRANCH_NO"].fillna("").astype(str)


def date_key(frame: pd.DataFrame) -> pd.Series:
    require(not frame["RC_DT"].isna().any(), "null race date")
    return pd.to_datetime(frame["RC_DT"].astype(str)).dt.strftime("%Y%m%d")


def build(silver: Path = SILVER, gold: Path = GOLD) -> dict:
    ticket = pd.read_parquet(silver / "BET_TICKET.parquet")
    order = pd.read_parquet(silver / "BET_ORDER.parquet")
    race = pd.read_parquet(silver / "RC_RACE.parquet")
    sales = pd.read_parquet(silver / "RC_SALES.parquet")
    sales_total = pd.read_parquet(silver / "RC_SALES_TOTAL.parquet")
    member = pd.read_parquet(silver / "MBR_MASTER.parquet")

    unique_key(ticket, ["ORDER_NO", "TICKET_SEQ"], "BET_TICKET")
    unique_key(order, ["ORDER_NO"], "BET_ORDER")
    unique_key(race, ["RC_DT", "RC_NO"], "RC_RACE")
    unique_key(sales, ["RC_DT", "RC_NO", "BET_TYPE_CD"], "RC_SALES")
    unique_key(sales_total, ["RC_DT", "RC_NO"], "RC_SALES_TOTAL")
    unique_key(member, ["MBR_NO"], "MBR_MASTER")
    require(not ticket["BET_AMT"].isna().any(), "BET_TICKET: null BET_AMT")
    require(not sales["SALES_AMT"].isna().any(), "RC_SALES: null SALES_AMT")
    require(ticket["TICKET_STAT_CD"].isin(["SOLD", "CANCEL", "VOID"]).all(),
            "BET_TICKET: unknown ticket status")
    require(ticket["SALES_AGG_INCLUDE_YN"].isin(["Y", "N"]).all(),
            "BET_TICKET: unknown sales inclusion flag")
    require(ticket.loc[ticket.TICKET_STAT_CD.eq("SOLD"), "BET_AMT"].ge(0).all(),
            "SOLD amount must be nonnegative")
    require(ticket.loc[ticket.TICKET_STAT_CD.eq("CANCEL"), "BET_AMT"].le(0).all(),
            "CANCEL amount must be nonpositive")
    require(ticket.loc[ticket.TICKET_STAT_CD.eq("VOID"), "BET_AMT"].ge(0).all(),
            "VOID amount must be nonnegative")

    dim_race = race[[
        "RC_DT", "RC_NO", "MEET_CD", "RC_DAY_SEQ", "RC_DIST_M",
        "RC_GRADE_CD", "BUDAM_TYPE_CD", "HR_CLASS_NM", "RC_TITLE_NM",
        "WEATHER_CD", "TRACK_STAT_CD", "TRACK_MOIST_RT", "START_DTM",
    ]].copy()
    dim_race.insert(0, "RACE_KEY", race_key(dim_race))
    dim_race["RC_DIST_NM"] = dim_race["RC_DIST_M"].astype("string") + "m"
    dim_race["WEATHER_NM"] = dim_race["WEATHER_CD"].map(WEATHER_NAMES)
    require(not dim_race["WEATHER_NM"].isna().any(), "unknown race weather code")
    dim_race = dim_race.sort_values(["RC_DT", "RC_NO"], kind="stable").reset_index(drop=True)

    dim_date = race[["RC_DT"]].drop_duplicates().copy()
    dim_date.insert(0, "DATE_KEY", date_key(dim_date))
    dates = pd.to_datetime(dim_date["RC_DT"].astype(str))
    dim_date["YEAR_NO"] = dates.dt.year
    dim_date["MONTH_NO"] = dates.dt.month
    dim_date["DAY_NO"] = dates.dt.day
    dim_date["WEEKDAY_NO"] = dates.dt.day_of_week + 1  # ISO Monday=1
    dim_date["WEEKDAY_NM"] = dates.dt.day_of_week.map(dict(enumerate(WEEKDAY_NAMES)))
    dim_date = dim_date.sort_values("DATE_KEY", kind="stable").reset_index(drop=True)

    pool_codes = sorted(sales["BET_TYPE_CD"].dropna().unique().tolist())
    require(set(pool_codes) == set(POOL_NAMES), "RC_SALES: unexpected pool codes")
    dim_pool = pd.DataFrame(
        [(code, POOL_NAMES[code]) for code in pool_codes],
        columns=["POOL_CD", "POOL_NM"],
    )

    bet_codes = sorted(ticket["BET_TYPE_CD"].dropna().unique().tolist())
    require(set(bet_codes).issubset(BET_TYPES), "BET_TICKET: unexpected bet type codes")
    dim_bet_type = pd.DataFrame(
        [(code, BET_TYPES[code]) for code in bet_codes],
        columns=["BET_TYPE_CD", "BET_TYPE_NM"],
    )
    dim_channel = order[["CHNL_CD", "OTB_BRANCH_NO"]].drop_duplicates().copy()
    dim_channel.insert(0, "CHANNEL_KEY", channel_key(dim_channel))
    dim_channel["CHNL_NM"] = dim_channel["CHNL_CD"].map(
        {"ONSITE": "현장", "APP": "온라인", "OTB": "장외발매소", "UNKNOWN": "미상"}
    )
    require(not dim_channel["CHNL_NM"].isna().any(), "unknown channel code")
    dim_channel = dim_channel.sort_values("CHANNEL_KEY", kind="stable").reset_index(drop=True)
    dim_ticket_status = pd.DataFrame(
        list(TICKET_STATUSES.items()), columns=["TICKET_STAT_CD", "TICKET_STAT_NM"]
    ).sort_values("TICKET_STAT_CD", kind="stable").reset_index(drop=True)
    require(not member["MBR_NO"].eq("NON_MEMBER").any(), "reserved member key exists")
    dim_member = member[[
        "MBR_NO", "BIRTH_DT", "JOIN_DT", "MBR_GRADE_CD", "MBR_STAT_CD",
        "REGION_CD",
    ]].copy().rename(columns={"MBR_NO": "MEMBER_KEY"})
    non_member = pd.DataFrame({
        "MEMBER_KEY": ["NON_MEMBER"], "BIRTH_DT": [pd.NaT], "JOIN_DT": [pd.NaT],
        "MBR_GRADE_CD": [pd.NA], "MBR_STAT_CD": [pd.NA], "REGION_CD": [pd.NA],
    })
    dim_member = pd.concat([dim_member, non_member], ignore_index=True)
    dim_member = dim_member.sort_values("MEMBER_KEY", kind="stable").reset_index(drop=True)
    require(len(dim_member) == len(member) + 1, "member dimension row reconciliation failed")

    # A ticket retains its natural PK. ORDER_NO and TICKET_SEQ are degenerate
    # identifiers; dimension codes are foreign keys.
    order_fields = [
        "ORDER_NO", "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM",
        "BIZ_DT", "CHNL_CD", "OTB_BRANCH_NO", "HEADER_MISMATCH_YN",
        "ORIG_MISSING_YN",
    ]
    fact_ticket = ticket.merge(
        order[order_fields], on="ORDER_NO", how="left", validate="many_to_one",
        indicator=True,
    )
    require(fact_ticket["_merge"].eq("both").all(), "BET_TICKET: missing BET_ORDER")
    fact_ticket = fact_ticket.drop(columns="_merge")
    require(len(fact_ticket) == len(ticket), "ticket join changed row count")
    fact_ticket.insert(2, "RACE_KEY", race_key(fact_ticket))
    fact_ticket.insert(3, "DATE_KEY", date_key(fact_ticket))
    fact_ticket.insert(4, "CHANNEL_KEY", channel_key(fact_ticket))
    fact_ticket.insert(5, "MEMBER_KEY", fact_ticket["MBR_NO"].fillna("NON_MEMBER"))

    amt = fact_ticket["BET_AMT"].astype("int64")
    included = fact_ticket["SALES_AGG_INCLUDE_YN"].eq("Y")
    sold = fact_ticket["TICKET_STAT_CD"].eq("SOLD") & included
    cancel = fact_ticket["TICKET_STAT_CD"].eq("CANCEL") & included
    void = fact_ticket["TICKET_STAT_CD"].eq("VOID") & included
    fact_ticket["VIRTUAL_GROSS_SALES_AMT"] = amt.where(sold, 0)
    fact_ticket["CANCEL_AMT"] = (-amt).where(cancel, 0)
    fact_ticket["VOID_AMT"] = amt.where(void, 0)
    fact_ticket["NET_AFTER_CANCEL_AMT"] = (
        fact_ticket["VIRTUAL_GROSS_SALES_AMT"] - fact_ticket["CANCEL_AMT"]
    )
    fact_ticket = fact_ticket[[
        "ORDER_NO", "TICKET_SEQ", "RACE_KEY", "DATE_KEY", "BET_TYPE_CD",
        "CHANNEL_KEY", "MEMBER_KEY",
        "RC_DT", "RC_NO",
        "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM", "BIZ_DT",
        "TICKET_STAT_CD", "BET_AMT", "UNIT_CNT",
        "VIRTUAL_GROSS_SALES_AMT", "CANCEL_AMT", "VOID_AMT",
        "NET_AFTER_CANCEL_AMT", "SALES_AGG_INCLUDE_YN", "INVALID_YN",
        "LATE_CANCEL_YN", "ZERO_LATE_CANCEL_YN", "HEADER_MISMATCH_YN",
        "ORIG_MISSING_YN", "_SRC_ROW_NO", "BRONZE_PATH", "DQ_DECISION_ID",
    ]].sort_values(["ORDER_NO", "TICKET_SEQ"], kind="stable").reset_index(drop=True)

    fact_actual = sales[[
        "RC_DT", "RC_NO", "BET_TYPE_CD", "SALES_AMT", "_SRC_ROW_NO",
        "BRONZE_PATH", "DQ_DECISION_ID",
    ]].copy()
    fact_actual.insert(0, "RACE_KEY", race_key(fact_actual))
    fact_actual.insert(1, "DATE_KEY", date_key(fact_actual))
    fact_actual = fact_actual.rename(columns={
        "BET_TYPE_CD": "POOL_CD", "SALES_AMT": "ACTUAL_SALES_AMT",
    })
    fact_actual = fact_actual.sort_values(
        ["RC_DT", "RC_NO", "POOL_CD"], kind="stable"
    ).reset_index(drop=True)

    tables = {
        "DIM_RACE": (dim_race, ["RACE_KEY"]),
        "DIM_DATE": (dim_date, ["DATE_KEY"]),
        "DIM_POOL": (dim_pool, ["POOL_CD"]),
        "DIM_BET_TYPE": (dim_bet_type, ["BET_TYPE_CD"]),
        "DIM_CHANNEL": (dim_channel, ["CHANNEL_KEY"]),
        "DIM_MEMBER": (dim_member, ["MEMBER_KEY"]),
        "DIM_TICKET_STATUS": (dim_ticket_status, ["TICKET_STAT_CD"]),
        "FACT_BET_TICKET": (fact_ticket, ["ORDER_NO", "TICKET_SEQ"]),
        "FACT_ACTUAL_RACE_SALES": (fact_actual, ["RACE_KEY", "POOL_CD"]),
    }
    for name, (frame, pk) in tables.items():
        unique_key(frame, pk, name)
    for name, frame in [("FACT_BET_TICKET", fact_ticket),
                        ("FACT_ACTUAL_RACE_SALES", fact_actual)]:
        require(frame["RACE_KEY"].isin(dim_race["RACE_KEY"]).all(),
                f"{name}: missing DIM_RACE FK")
        require(frame["DATE_KEY"].isin(dim_date["DATE_KEY"]).all(),
                f"{name}: missing DIM_DATE FK")
        require(frame[["DATE_KEY", "RACE_KEY"]].merge(
            dim_race[["RACE_KEY", "RC_DT"]].assign(DATE_KEY=date_key(dim_race))[
                ["DATE_KEY", "RACE_KEY"]
            ], on=["DATE_KEY", "RACE_KEY"], how="left", indicator=True
        )["_merge"].eq("both").all(), f"{name}: race/date mismatch")
    require(fact_actual["POOL_CD"].isin(dim_pool["POOL_CD"]).all(),
            "FACT_ACTUAL_RACE_SALES: missing DIM_POOL FK")
    require(fact_actual.groupby("RACE_KEY")["POOL_CD"].nunique().eq(len(dim_pool)).all(),
            "FACT_ACTUAL_RACE_SALES: a race is missing a pool")
    require(fact_ticket["BET_TYPE_CD"].isin(dim_bet_type["BET_TYPE_CD"]).all(),
            "FACT_BET_TICKET: missing DIM_BET_TYPE FK")
    require(fact_ticket["CHANNEL_KEY"].isin(dim_channel["CHANNEL_KEY"]).all(),
            "FACT_BET_TICKET: missing DIM_CHANNEL FK")
    require(fact_ticket["MEMBER_KEY"].isin(dim_member["MEMBER_KEY"]).all(),
            "FACT_BET_TICKET: missing DIM_MEMBER FK")
    require(int(fact_ticket["MEMBER_KEY"].eq("NON_MEMBER").sum()) ==
            int(fact_ticket["MBR_NO"].isna().sum()),
            "non-member ticket reconciliation failed")
    require(fact_ticket["TICKET_STAT_CD"].isin(dim_ticket_status["TICKET_STAT_CD"]).all(),
            "FACT_BET_TICKET: missing DIM_TICKET_STATUS FK")

    # RC_SALES_TOTAL is an independent race-level control total, not a fact.
    race_sum = fact_actual.groupby("RACE_KEY", as_index=False)["ACTUAL_SALES_AMT"].sum()
    control = sales_total[["RC_DT", "RC_NO", "SALES_AMT"]].copy()
    control.insert(0, "RACE_KEY", race_key(control))
    comparison = control.merge(race_sum, on="RACE_KEY", how="outer", indicator=True)
    require(comparison["_merge"].eq("both").all(), "RC_SALES_TOTAL race coverage mismatch")
    require(comparison["SALES_AMT"].eq(comparison["ACTUAL_SALES_AMT"]).all(),
            "RC_SALES_TOTAL does not equal sum of seven pools")

    require(len(fact_actual) == len(sales), "actual sales row reconciliation failed")
    require(int(fact_actual.ACTUAL_SALES_AMT.sum()) == int(sales.SALES_AMT.sum()),
            "actual sales amount reconciliation failed")
    require(len(fact_ticket) == len(ticket), "ticket row reconciliation failed")
    for status, column, sign in [
        ("SOLD", "VIRTUAL_GROSS_SALES_AMT", 1),
        ("CANCEL", "CANCEL_AMT", -1),
        ("VOID", "VOID_AMT", 1),
    ]:
        source = ticket.loc[
            ticket.TICKET_STAT_CD.eq(status) & ticket.SALES_AGG_INCLUDE_YN.eq("Y"),
            "BET_AMT",
        ].sum()
        require(int(fact_ticket[column].sum()) == sign * int(source),
                f"{status} amount reconciliation failed")

    report = {
        "source_rows": {"BET_TICKET": len(ticket), "BET_ORDER": len(order),
                        "MBR_MASTER": len(member),
                        "RC_RACE": len(race), "RC_SALES": len(sales),
                        "RC_SALES_TOTAL": len(sales_total)},
        "gold_rows": {name: len(frame) for name, (frame, _) in tables.items()},
        "gold_excluded_rows": {"BET_TICKET": 0, "RC_SALES": 0},
        "ticket_measures_krw": {
            column: int(fact_ticket[column].sum()) for column in [
                "VIRTUAL_GROSS_SALES_AMT", "CANCEL_AMT", "VOID_AMT",
                "NET_AFTER_CANCEL_AMT",
            ]
        },
        "actual_sales_krw": int(fact_actual.ACTUAL_SALES_AMT.sum()),
        "actual_race_control_count": len(comparison),
        "pk_duplicate_count": {name: 0 for name in tables},
        "missing_dimension_fk_count": {
            "FACT_BET_TICKET": {"DIM_RACE": 0, "DIM_DATE": 0,
                                "DIM_BET_TYPE": 0, "DIM_CHANNEL": 0,
                                "DIM_MEMBER": 0, "DIM_TICKET_STATUS": 0},
            "FACT_ACTUAL_RACE_SALES": {"DIM_RACE": 0, "DIM_DATE": 0,
                                       "DIM_POOL": 0},
        },
    }
    gold.mkdir(parents=True, exist_ok=True)
    for name, (frame, _) in tables.items():
        frame.to_parquet(gold / f"{name}.parquet", index=False)
    (gold / "_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver", type=Path, default=SILVER)
    parser.add_argument("--gold", type=Path, default=GOLD)
    args = parser.parse_args()
    print(json.dumps(build(args.silver, args.gold), ensure_ascii=False, indent=2))
