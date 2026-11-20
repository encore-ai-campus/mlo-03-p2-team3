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

import config as C


DAY = timedelta(days=1)
CLEAN_DIR = C.SILVER_DIR / "clean"
GOLD_DIR = C.ROOT / "data" / "03_gold"
HORSE_ATTRIBUTES = ("HR_SEX_CD", "HR_GRADE_CD", "HR_AGE", "TR_GRP_NO", "TR_NM", "TR_EXTERNAL_YN", "OW_NM")
COMMON_COLUMNS = {
    "DIM_DATE": ["DATE_KEY", "FULL_DT"],
    "DIM_HORSE": ["HORSE_KEY", "HR_NM", "VALID_FROM_DT", "VALID_TO_DT", "HR_AGE"],
    "DIM_TRAINER": ["TRAINER_KEY", "TR_GRP_NO"],
    "DIM_AGE_GROUP": ["AGE_GROUP_KEY", "MIN_AGE", "MAX_AGE"],
}
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
    hashes = {f"{name}.parquet": digest(CLEAN_DIR / f"{name}.parquet") for name in C.EXPECTED_SILVER_ROWS}
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
    return version


def read_clean(name, columns=None):
    return pq.read_table(CLEAN_DIR / f"{name}.parquet", columns=columns).to_pylist()


def no_prior_snapshot(row):
    if "PRIOR_SNAPSHOT_MISSING_YN" in row:
        return row["PRIOR_SNAPSHOT_MISSING_YN"] == "Y"
    return row["HORSE_MATCH_STATUS_CD"] == "NO_PRIOR_SNAPSHOT"


def build_horse_dimension():
    columns = ["HR_NM", "SNAPSHOT_DT", "HR_BIRTH_DT", *HORSE_ATTRIBUTES]
    snapshots = sorted(read_clean("HR_WEEKLY_SNAPSHOT", columns), key=lambda row: (row["HR_NM"], row["SNAPSHOT_DT"]))
    versions = [{
        "HORSE_KEY": 0, "HR_NM": None, "VALID_FROM_DT": None, "VALID_TO_DT": None,
        "HR_BIRTH_DT": None, **dict.fromkeys(HORSE_ATTRIBUTES),
    }]
    previous = None
    for snapshot in snapshots:
        name = snapshot["HR_NM"]
        values = {column: snapshot[column] for column in HORSE_ATTRIBUTES}
        if previous and name == previous["HR_NM"]:
            if values == {column: previous[column] for column in HORSE_ATTRIBUTES}:
                continue
            previous["VALID_TO_DT"] = snapshot["SNAPSHOT_DT"]
        previous = {
            "HORSE_KEY": len(versions), "HR_NM": name, "VALID_FROM_DT": snapshot["SNAPSHOT_DT"] + DAY,
            "VALID_TO_DT": date.max, "HR_BIRTH_DT": snapshot["HR_BIRTH_DT"], **values,
        }
        versions.append(previous)
    schema = pa.schema([
        ("HORSE_KEY", I32), ("HR_NM", TEXT), ("VALID_FROM_DT", DATE), ("VALID_TO_DT", DATE),
        ("HR_BIRTH_DT", DATE), *((column, I32 if column == "HR_AGE" else TEXT) for column in HORSE_ATTRIBUTES),
    ])
    return pa.Table.from_pylist(versions, schema=schema)


def draft_dimensions(history):
    date_values = [row[column] for row in history for column in ("VET_DT", "REPORT_DT") if row[column] is not None]
    first, last = min(date_values), max(date_values)
    dates = [first + i * DAY for i in range((last - first).days + 1)]
    date_dimension = pa.Table.from_pylist([
        {"DATE_KEY": day.year * 10000 + day.month * 100 + day.day, "FULL_DT": day}
        for day in dates
    ], schema=pa.schema([("DATE_KEY", I32), ("FULL_DT", DATE)]))

    groups = {}
    for row in read_clean("TR_WEEKLY_SNAPSHOT", ["TR_GRP_NO", "TR_NM"]):
        number, trainer = row["TR_GRP_NO"], row["TR_NM"]
        if groups.setdefault(number, trainer) != trainer:
            raise ValueError(f"Multiple trainers for provisional group key {number}.")
    groups["88"] = None
    trainer_dimension = pa.Table.from_pylist(
        [{"TRAINER_KEY": 0, "TR_GRP_NO": None, "TR_NM": None}] + [
            {"TRAINER_KEY": i, "TR_GRP_NO": number, "TR_NM": groups[number]}
            for i, number in enumerate(sorted(groups), 1)
        ],
        schema=pa.schema([("TRAINER_KEY", I32), ("TR_GRP_NO", TEXT), ("TR_NM", TEXT)]),
    )
    age_dimension = pa.Table.from_pylist([
        {"AGE_GROUP_KEY": i, "AGE_GROUP_NM": name, "MIN_AGE": lo, "MAX_AGE": hi}
        for i, (name, lo, hi) in enumerate([
            ("UNKNOWN", None, None), ("2~3세", 2, 3), ("4~5세", 4, 5), ("6~7세", 6, 7), ("8세 이상", 8, None)
        ])
    ], schema=pa.schema([("AGE_GROUP_KEY", I32), ("AGE_GROUP_NM", TEXT), ("MIN_AGE", I32), ("MAX_AGE", I32)]))
    return {
        "DIM_DATE": date_dimension, "DIM_HORSE": build_horse_dimension(),
        "DIM_TRAINER": trainer_dimension, "DIM_AGE_GROUP": age_dimension,
    }


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


def make_fact(history, dimensions):
    dates = {row["FULL_DT"]: row["DATE_KEY"] for row in dimensions["DIM_DATE"].to_pylist()}
    groups = {row["TR_GRP_NO"]: row["TRAINER_KEY"] for row in dimensions["DIM_TRAINER"].to_pylist()}
    if len(dates) != dimensions["DIM_DATE"].num_rows or len(groups) != dimensions["DIM_TRAINER"].num_rows:
        raise ValueError("[AG-7] Duplicate date or trainer group business key.")
    ages = [row for row in dimensions["DIM_AGE_GROUP"].to_pylist() if row["AGE_GROUP_KEY"] != 0]
    horses = horse_index(dimensions["DIM_HORSE"])
    fact = []
    for row in history:
        date_of_visit = row["VET_DT"]
        horse = lookup_horse(horses, row["HR_NM"], date_of_visit)
        if (horse is None) != no_prior_snapshot(row):
            raise ValueError(f"Clean and horse dimension disagree on VET_SEQ={row['VET_SEQ']}.")
        age = horse["HR_AGE"] if horse else None
        buckets = [item["AGE_GROUP_KEY"] for item in ages
                   if age is not None and item["MIN_AGE"] <= age
                   and (item["MAX_AGE"] is None or age <= item["MAX_AGE"])]
        if len(buckets) > 1:
            raise ValueError(f"Overlapping age groups for age {age}.")
        fact.append({
            "VET_SEQ": row["VET_SEQ"], "VET_DT_KEY": dates[date_of_visit], "REPORT_DT_KEY": dates[row["REPORT_DT"]],
            "HORSE_KEY": horse["HORSE_KEY"] if horse else 0, "TRAINER_KEY": groups[row["TR_GRP_NO"]],
            "AGE_GROUP_KEY": buckets[0] if buckets else 0, "VET_CNT": 1,
        })
    return fact


def shared_dimension_issues(dimensions, history):
    problems = []
    valid = {}
    for name, columns in COMMON_COLUMNS.items():
        if name not in dimensions:
            problems.append(f"Missing {name}.parquet")
            continue
        missing = set(columns) - set(dimensions[name].column_names)
        if missing:
            problems.append(f"Missing columns in {name}: {sorted(missing)}")
        else:
            valid[name] = dimensions[name]
    if "DIM_DATE" in valid:
        dates = set(valid["DIM_DATE"]["FULL_DT"].to_pylist())
        needed = {row[key] for row in history for key in ("VET_DT", "REPORT_DT")}
        missing = needed - dates
        if missing:
            problems.append(f"DIM_DATE does not cover {len(missing)} medical event/report dates")
    if "DIM_TRAINER" in valid:
        groups = set(valid["DIM_TRAINER"]["TR_GRP_NO"].to_pylist())
        missing = {row["TR_GRP_NO"] for row in history} - groups
        if missing:
            problems.append(f"DIM_TRAINER does not cover {len(missing)} recorded medical groups")
    for name in ("DIM_HORSE", "DIM_AGE_GROUP"):
        if name in valid and 0 not in valid[name][KEYS[name]].to_pylist():
            problems.append(f"{name} is missing unknown key 0")
    return problems


def validate(fact, bridge, dimensions, history, clean_bridge):
    dimension_keys = {}
    for name, field in KEYS.items():
        values = dimensions[name][field].to_pylist()
        if None in values or len(values) != len(set(values)):
            raise ValueError(f"[AG-7] Invalid primary key in {name}.")
        dimension_keys[name] = set(values)
    sequences = {row["VET_SEQ"] for row in fact}
    if len(sequences) != len(fact) or sequences != {row["VET_SEQ"] for row in history}:
        raise ValueError("[AG-3] Gold fact must have one row per clean medical history record.")
    for key, dimension in FK.items():
        if {row[key] for row in fact} - dimension_keys[dimension]:
            raise ValueError(f"[AG-7] Unresolved Gold foreign key: {key}")
    bridge_keys = {(row["VET_SEQ"], row["VET_TYPE_KEY"]) for row in bridge}
    if len(bridge_keys) != len(bridge) or {sequence for sequence, _ in bridge_keys} != sequences:
        raise ValueError("[AG-7] Gold bridge primary or history key is invalid.")
    if {key for _, key in bridge_keys} - dimension_keys["DIM_VET_TYPE"]:
        raise ValueError("[AG-7] Unresolved Gold veterinary type key.")
    if len(bridge) != len(clean_bridge) or sum(r["HORSE_KEY"] == 0 for r in fact) != sum(map(no_prior_snapshot, history)):
        raise ValueError("[AG-3] Gold medical totals differ from the clean quality results.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--common-dims", type=Path, help="Directory with the team's four agreed common dimensions")
    parser.add_argument("--clean-version", help="Team-approved clean manifest CLEAN_VERSION")
    args = parser.parse_args()
    if args.common_dims and not args.clean_version:
        parser.error("--common-dims requires the team-approved --clean-version.")
    clean_version = read_clean_manifest(args.clean_version)
    history = read_clean("HR_VET_HIST")
    clean_bridge = read_clean("HR_VET_TYPE_BRIDGE")
    common_hashes = {}
    if args.common_dims:
        paths = {name: args.common_dims / f"{name}.parquet" for name in COMMON_COLUMNS}
        dimensions = {}
        for name, path in paths.items():
            if not path.is_file():
                continue
            content = path.read_bytes()
            common_hashes[path.name] = hashlib.sha256(content).hexdigest()
            dimensions[name] = pq.read_table(pa.BufferReader(content))
        problems = shared_dimension_issues(dimensions, history)
        if problems:
            raise ValueError("[D-010] " + "; ".join(problems))
    else:
        dimensions = draft_dimensions(history)

    names = sorted({row["VET_TYPE_NM"] for row in clean_bridge})
    type_keys = {label: i for i, label in enumerate(names, 1)}
    dimensions["DIM_VET_TYPE"] = pa.Table.from_pylist(
        [{"VET_TYPE_KEY": key, "VET_TYPE_NM": label} for label, key in type_keys.items()],
        schema=pa.schema([("VET_TYPE_KEY", I32), ("VET_TYPE_NM", TEXT)]),
    )
    fact = make_fact(history, dimensions)
    bridge = [{"VET_SEQ": row["VET_SEQ"], "VET_TYPE_KEY": type_keys[row["VET_TYPE_NM"]]} for row in clean_bridge]
    validate(fact, bridge, dimensions, history, clean_bridge)

    output = GOLD_DIR / ("horse_medical" if args.common_dims else "horse_medical_draft")
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        **dimensions, "FCT_HORSE_MEDICAL": pa.Table.from_pylist(fact, schema=FACT_SCHEMA),
        "BRIDGE_HR_VET_TYPE": pa.Table.from_pylist(bridge, schema=BRIDGE_SCHEMA),
    }
    for name, table in tables.items():
        pq.write_table(table, output / f"{name}.parquet")
    (output / "DIM_TR_GRP.parquet").unlink(missing_ok=True)
    report = {
        "STATUS": "SHARED_DIMENSIONS" if args.common_dims else "DRAFT_DIMENSIONS",
        "CLEAN_VERSION": clean_version, "COMMON_DIMENSION_SOURCE_SHA256": common_hashes,
        "TABLE_ROWS": {name: table.num_rows for name, table in tables.items()},
        "VET_CNT_SUM": sum(row["VET_CNT"] for row in fact),
        "NO_PRIOR_SNAPSHOT_ROWS": sum(row["HORSE_KEY"] == 0 for row in fact),
        "PK_DUPLICATES": 0, "UNRESOLVED_FOREIGN_KEYS": 0,
    }
    (output / "_manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{output.relative_to(C.ROOT)}: {len(fact):,} medical records and {len(bridge):,} type links")


if __name__ == "__main__":
    main()
