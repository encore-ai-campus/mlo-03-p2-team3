"""Build the medical star schema from a verified Silver clean snapshot."""

import argparse
import hashlib
import json
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DAY = timedelta(days=1)
ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "02_silver" / "clean"
GOLD_DIR = ROOT / "data" / "03_gold" / "horse_medical"
HORSE_ATTRIBUTES = ("HR_SEX_CD", "HR_GRADE_CD", "HR_AGE", "TR_GRP_NO", "TR_NM", "TR_EXTERNAL_YN", "OW_NM")
KEYS = {
    "DIM_DATE": "DATE_KEY", "DIM_HORSE": "HORSE_KEY", "DIM_TRAINER": "TRAINER_KEY",
    "DIM_AGE_GROUP": "AGE_GROUP_KEY", "DIM_VET_TYPE": "VET_TYPE_KEY",
}
I32 = pa.int32()
TEXT = pa.string()
DATE = pa.date32()
FK = {
    "VET_DT_KEY": "DIM_DATE", "REPORT_DT_KEY": "DIM_DATE", "HORSE_KEY": "DIM_HORSE",
    "TRAINER_KEY": "DIM_TRAINER", "AGE_GROUP_KEY": "DIM_AGE_GROUP",
}
FACT_SCHEMA = pa.schema([("VET_SEQ", I32), *((key, I32) for key in FK), ("VET_CNT", I32)])
BRIDGE_SCHEMA = pa.schema([("VET_SEQ", I32), ("VET_TYPE_KEY", I32)])


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_clean_manifest(expected_version):
    hashes = {path.name: digest(path) for path in sorted(CLEAN_DIR.glob("*.parquet"))}
    if not hashes:
        raise ValueError(f"[D-012] No clean Parquet files in {CLEAN_DIR}.")
    version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    path = CLEAN_DIR / "_manifest.json"
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["CLEAN_SHA256"] != hashes or manifest["CLEAN_VERSION"] != version:
            raise ValueError("[D-012] Clean files do not match their manifest.")
    elif not expected_version:
        raise ValueError("[D-012] Provide --clean-version when the shared clean snapshot has no manifest.")
    if expected_version and version != expected_version:
        raise ValueError(f"[D-012] The clean snapshot checksum is {version}, not the agreed version.")
    return version, manifest.get("SOURCE_COMMIT") if path.is_file() else None


def read_clean(name, columns=None):
    return pq.read_table(CLEAN_DIR / f"{name}.parquet", columns=columns).to_pylist()


def no_prior_snapshot(row):
    if "PRIOR_SNAPSHOT_MISSING_YN" in row:
        return row["PRIOR_SNAPSHOT_MISSING_YN"] == "Y"
    return row["HORSE_MATCH_STATUS_CD"] == "NO_PRIOR_SNAPSHOT"


def age_group_dimension():
    return pa.Table.from_pylist([
        {"AGE_GROUP_KEY": i, "AGE_GROUP_NM": name, "MIN_AGE": lo, "MAX_AGE": hi}
        for i, (name, lo, hi) in enumerate([
            ("UNKNOWN", None, None), ("2~3세", 2, 3), ("4~5세", 4, 5), ("6~7세", 6, 7), ("8세 이상", 8, None)
        ])
    ], schema=pa.schema([("AGE_GROUP_KEY", I32), ("AGE_GROUP_NM", TEXT), ("MIN_AGE", I32), ("MAX_AGE", I32)]))


def build_date_dimension(history):
    medical_days = {row[column] for row in history for column in ("VET_DT", "REPORT_DT")}
    race_days = {row["RC_DT"] for row in read_clean("RC_RACE", ["RC_DT"])}
    first, last = min(medical_days), max(medical_days)
    rows = []
    for offset in range((last - first).days + 1):
        day = first + offset * DAY
        day_of_week = day.isoweekday()
        rows.append({
            "DATE_KEY": day.year * 10000 + day.month * 100 + day.day,
            "FULL_DT": day, "YEAR_NO": day.year, "MONTH_NO": day.month, "DAY_NO": day.day,
            "DOW_NO": day_of_week, "DOW_NM": "월화수목금토일"[day_of_week - 1],
            "WEEK_NO": day.isocalendar().week, "RACE_DAY_YN": "Y" if day in race_days else "N",
        })
    return pa.Table.from_pylist(rows, schema=pa.schema([
        ("DATE_KEY", I32), ("FULL_DT", DATE), ("YEAR_NO", I32), ("MONTH_NO", I32),
        ("DAY_NO", I32), ("DOW_NO", I32), ("DOW_NM", TEXT), ("WEEK_NO", I32), ("RACE_DAY_YN", TEXT),
    ]))


def build_horse_dimension(age_groups):
    columns = ["HR_NM", "SNAPSHOT_DT", "_SRC_ROW_NO", "HR_BIRTH_DT", "SIRE_NM", "DAM_NM", *HORSE_ATTRIBUTES]
    snapshots = sorted(read_clean("HR_WEEKLY_SNAPSHOT", columns), key=lambda row: (
        row["HR_NM"], row["SNAPSHOT_DT"], row["_SRC_ROW_NO"],
    ))
    versions = [{"HORSE_KEY": 0, "CURRENT_YN": "N"}]
    age_names = {row["AGE_GROUP_KEY"]: row["AGE_GROUP_NM"] for row in age_groups}
    previous = None
    for snapshot in snapshots:
        name = snapshot["HR_NM"]
        values = {column: snapshot[column] for column in HORSE_ATTRIBUTES}
        if previous and name == previous["HR_NM"]:
            if values == {column: previous[column] for column in HORSE_ATTRIBUTES}:
                continue
            previous["VALID_TO_DT"] = snapshot["SNAPSHOT_DT"]
            previous["CURRENT_YN"] = "N"
        age_key = age_group_key(snapshot["HR_AGE"], age_groups)
        previous = {
            "HORSE_KEY": len(versions), "HR_NM": name, "VALID_FROM_DT": snapshot["SNAPSHOT_DT"] + DAY,
            "VALID_TO_DT": date.max, "HR_BIRTH_DT": snapshot["HR_BIRTH_DT"], "CURRENT_YN": "Y",
            "SRC_SNAPSHOT_DT": snapshot["SNAPSHOT_DT"], "SIRE_NM": snapshot["SIRE_NM"],
            "DAM_NM": snapshot["DAM_NM"], "AGE_BAND_NM": age_names.get(age_key), **values,
        }
        versions.append(previous)
    schema = pa.schema([
        ("HORSE_KEY", I32), ("HR_NM", TEXT), ("HR_SEX_CD", TEXT), ("HR_BIRTH_DT", DATE),
        ("HR_AGE", I32), ("AGE_BAND_NM", TEXT), ("HR_GRADE_CD", TEXT), ("TR_GRP_NO", TEXT),
        ("TR_NM", TEXT), ("TR_EXTERNAL_YN", TEXT), ("OW_NM", TEXT), ("SIRE_NM", TEXT), ("DAM_NM", TEXT),
        ("SRC_SNAPSHOT_DT", DATE), ("VALID_FROM_DT", DATE), ("VALID_TO_DT", DATE), ("CURRENT_YN", TEXT),
    ])
    return pa.Table.from_pylist(versions, schema=schema)


def build_trainer_dimension():
    columns = ["TR_NM", "TR_GRP_NO", "TR_BIRTH_DT", "DEBUT_DT", "SNAPSHOT_DT", "_SRC_ROW_NO"]
    snapshots = sorted(read_clean("TR_WEEKLY_SNAPSHOT", columns), key=lambda row: (
        row["TR_NM"], row["SNAPSHOT_DT"], row["_SRC_ROW_NO"],
    ))
    latest = {row["TR_NM"]: row for row in snapshots}
    return pa.Table.from_pylist([
        {"TRAINER_KEY": key, **row} for key, row in enumerate(latest.values(), 1)
    ], schema=pa.schema([
        ("TRAINER_KEY", I32), ("TR_NM", TEXT), ("TR_GRP_NO", TEXT), ("TR_BIRTH_DT", DATE), ("DEBUT_DT", DATE),
    ]))


def horse_index(dimension):
    versions = defaultdict(list)
    for row in dimension.to_pylist():
        if row["HORSE_KEY"] != 0:
            if (
                not row["HR_NM"] or row["VALID_FROM_DT"] is None or row["VALID_TO_DT"] is None
                or row["VALID_FROM_DT"] > row["VALID_TO_DT"]
            ):
                raise ValueError(f"Invalid DIM_HORSE version: {row['HORSE_KEY']}")
            versions[row["HR_NM"]].append(row)
    result = {}
    for name, rows in versions.items():
        rows.sort(key=lambda row: row["VALID_FROM_DT"])
        for previous, current in zip(rows, rows[1:]):
            if previous["VALID_TO_DT"] >= current["VALID_FROM_DT"]:
                raise ValueError(f"Overlapping DIM_HORSE versions for {name}.")
        result[name] = ([row["VALID_FROM_DT"] for row in rows], rows)
    return result


def lookup_horse(index, name, event_date):
    starts, rows = index.get(name, ([], []))
    position = bisect_right(starts, event_date) - 1
    if position >= 0 and event_date <= rows[position]["VALID_TO_DT"]:
        return rows[position]
    return None


def age_group_key(age, groups):
    if age is None:
        return 0
    matches = [
        row["AGE_GROUP_KEY"] for row in groups
        if row["MIN_AGE"] <= age and (row["MAX_AGE"] is None or age <= row["MAX_AGE"])
    ]
    if len(matches) > 1:
        raise ValueError(f"Overlapping age groups for age {age}.")
    return matches[0] if matches else 0


def make_fact(history, dimensions, age_groups):
    dates = {row["FULL_DT"]: row["DATE_KEY"] for row in dimensions["DIM_DATE"].to_pylist()}
    groups = {row["TR_GRP_NO"]: row["TRAINER_KEY"] for row in dimensions["DIM_TRAINER"].to_pylist()}
    if len(dates) != dimensions["DIM_DATE"].num_rows or len(groups) != dimensions["DIM_TRAINER"].num_rows:
        raise ValueError("[AG-7] Duplicate date or trainer group business key.")
    horses = horse_index(dimensions["DIM_HORSE"])
    fact = []
    for row in history:
        date_of_visit = row["VET_DT"]
        horse = lookup_horse(horses, row["HR_NM"], date_of_visit)
        if (horse is None) != no_prior_snapshot(row):
            raise ValueError(f"Clean and horse dimension disagree on VET_SEQ={row['VET_SEQ']}.")
        age = horse["HR_AGE"] if horse else None
        fact.append({
            "VET_SEQ": row["VET_SEQ"], "VET_DT_KEY": dates[date_of_visit], "REPORT_DT_KEY": dates[row["REPORT_DT"]],
            "HORSE_KEY": horse["HORSE_KEY"] if horse else 0, "TRAINER_KEY": groups[row["TR_GRP_NO"]],
            "AGE_GROUP_KEY": age_group_key(age, age_groups), "VET_CNT": 1,
        })
    return fact


def validate(fact, bridge, dimensions, history, clean_bridge):
    dimension_keys = {}
    for name, field in KEYS.items():
        values = dimensions[name][field].to_pylist()
        if None in values or len(values) != len(set(values)):
            raise ValueError(f"[AG-7] Invalid primary key in {name}.")
        dimension_keys[name] = set(values)
    sequences = {row["VET_SEQ"] for row in fact}
    if (
        None in sequences or len(sequences) != len(fact) or len(fact) != len(history)
        or sequences != {row["VET_SEQ"] for row in history}
        or any(row["VET_CNT"] != 1 for row in fact)
    ):
        raise ValueError("[AG-3] Gold fact must have one row per clean medical history record.")
    for key, dimension in FK.items():
        if {row[key] for row in fact} - dimension_keys[dimension]:
            raise ValueError(f"[AG-7] Unresolved Gold foreign key: {key}")
    bridge_keys = {(row["VET_SEQ"], row["VET_TYPE_KEY"]) for row in bridge}
    if len(bridge_keys) != len(bridge) or {sequence for sequence, _ in bridge_keys} != sequences:
        raise ValueError("[AG-7] Gold bridge primary or history key is invalid.")
    if {key for _, key in bridge_keys} - dimension_keys["DIM_VET_TYPE"]:
        raise ValueError("[AG-7] Unresolved Gold veterinary type key.")
    type_names = {row["VET_TYPE_KEY"]: row["VET_TYPE_NM"] for row in dimensions["DIM_VET_TYPE"].to_pylist()}
    source_types = {(row["VET_SEQ"], row["VET_TYPE_NM"]) for row in clean_bridge}
    if (
        len(bridge) != len(clean_bridge)
        or {(sequence, type_names[key]) for sequence, key in bridge_keys} != source_types
        or {row["VET_SEQ"] for row in fact if row["HORSE_KEY"] == 0}
        != {row["VET_SEQ"] for row in history if no_prior_snapshot(row)}
    ):
        raise ValueError("[AG-3] Gold medical totals differ from the clean quality results.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-version", help="Team-approved clean manifest CLEAN_VERSION")
    parser.add_argument("--check", action="store_true", help="Compare existing Gold to the verified inputs without writing")
    args = parser.parse_args()
    clean_version, source_commit = read_clean_manifest(args.clean_version)
    history = sorted(read_clean("HR_VET_HIST"), key=lambda row: row["VET_SEQ"])
    clean_bridge = sorted(read_clean("HR_VET_TYPE_BRIDGE"), key=lambda row: (row["VET_SEQ"], row["VET_TYPE_NM"]))
    age_dimension = age_group_dimension()
    age_groups = [row for row in age_dimension.to_pylist() if row["AGE_GROUP_KEY"] != 0]
    dimensions = {
        "DIM_DATE": build_date_dimension(history),
        "DIM_HORSE": build_horse_dimension(age_groups),
        "DIM_TRAINER": build_trainer_dimension(),
        "DIM_AGE_GROUP": age_dimension,
    }

    names = sorted({row["VET_TYPE_NM"] for row in clean_bridge})
    type_keys = {label: i for i, label in enumerate(names, 1)}
    dimensions["DIM_VET_TYPE"] = pa.Table.from_pylist(
        [{"VET_TYPE_KEY": key, "VET_TYPE_NM": label} for label, key in type_keys.items()],
        schema=pa.schema([("VET_TYPE_KEY", I32), ("VET_TYPE_NM", TEXT)]),
    )
    fact = make_fact(history, dimensions, age_groups)
    bridge = [{"VET_SEQ": row["VET_SEQ"], "VET_TYPE_KEY": type_keys[row["VET_TYPE_NM"]]} for row in clean_bridge]
    validate(fact, bridge, dimensions, history, clean_bridge)

    tables = {
        **dimensions, "FCT_HORSE_MEDICAL": pa.Table.from_pylist(fact, schema=FACT_SCHEMA),
        "BRIDGE_HR_VET_TYPE": pa.Table.from_pylist(bridge, schema=BRIDGE_SCHEMA),
    }
    report = {
        "STATUS": "INDIVIDUAL_VALIDATED",
        "CLEAN_VERSION": clean_version,
        "CLEAN_SOURCE_COMMIT": source_commit,
        "CLEAN_INPUT_ROWS": {"HR_VET_HIST": len(history), "HR_VET_TYPE_BRIDGE": len(clean_bridge)},
        "GOLD_EXCLUDED_ROWS": 0,
        "TABLE_ROWS": {name: table.num_rows for name, table in tables.items()},
        "VET_CNT_SUM": sum(row["VET_CNT"] for row in fact),
        "NO_PRIOR_SNAPSHOT_ROWS": sum(row["HORSE_KEY"] == 0 for row in fact),
        "PK_DUPLICATES": 0, "UNRESOLVED_FOREIGN_KEYS": 0,
    }
    manifest = GOLD_DIR / "_manifest.json"
    if args.check:
        for name, table in tables.items():
            if not pq.read_table(GOLD_DIR / f"{name}.parquet").equals(table):
                raise ValueError(f"[AG-3] Stored {name} differs from the verified inputs.")
        if json.loads(manifest.read_text(encoding="utf-8")) != report:
            raise ValueError("[D-012] Stored Gold manifest differs from the verified inputs.")
    else:
        GOLD_DIR.mkdir(parents=True, exist_ok=True)
        for name, table in tables.items():
            pq.write_table(table, GOLD_DIR / f"{name}.parquet")
        manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    action = "verified" if args.check else "built"
    print(f"{GOLD_DIR.relative_to(ROOT)}: {action} {len(fact):,} medical records and {len(bridge):,} type links")


if __name__ == "__main__":
    main()
