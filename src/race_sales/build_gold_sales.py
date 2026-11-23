"""Build the ticket sales star schema from the shared quality-managed clean data.

Run: python src/race_sales/build_gold_sales.py
Read shared dimensions from data/03_gold/common (D-013 to D-016).
Output: the ticket fact and its two private dimensions in data/03_gold/race_sales.
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
COMMON = ROOT / "data" / "03_gold" / "common"
COMMON_KEYS = {
    "DIM_RACE": "RACE_KEY", "DIM_DATE": "DATE_KEY",
    "DIM_CHANNEL": "CHANNEL_KEY", "DIM_MEMBER": "MEMBER_KEY",
}
SOURCE_TABLES = ("BET_TICKET", "BET_ORDER", "RC_RACE", "MBR_MASTER")
FACT_NAME = "FCT_RACE_SALES"

BET_TYPES = {
    "WIN": "단승", "PLC": "연승", "QNL": "복승", "QPL": "복연승",
    "EXA": "쌍승", "TRI": "삼복승", "TLA": "삼쌍승",
}
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


def check_output_path(silver: Path, gold: Path, common: Path = COMMON) -> None:
    """Reject output paths that overlap an earlier stage or the input directory."""
    output = gold.resolve()
    protected = [ROOT / "data" / stage for stage in ("00_origin", "01_bronze", "02_silver")]
    for directory in [*protected, silver, COMMON, common]:
        directory = directory.resolve()
        require(not output.is_relative_to(directory) and not directory.is_relative_to(output),
                f"Gold output overlaps protected input: {directory}")


def unique_key(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    require(not frame[columns].isna().any().any(), f"{name}: null PK {columns}")
    require(not frame.duplicated(columns).any(), f"{name}: duplicate PK {columns}")


def read_common(common: Path) -> tuple[dict, dict]:
    """Read shared dimensions without rewriting them, recording content hashes."""
    dimensions, hashes = {}, {}
    for name, key in COMMON_KEYS.items():
        payload = (common / f"{name}.parquet").read_bytes()
        frame = pd.read_parquet(io.BytesIO(payload))
        unique_key(frame, [key], name)
        require(pd.api.types.is_integer_dtype(frame[key]), f"{name}: non-integer PK")
        require(int(frame[key].eq(0).sum()) == 1 and frame[key].ge(0).all(),
                f"{name}: expected one UNKNOWN key 0 and nonnegative keys (D-013)")
        dimensions[name] = frame
        hashes[f"{name}.parquet"] = hashlib.sha256(payload).hexdigest()
    return dimensions, {"input_path": "data/03_gold/common/", "input_file_sha256": hashes}


def date_key(values: pd.Series, dim_date: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(values)
    keys = (dates.dt.year * 10000 + dates.dt.month * 100 + dates.dt.day).fillna(0).astype("int32")
    return keys.where(keys.isin(dim_date["DATE_KEY"]), 0)


def seoul_timestamp(values: pd.Series, name: str) -> pd.Series:
    """Return timezone-naive KST wall time (D-013, MR-5)."""
    values = pd.to_datetime(values)
    require(not values.isna().any(), f"{name}: null timestamp")
    if values.dt.tz is not None:
        values = values.dt.tz_convert("Asia/Seoul").dt.tz_localize(None)
    return values


def attach_common_keys(frame: pd.DataFrame, dimensions: dict) -> pd.DataFrame:
    """Join business keys as specified in docs/gold/common.md section 2."""
    races = dimensions["DIM_RACE"].query("RACE_KEY > 0")
    channels = dimensions["DIM_CHANNEL"].query("CHANNEL_KEY > 0")
    members = dimensions["DIM_MEMBER"]
    known_members = members[members["MBR_TYPE_CD"].eq("MEMBER")]
    non_member = members[members["MBR_TYPE_CD"].eq("NON_MEMBER")]
    unique_key(races, ["RC_DT", "RC_NO"], "DIM_RACE business key")
    unique_key(known_members, ["MBR_NO"], "DIM_MEMBER business key")
    require(not channels.duplicated(["CHNL_CD", "OTB_BRANCH_NO"]).any(),
            "DIM_CHANNEL: duplicate business key")
    require(len(non_member) == 1 and non_member["MEMBER_KEY"].iloc[0] > 0,
            "DIM_MEMBER: expected one positive NON_MEMBER key (D-016)")
    result = frame.merge(races[["RC_DT", "RC_NO", "RACE_KEY"]],
                         on=["RC_DT", "RC_NO"], how="left", validate="many_to_one")
    result = result.merge(channels[["CHNL_CD", "OTB_BRANCH_NO", "CHANNEL_KEY"]],
                          on=["CHNL_CD", "OTB_BRANCH_NO"], how="left", validate="many_to_one")
    result.loc[result["CHNL_CD"].eq("UNKNOWN"), "CHANNEL_KEY"] = 0
    result["MEMBER_KEY"] = result["MBR_NO"].map(known_members.set_index("MBR_NO")["MEMBER_KEY"])
    non_member_rows = result["MBR_NO"].isna() | result["MBR_NO"].astype("string").str.strip().eq("").fillna(False)
    result.loc[non_member_rows, "MEMBER_KEY"] = non_member["MEMBER_KEY"].iloc[0]
    for key in ["RACE_KEY", "CHANNEL_KEY", "MEMBER_KEY"]:
        result[key] = result[key].fillna(0).astype("int32")
    result["DATE_KEY"] = date_key(result["RC_DT"], dimensions["DIM_DATE"])
    result["SALE_DTM"] = seoul_timestamp(result["SALE_DTM"], "BET_ORDER.SALE_DTM")
    result["SALE_DT_KEY"] = date_key(result["SALE_DTM"], dimensions["DIM_DATE"])
    return result


def build(silver: Path = SILVER, gold: Path = GOLD, silver_ref: str | None = None,
          common: Path = COMMON) -> dict:
    check_output_path(silver, gold, common)
    sources, provenance = read_sources(silver, silver_ref)
    dimensions, common_provenance = read_common(common)
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

    bet_codes = sorted(ticket["BET_TYPE_CD"].dropna().unique().tolist())
    require(set(bet_codes).issubset(BET_TYPES), "BET_TICKET: unexpected bet type codes")
    dim_bet_type = pd.DataFrame(
        [(code, BET_TYPES[code]) for code in bet_codes],
        columns=["BET_TYPE_CD", "BET_TYPE_NM"],
    )
    dim_ticket_status = pd.DataFrame(
        list(TICKET_STATUSES.items()), columns=["TICKET_STAT_CD", "TICKET_STAT_NM"]
    ).sort_values("TICKET_STAT_CD", kind="stable").reset_index(drop=True)

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
    fact_ticket = attach_common_keys(fact_ticket, dimensions)
    require(len(fact_ticket) == len(ticket), "common dimension joins changed row count")

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
    fact_ticket["SALE_HOUR_NO"] = fact_ticket["SALE_DTM"].dt.hour
    fact_ticket = fact_ticket[[
        "ORDER_NO", "TICKET_SEQ", "RACE_KEY", "DATE_KEY", "BET_TYPE_CD",
        "CHANNEL_KEY", "MEMBER_KEY", "SALE_DT_KEY",
        "RC_DT", "RC_NO",
        "ORDER_TYPE_CD", "ORIG_ORDER_NO", "MBR_NO", "SALE_DTM", "BIZ_DT", "SALE_HOUR_NO",
        "TICKET_STAT_CD", "BET_AMT", "UNIT_CNT",
        "VIRTUAL_GROSS_SALES_AMT", "SOLD_TICKET_CNT", "CANCEL_AMT", "VOID_AMT",
        "NET_AFTER_CANCEL_AMT", "SALES_AGG_INCLUDE_YN", "INVALID_YN",
        "LATE_CANCEL_YN", "ZERO_LATE_CANCEL_YN", "HEADER_MISMATCH_YN",
        "ORIG_MISSING_YN", "_SRC_ROW_NO", "_ORDER_SRC_ROW_NO",
    ]].sort_values(["ORDER_NO", "TICKET_SEQ"], kind="stable").reset_index(drop=True)

    tables = {
        "DIM_BET_TYPE": (dim_bet_type, ["BET_TYPE_CD"]),
        "DIM_TICKET_STATUS": (dim_ticket_status, ["TICKET_STAT_CD"]),
        FACT_NAME: (fact_ticket, ["ORDER_NO", "TICKET_SEQ"]),
    }
    pk_duplicates = {}
    all_tables = {name: (frame, [COMMON_KEYS[name]]) for name, frame in dimensions.items()} | tables
    for name, (frame, pk) in all_tables.items():
        unique_key(frame, pk, name)
        pk_duplicates[name] = int(frame.duplicated(pk).sum())
    missing_fks = {}
    for dimension, key in [
        ("DIM_RACE", "RACE_KEY"), ("DIM_DATE", "DATE_KEY"), ("DIM_DATE", "SALE_DT_KEY"),
        ("DIM_BET_TYPE", "BET_TYPE_CD"), ("DIM_CHANNEL", "CHANNEL_KEY"),
        ("DIM_MEMBER", "MEMBER_KEY"), ("DIM_TICKET_STATUS", "TICKET_STAT_CD"),
    ]:
        dim_key = COMMON_KEYS.get(dimension, key)
        missing = fact_ticket[key].isna() | ~fact_ticket[key].isin(all_tables[dimension][0][dim_key])
        missing_fks[dimension] = missing_fks.get(dimension, 0) + int(missing.sum())
        require(not missing.any(), f"{FACT_NAME}: missing {dimension} FK")
    dim_race = dimensions["DIM_RACE"]
    race_dates = dim_race[["RACE_KEY"]].assign(DATE_KEY=date_key(dim_race["RC_DT"], dimensions["DIM_DATE"]))
    expected_race_dates = fact_ticket["RACE_KEY"].map(race_dates.set_index("RACE_KEY")["DATE_KEY"])
    race_date_match = fact_ticket["RACE_KEY"].eq(0) | fact_ticket["DATE_KEY"].eq(expected_race_dates)
    require(race_date_match.all(), f"{FACT_NAME}: race/date mismatch")
    non_member_key = int(dimensions["DIM_MEMBER"].loc[
        dimensions["DIM_MEMBER"]["MBR_TYPE_CD"].eq("NON_MEMBER"), "MEMBER_KEY"
    ].iloc[0])
    non_member_rows = fact_ticket["MBR_NO"].isna() | fact_ticket["MBR_NO"].astype("string").str.strip().eq("").fillna(False)
    require(fact_ticket["MEMBER_KEY"].eq(non_member_key).eq(non_member_rows).all(),
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
        "common_dimension_provenance": common_provenance,
        "grain": {FACT_NAME: ["ORDER_NO", "TICKET_SEQ"]},
        "source_rows": {"BET_TICKET": len(ticket), "BET_ORDER": len(order),
                        "MBR_MASTER": len(member), "RC_RACE": len(race)},
        "gold_rows": {name: len(frame) for name, (frame, _) in tables.items()},
        "common_dimension_rows": {name: len(frame) for name, frame in dimensions.items()},
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
        "unknown_dimension_key_count": {
            key: int(fact_ticket[key].eq(0).sum())
            for key in ["RACE_KEY", "DATE_KEY", "SALE_DT_KEY", "CHANNEL_KEY", "MEMBER_KEY"]
        },
        "non_member_ticket_count": int(non_member_rows.sum()),
        "race_date_mismatch_count": int((~race_date_match).sum()),
        "quality_decision_ids": {
            "zero_amount": "D-003", "late_cancel": "D-004", "order_flags": "D-006",
            "clean_input": "D-012", "timestamp": "D-013", "common_keys": "D-013",
            "date_roles": "D-014", "non_member": "D-016",
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
    parser.add_argument("--common", type=Path, default=COMMON, help="Read-only shared Gold dimension directory")
    args = parser.parse_args()
    print(json.dumps(build(args.silver, args.gold, args.silver_ref, args.common), ensure_ascii=False, indent=2))
