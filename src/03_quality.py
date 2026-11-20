"""Silver 표준화 결과(02_silver/*.parquet) → 품질 관리 → 02_silver/clean/ + 02_silver/_excluded/

근거: meta/decision_log.md (D-001 ~ D-012)
- 표준화 결과는 읽기만 한다 (D-008). 결과는 clean/(유지 행 + 표시 컬럼)과 _excluded/(제외 행)에 따로 쓴다.
- 처리 순서 (D-001): 완전 중복 제거 → 나머지 규칙 측정. 집계별 제외 조건은 Gold에서 적용한다.
- 처리한 행은 전부 meta/dq_log.csv에 규칙 ID·결정 ID·Bronze 경로·_SRC_ROW_NO와 함께 남긴다 (D-009).
- 규칙별 결과는 meta/dq_result.csv, 보고서는 docs/품질관리.md (재실행해도 같은 내용).
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config as C

BRONZE_PATH = {t: f"data/01_bronze/{b}.parquet" for t, b in C.SILVER_FROM_BRONZE.items()}
TABLES = list(C.EXPECTED_SILVER_ROWS)
ACTION_KO = {"EXCLUDE": "제외", "FLAG": "표시", "FIX": "보정", "CHECK": "확인"}
DIM_KO = {"U": "유일성", "C": "완전성", "V": "유효성", "S": "일관성", "R": "참조 무결성", "T": "시점"}
MERGE_VET_NAMES = {"일,열사병": "일·열사병"}  # D-011

LOG, RESULTS = [], []


# ---------------------------------------------------------------- 기록 도구
def log(table, rows, rule, decision, action, col="", before="", after="", note=""):
    """rows: _SRC_ROW_NO를 가진 DataFrame. before/after는 같은 길이의 값 목록 또는 하나의 값."""
    if len(rows) == 0:
        return
    n = len(rows)
    LOG.append(pd.DataFrame({
        "TABLE_NM": table, "BRONZE_FILE": BRONZE_PATH[table], "SRC_ROW_NO": rows["_SRC_ROW_NO"].astype("int64").values,
        "RULE_ID": rule, "DECISION_ID": decision, "ACTION": action, "COL_NM": col,
        "BEFORE_VAL": before if not isinstance(before, (list, pd.Series)) else [str(x) for x in before],
        "AFTER_VAL": after if not isinstance(after, (list, pd.Series)) else [str(x) for x in after],
        "NOTE": [note] * n,
    }))


def result(rule, table, desc, action, decision, final_rows, target_rows, bronze="", std="", note=""):
    """final_rows: 최종(중복 제거 후) 위반 행 DataFrame (예시 행 번호를 뽑는 데 씀)."""
    ex = sorted(final_rows["_SRC_ROW_NO"].astype("int64").tolist())[:3] if len(final_rows) else []
    RESULTS.append({
        "RULE_ID": rule, "DIM": DIM_KO[rule[3]], "TABLE_NM": table, "RULE_DESC": desc, "ACTION": action,
        "DECISION_ID": decision, "BRONZE_CNT": bronze, "SILVER_STD_CNT": std, "FINAL_CNT": len(final_rows),
        "TARGET_ROWS": target_rows, "EXAMPLE_ROWS": ", ".join(map(str, ex)), "NOTE": note,
    })


def yn(mask):
    return pd.Series(mask).map({True: "Y", False: "N"}).values


# ---------------------------------------------------------------- 측정 함수 (표준화 직후·중복 제거 후 양쪽에 씀)
def biz_cols(df):
    return [c for c in df.columns if not c.startswith("_")]


def zero_ticket(t):
    return t["BET_AMT"].eq(0)


def ticket_context(t, o, race):
    """마권별 전표 종류·전표 시각·그 마권 경주의 출발 시각 (행 순서 유지)."""
    x = t[["ORDER_NO", "RC_DT", "RC_NO"]].reset_index(drop=True)
    x = x.merge(o[["ORDER_NO", "ORDER_TYPE_CD", "SALE_DTM"]], on="ORDER_NO", how="left")
    x = x.merge(race[["RC_DT", "RC_NO", "START_DTM"]], on=["RC_DT", "RC_NO"], how="left")
    x.index = t.index
    return x


def late_cancel_ticket(t, o, race):
    x = ticket_context(t, o, race)
    return x["ORDER_TYPE_CD"].eq("CANCEL") & (x["SALE_DTM"] >= x["START_DTM"])


def header_mismatch(t, o):
    g = t.groupby("ORDER_NO").agg(A=("BET_AMT", "sum"), N=("BET_AMT", "size"))
    j = o[["ORDER_NO", "TOTAL_AMT", "TICKET_CNT"]].merge(g, left_on="ORDER_NO", right_index=True, how="left")
    j.index = o.index
    return (j["TOTAL_AMT"] != j["A"]) | (j["TICKET_CNT"] != j["N"])


def first_format_mismatch(dic, bronze):
    """V01 Bronze 측정: 형식이 여러 개인 날짜 컬럼에서 첫 번째(주된) 형식이 아닌 원천값 수."""
    total, parts = 0, []
    for r in dic[dic.DATA_TYPE.isin(["DATE", "TIMESTAMP"])].itertuples():
        fmts = [f.strip() for f in r.RULE.replace("형식 ", "").replace(" 순서로 시도", "").split(" → ")]
        b = bronze.get(C.SILVER_FROM_BRONZE[r.TABLE_NM])
        if len(fmts) < 2 or b is None or r.SRC_COL not in b.columns:
            continue
        s = b[r.SRC_COL].str.strip()
        s = s[s.ne("")]
        n = int(pd.to_datetime(s, format=fmts[0], errors="coerce").isna().sum())
        total += n
        parts.append(f"{r.TABLE_NM}.{r.COL_NM} {n:,}")
    return total, "; ".join(parts)


# ---------------------------------------------------------------- 출력 도구 (스키마 유지)
def take(table_pa, positions):
    return table_pa.take(pa.array(positions, type=pa.int64()))


def with_flags(table_pa, flags):
    """flags: {컬럼: Y/N 배열}. _SRC_ROW_NO 앞에 붙인다."""
    cols = [c for c in table_pa.column_names if c != "_SRC_ROW_NO"]
    out = table_pa.select(cols)
    for name, vals in flags.items():
        out = out.append_column(name, pa.array(list(vals), pa.string()))
    return out.append_column("_SRC_ROW_NO", table_pa.column("_SRC_ROW_NO"))


def replace_col(table_pa, name, values):
    i = table_pa.column_names.index(name)
    return table_pa.set_column(i, name, pa.array(list(values), table_pa.schema.field(name).type))


def with_lineage(table_pa, name):
    size = table_pa.num_rows
    return with_flags(table_pa, {
        "_SRC_FILE": [f"{C.SILVER_FROM_BRONZE[name]}.parquet"] * size,
        "BRONZE_PATH": [BRONZE_PATH[name]] * size,
        "DQ_RULE_ID": ["DQ-U01"] * size,
        "DQ_DECISION_ID": ["D-001"] * size,
    })


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_clean_manifest() -> dict:
    silver = {path.name: path for path in C.SILVER_DIR.glob("*.parquet")}
    clean = {path.name: path for path in C.CLEAN_DIR.glob("*.parquet")}
    if not silver or silver.keys() != clean.keys():
        raise ValueError("Standardized and clean Silver table sets differ.")
    excluded = {path.name: path for path in C.EXCLUDED_DIR.glob("*.parquet")}
    for outputs in (clean, excluded):
        for name, path in outputs.items():
            input_schema = pq.read_schema(silver[name])
            output_schema = pq.read_schema(path)
            for field in input_schema:
                if field.name not in output_schema.names or output_schema.field(field.name).type != field.type:
                    raise ValueError(f"{path}: incompatible Silver column {field.name}")
    hashes = {name: _sha256(path) for name, path in clean.items()}
    return {
        "CLEAN_VERSION": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "INPUT_SHA256": {name: _sha256(path) for name, path in silver.items()},
        "CLEAN_SHA256": hashes,
        "EXCLUDED_SHA256": {name: _sha256(path) for name, path in excluded.items()},
        "CLEAN_ROWS": {name: pq.read_metadata(path).num_rows for name, path in clean.items()},
    }


def _write_clean_manifest() -> None:
    data = json.dumps(build_clean_manifest(), sort_keys=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=C.CLEAN_DIR, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, C.CLEAN_DIR / "_manifest.json")
    finally:
        temporary.unlink(missing_ok=True)


# ---------------------------------------------------------------- 본 처리
def main():
    LOG.clear()
    RESULTS.clear()
    C.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    C.EXCLUDED_DIR.mkdir(parents=True, exist_ok=True)
    pa_std = {t: pq.read_table(C.SILVER_DIR / f"{t}.parquet") for t in TABLES}
    std = {t: pa_std[t].to_pandas() for t in TABLES}
    bronze = {b: pd.read_parquet(C.BRONZE_DIR / f"{b}.parquet") for b in set(C.SILVER_FROM_BRONZE.values())}
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    issues = pd.read_csv(C.SILVER_ISSUE_LOG, dtype=str, keep_default_na=False)
    vmap = pd.read_csv(C.SILVER_VALUE_MAP, dtype=str, keep_default_na=False)

    o, race, entry, res = std["BET_ORDER"], std["RC_RACE"], std["RC_ENTRY"], std["RC_RESULT"]
    bt_raw = bronze["bet_ticket"]

    # ---- 1단계: 완전 중복 제거 (D-001, D-002) ----
    t_std = std["BET_TICKET"]
    order = t_std.sort_values("_SRC_ROW_NO", kind="stable")  # 한 파일 안이라 Bronze 경로 동률은 생기지 않음
    dup = order.duplicated(biz_cols(t_std), keep="first")
    dup_rows = order[dup]
    keep_of = order[~dup].assign(_K=lambda d: d.groupby(biz_cols(t_std), dropna=False).ngroup())
    kept_no = (order.assign(_K=order.groupby(biz_cols(t_std), dropna=False).ngroup())
               .merge(keep_of[["_K", "_SRC_ROW_NO"]].rename(columns={"_SRC_ROW_NO": "KEPT"}), on="_K")
               .set_index("_SRC_ROW_NO")["KEPT"])
    t = t_std.loc[~t_std["_SRC_ROW_NO"].isin(dup_rows["_SRC_ROW_NO"])]
    log("BET_TICKET", dup_rows, "DQ-U01", "D-002", "EXCLUDE", note="완전 중복. 같은 업무값 중 _SRC_ROW_NO 최소 행 유지",
        before="", after=[f"유지 행 {kept_no[n]}" for n in dup_rows["_SRC_ROW_NO"]])
    result("DQ-U01", "BET_TICKET", "완전 중복 행 (추적 컬럼 제외 업무값 기준, 최소 행 번호 외)", "EXCLUDE", "D-002",
           dup_rows, len(t_std), bronze=int(bt_raw.duplicated(biz_cols(bt_raw)).sum()), std=int(dup.sum()),
           note="FINAL_CNT = 제외한 행 수 (기준 1,052)")

    # ---- 2단계: 나머지 규칙 측정 (모두 중복 제거 후 t 기준) ----
    pk2 = t.duplicated(["ORDER_NO", "TICKET_SEQ"], keep=False)
    result("DQ-U02", "BET_TICKET", "PK(전표번호 + 마권 순번)가 중복된 행", "CHECK", "D-002", t[pk2], len(t),
           bronze=int(bt_raw.duplicated(["order_no", "ticket_seq"], keep=False).sum()),
           std=int(t_std.duplicated(["ORDER_NO", "TICKET_SEQ"], keep=False).sum()), note="중복된 두 행 모두 셈")

    pks = {"BET_ORDER": ["ORDER_NO"], "MBR_MASTER": ["MBR_NO"], "HR_WEEKLY_SNAPSHOT": ["SNAPSHOT_DT", "HR_NM"],
           "TR_WEEKLY_SNAPSHOT": ["SNAPSHOT_DT", "TR_NM"], "RC_RACE": ["RC_DT", "RC_NO"],
           "RC_ENTRY": ["RC_DT", "RC_NO", "CHUL_NO"], "RC_ODDS": ["RC_DT", "RC_NO", "CHUL_NO"],
           "RC_RESULT": ["RC_DT", "RC_NO", "CHUL_NO"], "RC_SALES": ["RC_DT", "RC_NO", "BET_TYPE_CD"],
           "RC_SALES_TOTAL": ["RC_DT", "RC_NO"], "HR_VET_HIST": ["VET_SEQ"], "RC_CHANGE_EVENT": ["_SRC_ROW_NO"]}
    pk_bad = pd.concat([std[tb][std[tb].duplicated(k, keep=False)] for tb, k in pks.items()])
    result("DQ-U03", "그 외 12개 테이블", "테이블별 PK가 중복된 행 (" + ", ".join(f"{tb}({'+'.join(k)})" for tb, k in pks.items()) + ")",
           "CHECK", "D-001", pk_bad, sum(len(std[tb]) for tb in pks), std=len(pk_bad))

    # C01 마명 빈칸 → 출전표로 보정 (D-005)
    k3 = ["RC_DT", "RC_NO", "CHUL_NO"]
    ent_nm = entry.groupby(k3).HR_NM.agg(["first", "size"])
    blank = t["HR_NM"].isna()
    look = t.loc[blank, k3].merge(ent_nm, left_on=k3, right_index=True, how="left")
    look.index = t.index[blank]
    fillable = look["size"].eq(1)
    filled_idx = look.index[fillable]
    t = t.copy()
    t.loc[filled_idx, "HR_NM"] = look.loc[filled_idx, "first"].values
    hr_filled = t.index.isin(filled_idx)
    log("BET_TICKET", t.loc[filled_idx], "DQ-C01", "D-005", "FIX", col="HR_NM", before="", after=t.loc[filled_idx, "HR_NM"],
        note="RC_DT + RC_NO + CHUL_NO로 RC_ENTRY 1행에 연결된 마명")
    result("DQ-C01", "BET_TICKET", "마명 빈칸 (마번은 있음)", "FIX", "D-005", t.loc[filled_idx], len(t),
           bronze=int(bt_raw["hr_name"].str.strip().eq("").sum()), std=int(t_std["HR_NM"].isna().sum()),
           note=f"보정 {len(filled_idx):,} / 연결 안 됨 {int((~fillable).sum()):,} → HR_NM_FILLED_YN")

    # V01 날짜 형식, V02 코드 (표준화 전후 비교)
    b_v01, v01_note = first_format_mismatch(dic, bronze)
    dt_cols = set(dic[dic.DATA_TYPE.isin(["DATE", "TIMESTAMP", "TIME"])][["TABLE_NM", "COL_NM"]].itertuples(index=False, name=None))
    is_dt = pd.Series([(a, b) in dt_cols for a, b in zip(issues.TABLE_NM, issues.COL_NM)], index=issues.index, dtype=bool)
    pf = issues[(issues.ISSUE_CD == "PARSE_FAIL") & is_dt]
    result("DQ-V01", "날짜·일시 컬럼 전체", "날짜·일시 형식 불일치 (Bronze: 주된 형식이 아닌 원천값 / Silver: 변환 실패)", "CHECK", "MR-5",
           pd.DataFrame({"_SRC_ROW_NO": pf.SRC_ROW_NO.astype("int64")}), sum(len(std[x]) for x in TABLES),
           bronze=b_v01, std=len(pf), note=v01_note)
    changed = vmap[(vmap.RAW_VAL != vmap.STD_VAL) & ~((vmap.RAW_VAL == "(NULL)") & (vmap.STD_VAL == "(NULL)"))]
    ooc = issues[issues.ISSUE_CD == "OUT_OF_CODE"]
    result("DQ-V02", "코드 컬럼 전체", "표준 코드가 아닌 값 (Bronze: 원천값 ≠ 표준코드 / Silver: 코드표 밖 값)", "CHECK", "MR-6",
           pd.DataFrame({"_SRC_ROW_NO": ooc.SRC_ROW_NO.astype("int64")}), sum(len(std[x]) for x in TABLES),
           bronze=int(changed.CNT.astype(int).sum()), std=len(ooc))

    # V03 0원 마권 (D-003)
    inv = zero_ticket(t)
    log("BET_TICKET", t[inv], "DQ-V03", "D-003", "FLAG", col="INVALID_YN", after="Y", note="마권 최소 100원. 업무 집계 제외, 오류 집계 포함")
    result("DQ-V03", "BET_TICKET", "0원 마권", "FLAG", "D-003", t[inv], len(t),
           bronze=int(bt_raw["bet_amt"].str.strip().eq("0").sum()), std=int(zero_ticket(t_std).sum()),
           note="상태별 " + ", ".join(f"{k} {v:,}" for k, v in t[inv].TICKET_STAT_CD.value_counts().sort_index().items()) + " → INVALID_YN")

    v04 = t["BET_AMT"] != t["UNIT_CNT"] * 100
    result("DQ-V04", "BET_TICKET", "금액 ≠ 구좌 수 × 100", "CHECK", "MR-8", t[v04], len(t),
           bronze=int((bt_raw.bet_amt.astype(int) != bt_raw.ticket_cnt.astype(int) * 100).sum()),
           std=int((t_std.BET_AMT != t_std.UNIT_CNT * 100).sum()))

    # S01 전표·마권 불일치 (D-006)
    hm = header_mismatch(t, o)
    log("BET_ORDER", o[hm], "DQ-S01", "D-006", "FLAG", col="HEADER_MISMATCH_YN", after="Y", note="전표 장수·총액 ≠ 마권 개수·합계. 고치지 않음")
    result("DQ-S01", "BET_ORDER ↔ BET_TICKET", "전표의 장수·총액 ≠ 마권 개수·합계", "FLAG", "D-006", o[hm], len(o),
           std=int(header_mismatch(t_std, o).sum()), note="→ HEADER_MISMATCH_YN")

    tt = t.reset_index(drop=True).merge(o[["ORDER_NO", "ORDER_TYPE_CD"]], on="ORDER_NO", how="left")
    s02 = (tt.ORDER_TYPE_CD.eq("CANCEL") != tt.TICKET_STAT_CD.eq("CANCEL"))
    result("DQ-S02", "BET_TICKET ↔ BET_ORDER", "전표 종류와 마권 상태가 안 맞음 (취소 전표인데 CANCEL이 아니거나, 구매 전표인데 CANCEL)", "CHECK", "D-001", tt[s02], len(t))

    sa, st_ = std["RC_SALES"], std["RC_SALES_TOTAL"]
    g = sa.groupby(["RC_DT", "RC_NO"]).SALES_AMT.sum().rename("S").reset_index().merge(st_, on=["RC_DT", "RC_NO"], how="outer")
    result("DQ-S03", "RC_SALES ↔ RC_SALES_TOTAL", "승식별 매출 합 ≠ 경주 합계 (합계 테이블은 대사용)", "CHECK", "MR-3",
           g[g.S != g.SALES_AMT].fillna({"_SRC_ROW_NO": -1}), len(st_))

    # 진료: 진료일 이전(엄격) 최근 스냅샷 (D-007)
    vet = std["HR_VET_HIST"]
    snap = std["HR_WEEKLY_SNAPSHOT"][["HR_NM", "SNAPSHOT_DT", "TR_GRP_NO"]].assign(D=lambda d: pd.to_datetime(d.SNAPSHOT_DT))
    vv = vet.assign(D=pd.to_datetime(vet.VET_DT), _ORD=range(len(vet))).sort_values("D", kind="stable")
    mm = pd.merge_asof(vv, snap.sort_values("D")[["HR_NM", "D", "TR_GRP_NO"]], on="D", by="HR_NM",
                       allow_exact_matches=False, suffixes=("", "_SNAP")).sort_values("_ORD")
    mm.index = vet.index
    no_snap = mm["TR_GRP_NO_SNAP"].isna()
    grp_bad = ~no_snap & (mm["TR_GRP_NO"] != mm["TR_GRP_NO_SNAP"])
    log("HR_VET_HIST", vet[grp_bad], "DQ-S04", "D-007", "FLAG", col="TR_GRP_MISMATCH_YN", before=vet.loc[grp_bad, "TR_GRP_NO"],
        after=mm.loc[grp_bad, "TR_GRP_NO_SNAP"], note="BEFORE=진료 기록의 조, AFTER=직전 스냅샷의 조 (값은 바꾸지 않음)")
    result("DQ-S04", "HR_VET_HIST ↔ HR_WEEKLY_SNAPSHOT", "진료 기록의 조 ≠ 진료일 직전 스냅샷의 조", "FLAG", "D-007", vet[grp_bad], len(vet),
           note="직전 스냅샷이 없는 행은 제외하고 비교 → TR_GRP_MISMATCH_YN")

    res_nm = entry[k3 + ["HR_NM"]].merge(res[k3 + ["HR_NM", "_SRC_ROW_NO"]], on=k3, suffixes=("", "_R"))
    s05 = res_nm[res_nm.HR_NM != res_nm.HR_NM_R]
    result("DQ-S05", "RC_ENTRY ↔ RC_RESULT", "같은 출전 키인데 출전표와 결과표의 마명이 다름", "CHECK", "D-001", s05, len(entry))

    t_orig = t[~hr_filled]
    x6 = t_orig[k3 + ["HR_NM", "_SRC_ROW_NO"]].merge(entry[k3 + ["HR_NM"]], on=k3, how="left", suffixes=("", "_E"))
    s06 = x6[x6.HR_NM.notna() & (x6.HR_NM != x6.HR_NM_E)]
    result("DQ-S06", "BET_TICKET ↔ RC_ENTRY", "원래 마명이 있는 마권의 마명 ≠ 출전표 마명 (C01 보정의 전제)", "CHECK", "D-005", s06, len(t_orig))

    stat = res.set_index(k3)["ENTRY_STAT_CD"]
    s1 = pd.Series(stat.reindex(pd.MultiIndex.from_frame(t[k3])).values, index=t.index)
    k3b = t[["RC_DT", "RC_NO", "CHUL_NO2"]].rename(columns={"CHUL_NO2": "CHUL_NO"})
    s2 = pd.Series(stat.reindex(pd.MultiIndex.from_frame(k3b)).values, index=t.index)
    not_ran = s1.ne("RAN") | (t.CHUL_NO2.notna() & s2.ne("RAN"))
    s07 = t[t.TICKET_STAT_CD.eq("VOID") & ~not_ran]
    s08 = t[t.TICKET_STAT_CD.eq("SOLD") & not_ran]
    result("DQ-S07", "BET_TICKET ↔ RC_RESULT", "무효(VOID) 마권인데 고른 말이 모두 출주함", "CHECK", "D-001", s07,
           int(t.TICKET_STAT_CD.eq("VOID").sum()))
    result("DQ-S08", "BET_TICKET ↔ RC_RESULT", "정상(SOLD) 마권인데 고른 말 중 뛰지 않은 말이 있음", "CHECK", "D-001", s08,
           int(t.TICKET_STAT_CD.eq("SOLD").sum()))

    # S09 진료명 통합 (D-011): 브리지에서 나뉜 진료명을 한 유형으로
    br = std["HR_VET_TYPE_BRIDGE"]
    merge_seq = vet.loc[vet.VET_NM.isin(MERGE_VET_NAMES), ["VET_SEQ", "VET_NM"]]
    br_rows_merge = br[br.VET_SEQ.isin(merge_seq.VET_SEQ)]
    first_pos = br_rows_merge.groupby("VET_SEQ").head(1).index
    drop_pos = br_rows_merge.index.difference(first_pos)
    new_name = br.loc[first_pos, "VET_SEQ"].map(dict(zip(merge_seq.VET_SEQ, merge_seq.VET_NM.map(MERGE_VET_NAMES))))
    log("HR_VET_TYPE_BRIDGE", br_rows_merge, "DQ-S09", "D-011", "FIX", col="VET_TYPE_NM",
        before=br_rows_merge.VET_TYPE_NM,
        after=[new_name[i] if i in first_pos else "(통합되어 행 없음)" for i in br_rows_merge.index],
        note="원문 HR_VET_HIST.VET_NM은 그대로 보존")
    result("DQ-S09", "HR_VET_TYPE_BRIDGE", "쉼표로 잘못 나뉜 진료명 통합 ('일,열사병' → '일·열사병')", "FIX", "D-011",
           br.loc[first_pos], len(br),
           note=f"진료 기록 {len(merge_seq)}건, 브리지 {len(br):,} → {len(br) - len(drop_pos):,}행")

    # R01 ~ R05
    miss1 = s1.isna()
    miss2 = t.CHUL_NO2.notna() & s2.isna()
    result("DQ-R01", "BET_TICKET → RC_ENTRY", "마권의 경주 + 마번(복승 두 번째 말 포함)이 출전표에 없음", "CHECK", "D-001",
           t[miss1 | miss2], len(t))
    m = std["MBR_MASTER"]
    r02 = o[o.MBR_NO.notna() & ~o.MBR_NO.isin(m.MBR_NO)]
    result("DQ-R02", "BET_ORDER → MBR_MASTER", "전표의 회원번호가 회원 마스터에 없음", "CHECK", "D-001", r02, int(o.MBR_NO.notna().sum()))
    is_cancel = o.ORDER_TYPE_CD.eq("CANCEL")
    orig_missing = is_cancel & o.ORIG_ORDER_NO.isna()
    log("BET_ORDER", o[orig_missing], "DQ-R03", "D-006", "FLAG", col="ORIG_MISSING_YN", after="Y", note="취소 전표에 원전표번호 없음. 추정 연결하지 않음")
    result("DQ-R03", "BET_ORDER", "취소 전표에 원전표번호가 없음", "FLAG", "D-006", o[orig_missing], int(is_cancel.sum()), note="→ ORIG_MISSING_YN")
    sales_no = set(o.loc[o.ORDER_TYPE_CD.eq("SALE"), "ORDER_NO"])
    r04 = o[is_cancel & o.ORIG_ORDER_NO.notna() & ~o.ORIG_ORDER_NO.isin(sales_no)]
    result("DQ-R04", "BET_ORDER", "원전표번호가 구매 전표를 가리키지 않음", "CHECK", "D-001", r04, int((is_cancel & o.ORIG_ORDER_NO.notna()).sum()))
    log("HR_VET_HIST", vet[no_snap], "DQ-R05", "D-007", "FLAG", col="PRIOR_SNAPSHOT_MISSING_YN", after="Y",
        note="진료일 이전 말 스냅샷 없음. 말 연결은 확인 필요")
    result("DQ-R05", "HR_VET_HIST → HR_WEEKLY_SNAPSHOT", "진료일 이전(엄격) 말 스냅샷이 없음", "FLAG", "D-007", vet[no_snap], len(vet),
           note="→ PRIOR_SNAPSHOT_MISSING_YN")

    # T01 ~ T04
    ctx = ticket_context(t, o, race)
    t01 = t[ctx.ORDER_TYPE_CD.eq("SALE") & (ctx.SALE_DTM >= ctx.START_DTM)]
    result("DQ-T01", "BET_TICKET + BET_ORDER + RC_RACE", "구매 시각 ≥ 그 마권 경주의 출발 시각", "CHECK", "D-001", t01,
           int(ctx.ORDER_TYPE_CD.eq("SALE").sum()))
    late_t = late_cancel_ticket(t, o, race)
    late_orders = set(t.loc[late_t, "ORDER_NO"])
    late_o = o.ORDER_NO.isin(late_orders)
    log("BET_TICKET", t[late_t], "DQ-T02", "D-004", "FLAG", col="LATE_CANCEL_YN", after="Y", note="취소 시각 ≥ 마권 경주 출발 시각")
    log("BET_ORDER", o[late_o], "DQ-T03", "D-004", "FLAG", col="LATE_CANCEL_YN", after="Y", note="전표 안에 늦은 취소 마권이 하나 이상")
    zero_late_tickets = late_t & inv
    zero_late_orders = o.ORDER_NO.isin(t.loc[zero_late_tickets, "ORDER_NO"])
    zero_late = int(zero_late_tickets.sum())
    result("DQ-T02", "BET_TICKET", "늦은 취소: 취소 시각 ≥ 그 마권 경주의 출발 시각 (마권)", "FLAG", "D-004", t[late_t],
           int(ctx.ORDER_TYPE_CD.eq("CANCEL").sum()), std=int(late_cancel_ticket(t_std, o, race).sum()),
           note=f"그중 0원 늦은 취소 {zero_late:,} → LATE_CANCEL_YN")
    all_late = t.assign(L=late_t).loc[t.ORDER_NO.isin(late_orders)].groupby("ORDER_NO").L.all()
    result("DQ-T03", "BET_ORDER", "늦은 취소 마권이 있는 전표 (고유 전표 수)", "FLAG", "D-004", o[late_o], int(is_cancel.sum()),
           std=int(o.ORDER_NO.isin(set(t_std.loc[late_cancel_ticket(t_std, o, race), "ORDER_NO"])).sum()),
           note=f"전부 늦은 취소 {int(all_late.sum()):,} / 일부만 {int((~all_late).sum()):,} → LATE_CANCEL_YN")
    t04 = vet[pd.to_datetime(vet.REPORT_DT) < pd.to_datetime(vet.VET_DT)]
    result("DQ-T04", "HR_VET_HIST", "보고일 < 진료일", "CHECK", "D-001", t04, len(vet))

    # ---- 3단계: 저장 (D-008) ----
    pos = {tb: pd.Series(range(len(std[tb])), index=std[tb].index) for tb in TABLES}
    outputs = {}
    keep_pos = pos["BET_TICKET"][t.index].tolist()
    tpa = take(pa_std["BET_TICKET"], keep_pos)
    tpa = replace_col(tpa, "HR_NM", t["HR_NM"].where(t["HR_NM"].notna(), None).tolist())
    invalid = yn(inv.values)
    eligible = yn(~inv.values)
    outputs["BET_TICKET"] = with_flags(tpa, {
        "INVALID_YN": invalid,
        "ZERO_BET_AGG_EXCLUDE_YN": invalid,
        "ERROR_AGG_INCLUDE_YN": invalid,
        "LATE_CANCEL_YN": yn(late_t.values),
        "ZERO_LATE_CANCEL_YN": yn(zero_late_tickets.values),
        "HR_NM_FILLED_YN": yn(hr_filled),
        "HR_NM_ORIG": take(pa_std["BET_TICKET"], keep_pos)["HR_NM"].to_pylist(),
        "SALES_AGG_INCLUDE_YN": eligible,
        "CANCEL_RATE_NUMERATOR_INCLUDE_YN": eligible,
        "CANCEL_RATE_DENOMINATOR_INCLUDE_YN": eligible,
    })
    outputs["BET_ORDER"] = with_flags(pa_std["BET_ORDER"], {
        "HEADER_MISMATCH_YN": yn(hm.values),
        "ORIG_MISSING_YN": yn(orig_missing.values),
        "LATE_CANCEL_YN": yn(late_o.values),
        "ZERO_LATE_CANCEL_YN": yn(zero_late_orders.values),
        "CANCEL_RATE_DENOM_INCLUDE_YN": yn(o.TOTAL_AMT.ne(0).values),
    })
    group_mismatch = yn(grp_bad.values)
    no_prior = yn(no_snap.values)
    outputs["HR_VET_HIST"] = with_flags(pa_std["HR_VET_HIST"], {
        "TR_GRP_MISMATCH_YN": group_mismatch,
        "PRIOR_SNAPSHOT_MISSING_YN": no_prior,
        "VET_TR_GRP_MISMATCH_YN": group_mismatch,
        "VET_NO_PRIOR_SNAPSHOT_YN": no_prior,
        "VET_GROUP_ANALYSIS_STATUS": (grp_bad | no_snap).map({True: "확인 필요", False: "정상"}),
    })
    br_keep = [p for i, p in pos["HR_VET_TYPE_BRIDGE"].items() if i not in set(drop_pos)]
    bpa = take(pa_std["HR_VET_TYPE_BRIDGE"], br_keep)
    names = br["VET_TYPE_NM"].copy()
    names.loc[first_pos] = new_name
    keep_idx = [i for i in br.index if i not in set(drop_pos)]
    bpa = replace_col(bpa, "VET_TYPE_NM", names.loc[keep_idx].tolist())
    outputs["HR_VET_TYPE_BRIDGE"] = with_flags(bpa, {
        "VET_TYPE_MERGED_YN": yn(pd.Index(keep_idx).isin(first_pos)),
        "VET_TYPE_AGG_NM": bpa["VET_TYPE_NM"].to_pylist(),
        "VET_TYPE_AGG_INCLUDE_YN": ["Y"] * len(bpa),
    })
    for tb in TABLES:
        pq.write_table(with_lineage(outputs.get(tb, pa_std[tb]), tb), C.CLEAN_DIR / f"{tb}.parquet")

    ex = take(pa_std["BET_TICKET"], pos["BET_TICKET"][dup_rows.index].tolist())
    ex = ex.append_column("RULE_ID", pa.array(["DQ-U01"] * len(dup_rows)))
    ex = ex.append_column("DECISION_ID", pa.array(["D-002"] * len(dup_rows)))
    reason = ["완전 중복 (최소 _SRC_ROW_NO 행만 유지)"] * len(dup_rows)
    ex = ex.append_column("REASON", pa.array(reason))
    ex = ex.append_column("EXCLUSION_REASON", pa.array(reason))
    ex = ex.append_column("DQ_ISSUE_ID", pa.array(["D-002"] * len(ex)))
    ex = ex.append_column("DQ_ACTION_DECISION_ID", pa.array(["D-002"] * len(ex)))
    ex = ex.append_column("BRONZE_FILE", pa.array([BRONZE_PATH["BET_TICKET"]] * len(dup_rows)))
    ex = ex.append_column("KEPT_SRC_ROW_NO", pa.array([int(kept_no[n]) for n in dup_rows["_SRC_ROW_NO"]], pa.int64()))
    pq.write_table(with_lineage(ex, "BET_TICKET"), C.EXCLUDED_DIR / "BET_TICKET.parquet")

    dq = pd.concat(LOG, ignore_index=True).sort_values(["RULE_ID", "TABLE_NM", "SRC_ROW_NO", "COL_NM"], kind="stable")
    dq.to_csv(C.DQ_LOG, index=False, encoding=C.CSV_ENCODING)
    rs = pd.DataFrame(RESULTS)
    rs["_D"] = rs.RULE_ID.str[3].map({k: i for i, k in enumerate(DIM_KO)})
    rs = rs.sort_values(["_D", "RULE_ID"], kind="stable").drop(columns="_D")
    rs.to_csv(C.DQ_RESULT, index=False, encoding=C.CSV_ENCODING)
    write_report(rs, std, outputs)
    _write_clean_manifest()

    for r in rs.itertuples():
        print(f"{r.RULE_ID:<7} {ACTION_KO[r.ACTION]:<3} {r.FINAL_CNT:>7,}  {r.RULE_DESC[:46]}")
    print(f"처리 로그 {len(dq):,}행 → {C.DQ_LOG.relative_to(C.ROOT)}")


# ---------------------------------------------------------------- 보고서
def fmt(x):
    return f"{x:,}" if isinstance(x, (int,)) else (str(x) if str(x) != "" else "—")


def write_report(rs, std, outputs):
    L = ["# 품질관리 보고서", "",
         "> `src/03_quality.py`가 만든 문서입니다. 다시 실행하면 같은 내용이 나옵니다.", "",
         "- **흐름:** Bronze → Silver 표준화(`data/02_silver/*.parquet`, 보존) → 품질 관리 → `data/02_silver/clean/` + `data/02_silver/_excluded/` → Gold",
         "- **처리 순서 (D-001):** 완전 중복 제거 → 나머지 규칙 측정 → 집계별 제외 조건(Gold에서 적용)",
         "- **근거:** 모든 규칙에 근거 결정 ID가 있습니다. 결정 내용은 `meta/decision_log.md`에 있습니다.",
         "- **기록:** 처리한 행은 `meta/dq_log.csv`(규칙 ID·결정 ID·Bronze 경로·원천 행 번호), 규칙별 결과는 `meta/dq_result.csv`에 있습니다.",
         "",
         "## 1. 규칙 목록", "",
         "| 규칙 ID | 차원 | 대상 | 규칙 (위반 조건) | 처리 | 근거 결정 ID |", "|:--|:--|:--|:--|:--|:--|"]
    for r in rs.itertuples():
        L.append(f"| {r.RULE_ID} | {r.DIM} | {r.TABLE_NM} | {r.RULE_DESC.replace('|', '/')} | {ACTION_KO[r.ACTION]} | {r.DECISION_ID} |")
    L += ["", "## 2. 규칙별 위반 수: Bronze · Silver 표준화 직후 · 최종(중복 제거 후)", "",
          "- **Bronze:** 원천 그대로의 값으로 잰 수입니다. 표기가 섞여 있어 잴 수 없는 규칙은 —",
          "- **Silver 표준화 직후:** 완전 중복을 지우기 전에 잰 수입니다 (참고).",
          "- **최종:** 완전 중복 1,052행을 제거한 뒤 잰 수입니다. **팀 기준 숫자는 이 값**입니다. DQ-U01은 제외한 행 수입니다.",
          "- **비율:** 최종 ÷ 대상 행 수",
          "- **예시 행:** `_SRC_ROW_NO` (원천 데이터 행 번호) 앞 3개", "",
          "| 규칙 ID | Bronze | Silver 표준화 직후 | **최종** | 대상 행 수 | 비율 | 예시 행 | 비고 |", "|:--|--:|--:|--:|--:|--:|:--|:--|"]
    for r in rs.itertuples():
        ratio = f"{r.FINAL_CNT / r.TARGET_ROWS:.2%}" if r.TARGET_ROWS else "—"
        L.append(f"| {r.RULE_ID} | {fmt(r.BRONZE_CNT)} | {fmt(r.SILVER_STD_CNT)} | **{r.FINAL_CNT:,}** | {r.TARGET_ROWS:,} | {ratio} | "
                 f"{r.EXAMPLE_ROWS or '—'} | {str(r.NOTE).replace('|', '/')} |")
    L += ["", "## 3. 차원별 요약 (최종)", "", "| 차원 | 규칙 수 | 위반 규칙 수 | 위반 수 합 | 대상 행 수 합 | 비율 |", "|:--|--:|--:|--:|--:|--:|"]
    for dim in DIM_KO.values():
        d = rs[rs.DIM == dim]
        if len(d):
            v, n = int(d.FINAL_CNT.sum()), int(d.TARGET_ROWS.sum())
            L.append(f"| {dim} | {len(d)} | {int((d.FINAL_CNT > 0).sum())} | {v:,} | {n:,} | {v / n:.2%} |")
    L += ["", "## 4. 처리 결과", "", "### 테이블별 행 수 대사 (D-008: 표준화 직후 = clean + _excluded)", "",
          "| 테이블 | 표준화 직후 | clean | _excluded | 대사 |", "|:--|--:|--:|--:|:-:|"]
    n_ex = pq.read_metadata(C.EXCLUDED_DIR / "BET_TICKET.parquet").num_rows
    for tb in TABLES:
        n_std = len(std[tb])
        n_cl = pq.read_metadata(C.CLEAN_DIR / f"{tb}.parquet").num_rows
        e = n_ex if tb == "BET_TICKET" else 0
        ok = "O" if n_std == n_cl + e else ("브리지 별도 (D-011)" if tb == "HR_VET_TYPE_BRIDGE" else "X")
        L.append(f"| {tb} | {n_std:,} | {n_cl:,} | {e:,} | {ok} |")
    L += ["", "### 표시·보정 컬럼 (clean/에 추가)", "", "| 테이블 | 컬럼 | Y 건수 | 결정 | 뜻 |", "|:--|:--|--:|:--|:--|"]
    flag_doc = [("BET_TICKET", "INVALID_YN", "D-003", "0원 마권. 매출·취소율 등 업무 집계에서 제외, 오류 집계에는 포함"),
                ("BET_TICKET", "LATE_CANCEL_YN", "D-004", "취소 시각 ≥ 그 마권 경주 출발 시각"),
                ("BET_TICKET", "HR_NM_FILLED_YN", "D-005", "마명을 출전표로 보정함"),
                ("BET_ORDER", "HEADER_MISMATCH_YN", "D-006", "전표 장수·총액 ≠ 마권 개수·합계"),
                ("BET_ORDER", "ORIG_MISSING_YN", "D-006", "취소 전표에 원전표번호 없음"),
                ("BET_ORDER", "LATE_CANCEL_YN", "D-004", "늦은 취소 마권이 하나 이상인 전표"),
                ("BET_TICKET", "ZERO_LATE_CANCEL_YN", "D-004", "0원이며 늦은 취소인 마권"),
                ("BET_ORDER", "ZERO_LATE_CANCEL_YN", "D-004", "0원 늦은 취소 마권이 하나 이상인 전표"),
                ("BET_TICKET", "SALES_AGG_INCLUDE_YN", "D-003", "0원이 아닌 매출 집계 대상 마권"),
                ("HR_VET_HIST", "TR_GRP_MISMATCH_YN", "D-007", "진료 기록의 조 ≠ 직전 스냅샷의 조 (확인 필요)"),
                ("HR_VET_HIST", "PRIOR_SNAPSHOT_MISSING_YN", "D-007", "진료일 이전 스냅샷 없음 (확인 필요)"),
                ("HR_VET_TYPE_BRIDGE", "VET_TYPE_MERGED_YN", "D-011", "'일·열사병'으로 통합한 행")]
    for tb, col, dec, mean in flag_doc:
        n = sum(1 for v in outputs[tb].column(col).to_pylist() if v == "Y")
        L.append(f"| {tb} | `{col}` | {n:,} | {dec} | {mean} |")
    L += ["", "## 5. 표준화 전후 비교로 알 수 있는 것", "",
          "- **표준화로 사라진 문제:** 날짜 형식 혼용(DQ-V01), 표준 코드가 아닌 값(DQ-V02). Bronze에는 많지만 Silver에서는 0입니다.",
          "- **표준화 후에도 남은 문제:** 완전 중복(DQ-U01), 0원 마권(DQ-V03), 마명 빈칸(DQ-C01). 내용 문제라 품질 관리에서 처리했습니다.",
          "- **Silver에서야 잴 수 있는 문제:** 전표·마권 불일치(DQ-S01), 늦은 취소(DQ-T02/T03), 진료 조 불일치(DQ-S04). 타입과 코드가 맞아야 비교할 수 있습니다.",
          "- **완전 중복을 먼저 지워야 하는 이유:** 0원 마권은 중복 포함 시 Silver 표준화 직후 값, 제거 후 최종 값으로 숫자가 다릅니다 (위 2장).", ""]
    C.DQ_REPORT.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
