"""Build the ticket sales star schema from the shared quality-managed clean data.

Run: python src/race_sales/build_gold_sales.py --silver-ref origin/develop
Output: data/03_gold/race_sales. No Silver file or ticket row is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SILVER = ROOT / "data" / "02_silver" / "clean"
GOLD = ROOT / "data" / "03_gold" / "race_sales"
SOURCE_TABLES = ("BET_TICKET", "BET_ORDER", "RC_RACE", "MBR_MASTER")
FACT_NAME = "race_sales"

BET_TYPES = {
    "WIN": "단승", "PLC": "연승", "QNL": "복승", "QPL": "복연승",
    "EXA": "쌍승", "TRI": "삼복승", "TLA": "삼쌍승",
}
WEATHER_NAMES = {
    "CLEAR": "맑음", "CLOUDY": "흐림", "RAIN": "비", "FOG": "안개",
}
WEEKDAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")
TICKET_STATUSES = {"SOLD": "정상 발매", "CANCEL": "발매 취소", "VOID": "무효"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_sources(silver: Path, silver_ref: str | None) -> tuple[dict, dict]:
    """Read immutable input bytes and verify the shared clean manifest (D-012)."""
    commit = None
    if silver_ref is not None:
        commit = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", f"{silver_ref}^{{commit}}"],
            text=True,
        ).strip()

    def read_file(name: str) -> bytes:
        if commit is not None:
            return subprocess.check_output([
                "git", "-C", str(ROOT), "show",
                f"{commit}:data/02_silver/clean/{name}",
            ])
        return (silver / name).read_bytes()

    manifest = json.loads(read_file("_manifest.json"))
    require(bool(manifest.get("SOURCE_COMMIT")), "clean manifest: missing SOURCE_COMMIT")
    require(bool(manifest.get("CLEAN_VERSION")), "clean manifest: missing CLEAN_VERSION")
    frames, hashes = {}, {}
    for name in SOURCE_TABLES:
        filename = f"{name}.parquet"
        payload = read_file(filename)
        digest = hashlib.sha256(payload).hexdigest()
        require(digest == manifest.get("CLEAN_SHA256", {}).get(filename),
                f"{filename}: hash differs from shared clean manifest (D-012)")
        frames[name] = pd.read_parquet(io.BytesIO(payload))
        hashes[filename] = digest
    # Keep provenance independent of the Git ref used to read the same clean data.
    return frames, {
        "input_path": "data/02_silver/clean/",
        "manifest_source_commit": manifest["SOURCE_COMMIT"],
        "clean_version": manifest["CLEAN_VERSION"],
        "input_file_sha256": hashes,
    }


def check_output_path(silver: Path, gold: Path) -> None:
    """Reject output paths that overlap an earlier stage or the input directory."""
    output = gold.resolve()
    protected = [ROOT / "data" / stage for stage in ("00_origin", "01_bronze", "02_silver")]
    for directory in [*protected, silver]:
        directory = directory.resolve()
        require(not output.is_relative_to(directory) and not directory.is_relative_to(output),
                f"Gold output overlaps protected input: {directory}")


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


def seoul_timestamp(values: pd.Series, name: str) -> pd.Series:
    """Interpret shared naive timestamps in Korea time, as defined by MR-5."""
    values = pd.to_datetime(values)
    require(not values.isna().any(), f"{name}: null timestamp")
    if values.dt.tz is None:
        return values.dt.tz_localize("Asia/Seoul")
    return values.dt.tz_convert("Asia/Seoul")


def build(silver: Path = SILVER, gold: Path = GOLD, silver_ref: str | None = None) -> dict:
    check_output_path(silver, gold)
    sources, provenance = read_sources(silver, silver_ref)
    ticket, order, race, member = (sources[name] for name in SOURCE_TABLES)

    unique_key(ticket, ["ORDER_NO", "TICKET_SEQ"], "BET_TICKET")
    unique_key(order, ["ORDER_NO"], "BET_ORDER")
    unique_key(race, ["RC_DT", "RC_NO"], "RC_RACE")
    unique_key(member, ["MBR_NO"], "MBR_MASTER")
    unique_key(ticket, ["_SRC_ROW_NO"], "BET_TICKET source row")
    unique_key(order, ["_SRC_ROW_NO"], "BET_ORDER source row")
    require(not ticket["BET_AMT"].isna().any(), "BET_TICKET: null BET_AMT")
    require(not order["SALE_DTM"].isna().any(), "BET_ORDER: null SALE_DTM")
    require(ticket["TICKET_STAT_CD"].isin(["SOLD", "CANCEL", "VOID"]).all(),
            "BET_TICKET: unknown ticket status")
    require(ticket["INVALID_YN"].isin(["Y", "N"]).all(),
            "BET_TICKET: unknown invalid flag")
    require(ticket["INVALID_YN"].eq("Y").eq(ticket["BET_AMT"].eq(0)).all(),
            "BET_TICKET: invalid flag does not match zero amount")
    require(ticket["LATE_CANCEL_YN"].isin(["Y", "N"]).all(),
            "BET_TICKET: unknown late cancellation flag")
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
    dim_race["START_DTM"] = seoul_timestamp(dim_race["START_DTM"], "RC_RACE.START_DTM")
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
        "ORIG_MISSING_YN", "_SRC_ROW_NO",
    ]
    fact_ticket = ticket.merge(
        order[order_fields].rename(columns={"_SRC_ROW_NO": "_ORDER_SRC_ROW_NO"}),
        on="ORDER_NO", how="left", validate="many_to_one",
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
    # D-003: zero-amount tickets stay in the fact but do not enter sales measures.
    included = fact_ticket["INVALID_YN"].eq("N")
    fact_ticket["SALES_AGG_INCLUDE_YN"] = included.map({True: "Y", False: "N"})
    fact_ticket["ZERO_LATE_CANCEL_YN"] = (
        fact_ticket["INVALID_YN"].eq("Y") & fact_ticket["LATE_CANCEL_YN"].eq("Y")
    ).map({True: "Y", False: "N"})
    sold = fact_ticket["TICKET_STAT_CD"].eq("SOLD") & included
    cancel = fact_ticket["TICKET_STAT_CD"].eq("CANCEL") & included
    void = fact_ticket["TICKET_STAT_CD"].eq("VOID") & included
    fact_ticket["VIRTUAL_GROSS_SALES_AMT"] = amt.where(sold, 0)
    fact_ticket["SOLD_TICKET_CNT"] = sold.astype("int64")
    fact_ticket["CANCEL_AMT"] = (-amt).where(cancel, 0)
    fact_ticket["VOID_AMT"] = amt.where(void, 0)
    fact_ticket["NET_AFTER_CANCEL_AMT"] = (
        fact_ticket["VIRTUAL_GROSS_SALES_AMT"] - fact_ticket["CANCEL_AMT"]
    )
    fact_ticket["SALE_DTM"] = seoul_timestamp(fact_ticket["SALE_DTM"], "BET_ORDER.SALE_DTM")
    fact_ticket["SALE_HOUR"] = fact_ticket["SALE_DTM"].dt.hour
    fact_ticket = fact_ticket[[
        "ORDER_NO", "TICKET_SEQ", "RACE_KEY", "DATE_KEY", "BET_TYPE_CD",
        "CHANNEL_KEY", "MEMBER_KEY",
        "RC_DT", "RC_NO",
        "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM", "BIZ_DT", "SALE_HOUR",
        "TICKET_STAT_CD", "BET_AMT", "UNIT_CNT",
        "VIRTUAL_GROSS_SALES_AMT", "SOLD_TICKET_CNT", "CANCEL_AMT", "VOID_AMT",
        "NET_AFTER_CANCEL_AMT", "SALES_AGG_INCLUDE_YN", "INVALID_YN",
        "LATE_CANCEL_YN", "ZERO_LATE_CANCEL_YN", "HEADER_MISMATCH_YN",
        "ORIG_MISSING_YN", "_SRC_ROW_NO", "_ORDER_SRC_ROW_NO",
    ]].sort_values(["ORDER_NO", "TICKET_SEQ"], kind="stable").reset_index(drop=True)

    tables = {
        "DIM_RACE": (dim_race, ["RACE_KEY"]),
        "DIM_DATE": (dim_date, ["DATE_KEY"]),
        "DIM_BET_TYPE": (dim_bet_type, ["BET_TYPE_CD"]),
        "DIM_CHANNEL": (dim_channel, ["CHANNEL_KEY"]),
        "DIM_MEMBER": (dim_member, ["MEMBER_KEY"]),
        "DIM_TICKET_STATUS": (dim_ticket_status, ["TICKET_STAT_CD"]),
        FACT_NAME: (fact_ticket, ["ORDER_NO", "TICKET_SEQ"]),
    }
    pk_duplicates = {}
    for name, (frame, pk) in tables.items():
        unique_key(frame, pk, name)
        pk_duplicates[name] = int(frame.duplicated(pk).sum())
    missing_fks = {}
    for dimension, key in [
        ("DIM_RACE", "RACE_KEY"), ("DIM_DATE", "DATE_KEY"),
        ("DIM_BET_TYPE", "BET_TYPE_CD"), ("DIM_CHANNEL", "CHANNEL_KEY"),
        ("DIM_MEMBER", "MEMBER_KEY"), ("DIM_TICKET_STATUS", "TICKET_STAT_CD"),
    ]:
        missing = fact_ticket[key].isna() | ~fact_ticket[key].isin(tables[dimension][0][key])
        missing_fks[dimension] = int(missing.sum())
        require(not missing.any(), f"{FACT_NAME}: missing {dimension} FK")
    race_dates = dim_race[["RACE_KEY"]].assign(DATE_KEY=date_key(dim_race))
    race_date_match = fact_ticket[["DATE_KEY", "RACE_KEY"]].merge(
        race_dates, on=["DATE_KEY", "RACE_KEY"], how="left", validate="many_to_one", indicator=True
    )["_merge"].eq("both")
    require(race_date_match.all(), f"{FACT_NAME}: race/date mismatch")
    require(int(fact_ticket["MEMBER_KEY"].eq("NON_MEMBER").sum()) ==
            int(fact_ticket["MBR_NO"].isna().sum()),
            "non-member ticket reconciliation failed")
    require(len(fact_ticket) == len(ticket), "ticket row reconciliation failed")
    unique_key(fact_ticket, ["_SRC_ROW_NO"], f"{FACT_NAME} source row")
    require(fact_ticket["_SRC_ROW_NO"].isin(ticket["_SRC_ROW_NO"]).all(),
            "ticket source row membership reconciliation failed")
    source_amounts = {}
    for status, column, sign in [
        ("SOLD", "VIRTUAL_GROSS_SALES_AMT", 1),
        ("CANCEL", "CANCEL_AMT", -1),
        ("VOID", "VOID_AMT", 1),
    ]:
        source = ticket.loc[
            ticket.TICKET_STAT_CD.eq(status) & ticket.INVALID_YN.eq("N"),
            "BET_AMT",
        ].sum()
        require(int(fact_ticket[column].sum()) == sign * int(source),
                f"{status} amount reconciliation failed")
        source_amounts[column] = sign * int(source)
    source_amounts["NET_AFTER_CANCEL_AMT"] = (
        source_amounts["VIRTUAL_GROSS_SALES_AMT"] - source_amounts["CANCEL_AMT"]
    )
    require(int(fact_ticket.NET_AFTER_CANCEL_AMT.sum()) == source_amounts["NET_AFTER_CANCEL_AMT"],
            "net amount reconciliation failed")
    source_sold_count = int((ticket.TICKET_STAT_CD.eq("SOLD") & ticket.INVALID_YN.eq("N")).sum())
    require(int(fact_ticket.SOLD_TICKET_CNT.sum()) == source_sold_count,
            "sold ticket count reconciliation failed")
    require(int(fact_ticket.BET_AMT.sum()) == int(ticket.BET_AMT.sum()),
            "original ticket amount reconciliation failed")

    report = {
        "input_provenance": provenance,
        "grain": {FACT_NAME: ["ORDER_NO", "TICKET_SEQ"]},
        "source_rows": {"BET_TICKET": len(ticket), "BET_ORDER": len(order),
                        "MBR_MASTER": len(member), "RC_RACE": len(race)},
        "gold_rows": {name: len(frame) for name, (frame, _) in tables.items()},
        "gold_excluded_rows": {"BET_TICKET": 0},
        "row_reconciliation": {"BET_TICKET": {
            "input_rows": len(ticket), "kept_rows": len(fact_ticket),
            "excluded_rows": 0, "one_to_one_source_row_mapping": True,
        }},
        "source_ticket_measures_krw": source_amounts,
        "ticket_measures_krw": {
            column: int(fact_ticket[column].sum()) for column in [
                "VIRTUAL_GROSS_SALES_AMT", "CANCEL_AMT", "VOID_AMT",
                "NET_AFTER_CANCEL_AMT",
            ]
        },
        "sold_ticket_count": {"source": source_sold_count, "gold": int(fact_ticket.SOLD_TICKET_CNT.sum())},
        "quality_flag_count": {
            "INVALID_YN": int(fact_ticket.INVALID_YN.eq("Y").sum()),
            "LATE_CANCEL_YN": int(fact_ticket.LATE_CANCEL_YN.eq("Y").sum()),
            "ZERO_LATE_CANCEL_YN": int(fact_ticket.ZERO_LATE_CANCEL_YN.eq("Y").sum()),
        },
        "pk_duplicate_count": pk_duplicates,
        "missing_dimension_fk_count": {FACT_NAME: missing_fks},
        "race_date_mismatch_count": int((~race_date_match).sum()),
        "quality_decision_ids": {
            "zero_amount": "D-003", "late_cancel": "D-004", "order_flags": "D-006",
            "clean_input": "D-012", "timestamp": "MR-5",
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
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--silver", type=Path, default=SILVER, help="Shared clean directory with _manifest.json")
    source.add_argument("--silver-ref", help="Read clean directly from a Git commit/ref without changing Silver files")
    parser.add_argument("--gold", type=Path, default=GOLD)
    args = parser.parse_args()
    print(json.dumps(build(args.silver, args.gold, args.silver_ref), ensure_ascii=False, indent=2))
