"""Bronze 검증: 원천 행 수 = Bronze 행 수, 원천 값 그대로 적재, 메타 컬럼, 원천 파일 무변경."""
import importlib
import sys

import pandas as pd

import config as C

bronze = importlib.import_module("01_bronze")


def main():
    log = bronze.load_log()
    ok = True
    print(f"{'원천 파일':<36} {'원천':>8} {'Bronze':>8} {'일치':>4} {'값동일':>6} {'해시':>4}")
    for src in C.SOURCES:
        path = C.ORIGIN_DIR / src["file"]
        b = pd.read_parquet(C.BRONZE_DIR / f"{src['bronze']}.parquet")
        n_src = bronze.count_source_rows(path, src["format"])
        same_rows = n_src == len(b)

        # 원천을 다시 읽어 메타 컬럼을 뺀 값이 그대로인지
        raw = bronze.read_source(path, src["format"])
        same_vals = raw.equals(b.drop(columns=bronze.META_COLS))

        meta_ok = (
            all(c in b.columns for c in bronze.META_COLS)
            and (b["_SRC_SYSTEM"] == src["system"]).all()
            and (b["_LOAD_FILE"] == src["file"]).all()
            and b["_LOAD_DTM"].nunique() == 1
            and b["_SRC_ROW_NO"].tolist() == list(range(1, len(b) + 1))
        )
        # 원천 파일이 적재 당시와 같은지 (원천 무변경 확인)
        logged = log[(log.LOAD_FILE == src["file"]) & (log.LOAD_DTM == b["_LOAD_DTM"].iloc[0])]
        hash_ok = len(logged) == 1 and logged.iloc[0].SHA256 == bronze.sha256(path)

        row_ok = same_rows and same_vals and meta_ok and hash_ok
        ok &= row_ok
        print(f"{src['file']:<36} {n_src:>8,} {len(b):>8,} {'O' if same_rows else 'X':>4} "
              f"{'O' if same_vals else 'X':>6} {'O' if hash_ok else 'X':>4}"
              + ("" if meta_ok else "  ← 메타 컬럼 이상"))
    print("Bronze 검증:", "통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
