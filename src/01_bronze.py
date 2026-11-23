"""원천(00_origin) → Bronze(01_bronze) 적재.

- 원천은 읽기만 한다. 값은 전부 문자열 그대로 적재한다 (빈 칸도 빈 문자열 그대로).
- 메타 컬럼: _SRC_SYSTEM, _LOAD_FILE, _LOAD_DTM, _SRC_ROW_NO(원천 데이터 행 번호, 1부터)
- _LOAD_DTM은 meta/bronze_load_log.csv에 원천 파일 해시와 함께 기록한다.
  같은 해시의 파일을 다시 적재하면 기록된 _LOAD_DTM을 재사용하므로 재실행해도 같은 파일이 나온다.
  원천 파일 내용이 바뀌면 새 _LOAD_DTM으로 적재하고 로그에 한 줄 추가한다.
"""
import csv
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import config as C

META_COLS = ["_SRC_SYSTEM", "_LOAD_FILE", "_LOAD_DTM", "_SRC_ROW_NO"]
LOG_COLS = ["LOAD_FILE", "SRC_SYSTEM", "SHA256", "ROW_CNT", "LOAD_DTM", "BRONZE_FILE"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_source(path, fmt):
    if fmt == "csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding=C.CSV_ENCODING)
    if fmt == "jsonl":
        with open(path, encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f if line.strip()]
        for i, line in enumerate(lines, 1):
            json.loads(line)  # 깨진 줄이 있으면 여기서 멈춘다
        return pd.DataFrame({"RAW_JSON": lines}, dtype=str)
    raise ValueError(f"지원하지 않는 형식: {fmt}")


def count_source_rows(path, fmt):
    """pandas와 별개로 원천 행 수를 센다 (검증용)."""
    if fmt == "csv":
        with open(path, encoding=C.CSV_ENCODING, newline="") as f:
            return sum(1 for _ in csv.reader(f)) - 1
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def load_log():
    if C.BRONZE_LOAD_LOG.exists():
        return pd.read_csv(C.BRONZE_LOAD_LOG, dtype=str, keep_default_na=False)
    return pd.DataFrame(columns=LOG_COLS)


def main():
    C.BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    C.META_DIR.mkdir(parents=True, exist_ok=True)
    log = load_log()
    now = datetime.now(ZoneInfo(C.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
    results = []

    for src in C.SOURCES:
        path = C.ORIGIN_DIR / src["file"]
        digest = sha256(path)
        hit = log[(log.LOAD_FILE == src["file"]) & (log.SHA256 == digest)]
        if len(hit):
            load_dtm = hit.iloc[0].LOAD_DTM
        else:
            load_dtm = now

        df = read_source(path, src["format"])
        df["_SRC_SYSTEM"] = src["system"]
        df["_LOAD_FILE"] = src["file"]
        df["_LOAD_DTM"] = load_dtm
        df["_SRC_ROW_NO"] = range(1, len(df) + 1)
        df["_SRC_ROW_NO"] = df["_SRC_ROW_NO"].astype("int64")

        out = C.BRONZE_DIR / f"{src['bronze']}.parquet"
        df.to_parquet(out, index=False)

        if not len(hit):
            log = pd.concat([log, pd.DataFrame([{
                "LOAD_FILE": src["file"], "SRC_SYSTEM": src["system"], "SHA256": digest,
                "ROW_CNT": str(len(df)), "LOAD_DTM": load_dtm,
                "BRONZE_FILE": out.relative_to(C.ROOT).as_posix(),
            }])], ignore_index=True)
        results.append((src["file"], len(df), "재사용" if len(hit) else "신규"))

    log[LOG_COLS].to_csv(C.BRONZE_LOAD_LOG, index=False)
    for file, n, kind in results:
        print(f"{file:<36} {n:>8,}행  _LOAD_DTM {kind}")


if __name__ == "__main__":
    main()
