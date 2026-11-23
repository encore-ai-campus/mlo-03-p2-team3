"""Bronze(01_bronze) → Silver(02_silver) 표준화.

규칙 근거: meta/mapping_rules.md (팀 공용 매핑 규칙서)
- 이름·타입·코드·형식만 바꾼다. 행은 지우지 않는다 (RC_SALES '합계' 행은 RC_SALES_TOTAL로 분리).
- 원천값을 버리지 않고 기록한다.
  * 변환 실패 / 코드표 밖 값 / 규칙상 NULL 처리된 원천값 → meta/silver_issue_log.csv (원천 행 번호와 원천값)
  * 코드 매핑(원천값 → 표준코드) 건수 → meta/silver_value_map.csv
  * 컬럼별 NULL·TRIM·실패 건수 → meta/silver_column_profile.csv
  * 표준 컬럼 정의·원천 컬럼·적용 규칙·제외 컬럼 → meta/data_dictionary.csv
  * 모든 Silver 테이블은 _SRC_ROW_NO(Bronze 행 번호)를 갖고 있어 원천 행으로 되돌아갈 수 있다.
"""
import json
import re
from datetime import time
from decimal import Decimal, InvalidOperation

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config as C

NULL_TOKENS = {"", "-----"}


def ok(x):
    """값이 있는지 (None·NaN·pd.NA가 아니면 True)."""
    return x is not None and x is not pd.NA and not (isinstance(x, float) and x != x)

ISSUES, VALUE_MAPS, PROFILES, DICTIONARY = [], [], [], []


# ---------------------------------------------------------------- 공통 도구
class Table:
    def __init__(self, name, bronze):
        self.name = name
        self.b = bronze.reset_index(drop=True)
        self.rowno = self.b["_SRC_ROW_NO"]
        self.cols = {}  # 표준 컬럼 → (값, 타입)
        self.trim_cnt = {}

    def raw(self, src):
        """TRIM 후 빈 값 → NULL. TRIM으로 바뀐 건수를 기록한다."""
        s = self.b[src].astype(object)
        stripped = s.map(lambda x: x.strip() if isinstance(x, str) else x)
        self.trim_cnt[src] = int(((s != stripped) & stripped.notna()).sum())
        return pd.Series([x if isinstance(x, str) and x not in NULL_TOKENS else None for x in stripped],
                         index=s.index, dtype=object)

    def add(self, col, values, typ, src, rule):
        self.cols[col] = (pd.Series(values, index=self.b.index), typ)
        DICTIONARY.append({"TABLE_NM": self.name, "COL_NM": col, "DATA_TYPE": typ,
                           "SRC_COL": src, "RULE": rule})

    def exclude(self, src, reason):
        DICTIONARY.append({"TABLE_NM": self.name, "COL_NM": "(제외)", "DATA_TYPE": "",
                           "SRC_COL": src, "RULE": reason})

    def issue(self, col, mask, raw, code, note=""):
        mask = pd.Series(mask, index=self.b.index).fillna(False).astype(bool)
        if not mask.any():
            return
        ISSUES.append(pd.DataFrame({
            "TABLE_NM": self.name, "SRC_ROW_NO": self.rowno[mask].values, "COL_NM": col,
            "RAW_VAL": pd.Series(raw, index=self.b.index)[mask].astype(str).values,
            "ISSUE_CD": code, "NOTE": note,
        }))

    def value_map(self, col, raw, std):
        df = pd.DataFrame({"RAW_VAL": pd.Series(raw, index=self.b.index).fillna("(NULL)"),
                           "STD_VAL": pd.Series(std, index=self.b.index).fillna("(NULL)")})
        g = df.groupby(["RAW_VAL", "STD_VAL"], sort=True).size().reset_index(name="CNT")
        g.insert(0, "COL_NM", col)
        g.insert(0, "TABLE_NM", self.name)
        VALUE_MAPS.append(g)


def to_int(t, col, raw, typ="INT", src=None, rule="정수 변환"):
    s = pd.Series(raw, index=t.b.index)
    num = pd.to_numeric(s.map(lambda x: x.replace(",", "") if isinstance(x, str) else x), errors="coerce")
    bad = s.notna() & (num.isna() | (num % 1 != 0))
    t.issue(col, bad, s, "PARSE_FAIL", "정수 아님")
    num = num.where(~bad)
    t.add(col, num.astype("Int64"), typ, src or col, rule)


def to_dec(t, col, raw, typ, src=None, rule="소수 변환"):
    precision, scale = map(int, re.findall(r"\d+", typ))
    q = Decimal(1).scaleb(-scale)
    limit = Decimal(1).scaleb(precision - scale)  # 정수부 자릿수 상한
    s = pd.Series(raw, index=t.b.index)

    def conv(x):
        if not ok(x):
            return None
        try:
            d = Decimal(str(x).replace(",", ""))
            if not d.is_finite() or d.copy_abs() >= limit:
                return "FAIL"  # 정밀도(전체 자릿수) 초과
            r = d.quantize(q)
        except InvalidOperation:
            return "FAIL"
        return r if d == r else "FAIL"  # 반올림으로 값이 바뀌면 실패

    out = s.map(conv)
    bad = out.eq("FAIL")
    t.issue(col, bad, s, "PARSE_FAIL", f"{typ} 변환 실패")
    t.add(col, out.where(~bad, None), typ, src or col, rule)


def to_date(t, col, raw, fmts, src=None, typ="DATE"):
    s = pd.Series(raw, index=t.b.index)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for f in fmts:
        todo = s.notna() & out.isna()
        out[todo] = pd.to_datetime(s[todo], format=f, errors="coerce")
    bad = s.notna() & out.isna()
    t.issue(col, bad, s, "PARSE_FAIL", "형식 " + " / ".join(fmts) + " 모두 불일치")
    t.add(col, out, typ, src or col, "형식 " + " → ".join(fmts) + " 순서로 시도")


def to_code(t, col, raw, mapping, group, src=None, rule=None):
    s = pd.Series(raw, index=t.b.index)
    out = s.map(lambda x: mapping.get(x) if ok(x) else None)
    bad = s.notna() & out.isna()
    t.issue(col, bad, s, "OUT_OF_CODE", f"코드그룹 {group}")
    t.value_map(col, s, out)
    t.add(col, out, "CODE", src or col, rule or f"코드그룹 {group} 매핑")


def to_str(t, col, src, rule="TRIM, 빈칸 NULL", typ="VARCHAR", upper=False):
    s = t.raw(src)
    if upper:
        s = s.map(lambda x: x.upper() if isinstance(x, str) else x)
    t.add(col, s, typ, src, rule)


def rule_null(t, col, mask, raw, note):
    """규칙에 따라 NULL로 둔 원천값을 기록한다 (실패가 아님)."""
    t.issue(col, mask, raw, "RULE_NULL", note)


def split_regex(raw, pattern):
    """정규식 그룹을 컬럼별 Series로. 매칭 실패는 fail 마스크."""
    s = pd.Series(raw)
    m = s.map(lambda x: re.fullmatch(pattern, x) if isinstance(x, str) else None)
    fail = s.notna() & m.isna()
    return m, fail


# ---------------------------------------------------------------- 코드표 (매핑_규칙서 6장)
BET_TYPE = {"WIN": "WIN", "단승": "WIN", "단식": "WIN", "PLC": "PLC", "연승": "PLC", "연식": "PLC",
            "QNL": "QNL", "복승": "QNL", "복식": "QNL", "복연": "QPL", "쌍식": "EXA",
            "삼복": "TRI", "삼쌍": "TLA"}
TICKET_STAT = {"SOLD": "SOLD", "sold": "SOLD", "CANCEL": "CANCEL", "cancel": "CANCEL",
               "VOID": "VOID", "void": "VOID"}
ORDER_TYPE = {"SALE": "SALE", "CANCEL": "CANCEL"}
MBR_STAT = {"10": "10", "20": "20", "90": "90"}
MBR_GRADE = {"VIP": "VIP", "GOLD": "GOLD", "NORMAL": "NORMAL"}
_REGION_FULL = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
                "광주광역시": "광주", "대전광역시": "대전", "경기도": "경기", "경상북도": "경북",
                "경상남도": "경남", "전라남도": "전남", "제주특별자치도": "제주"}
REGION = {**_REGION_FULL, **{v: v for v in _REGION_FULL.values()}}
HR_SEX = {"수": "M", "암": "F", "거": "G"}
HR_GRADE = {**{f"제{i}": str(i) for i in range(1, 7)}, "미": "NONE"}
RC_GRADE = {**{str(i): str(i) for i in range(1, 7)}, "OPEN": "OPEN"}
BUDAM_TYPE = {"핸디캡": "HANDICAP", "별정A": "SPECIAL_A"}
ENTRY_STAT = {**{str(i): "RAN" for i in range(1, 11)}, "94": "EXCLUDED", "95": "SCRATCHED"}
MARGIN_WORD = {"코": "NOSE", "머리": "HEAD", "목": "NECK", "동순위": "DH", "-": "NA"}
WEATHER = {"맑음": "CLEAR", "흐림": "CLOUDY", "비": "RAIN", "안개": "FOG"}
TRACK_STAT = {"건조": "DRY", "양호": "GOOD", "다습": "MOIST", "포화": "SATURATED", "불량": "SLOPPY"}
EVENT_TYPE = {"JOCKEY_CHANGE": "JOCKEY_CHANGE", "SCRATCH": "SCRATCH", "TRACK_STATUS": "TRACK_STATUS"}
MEET = {"제주": "JEJU"}
FRACTION = {"½": Decimal("0.5"), "¼": Decimal("0.25"), "¾": Decimal("0.75")}


def mmss_to_sec(x):
    """'1:13.2' → Decimal('73.2'), 형식 불일치는 'FAIL'."""
    m = re.fullmatch(r"(\d+):(\d{2}(?:\.\d+)?)", x)
    return Decimal(m.group(1)) * 60 + Decimal(m.group(2)) if m else "FAIL"


# ---------------------------------------------------------------- 테이블별 규칙 (매핑_규칙서 10장)
def bet_order(b):
    t = Table("BET_ORDER", b)
    to_str(t, "ORDER_NO", "order_no", typ="VARCHAR(10)")
    to_code(t, "ORDER_TYPE_CD", t.raw("order_type_cd"), ORDER_TYPE, "ORDER_TYPE", "order_type_cd")
    to_str(t, "ORIG_ORDER_NO", "orig_order_no", typ="VARCHAR(10)")
    to_str(t, "MBR_NO", "member_no", "TRIM + 대문자, 빈칸 NULL(비회원)", "VARCHAR(8)", upper=True)

    ch = t.raw("channel_cd")
    m, fail = split_regex(ch, r"OTB(\d{2})")
    chnl = ch.map(lambda x: "UNKNOWN" if not ok(x) else ("OTB" if re.fullmatch(r"OTB\d{2}", x) else
                                                          {"ONSITE": "ONSITE", "APP": "APP"}.get(x)))
    t.issue("CHNL_CD", ch.notna() & chnl.isna(), ch, "OUT_OF_CODE", "코드그룹 CHNL")
    t.value_map("CHNL_CD", ch, chnl)
    t.add("CHNL_CD", chnl, "CODE", "channel_cd", "ONSITE/APP 그대로, OTBnn→OTB, 빈칸→UNKNOWN")
    t.add("OTB_BRANCH_NO", m.map(lambda x: x.group(1) if ok(x) else None), "VARCHAR(2)", "channel_cd",
          "OTBnn의 nn")

    to_date(t, "SALE_DTM", t.raw("sale_dtm"), ["%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"], "sale_dtm", "TIMESTAMP")
    to_date(t, "BIZ_DT", t.raw("biz_date"), ["%Y%m%d"], "biz_date")
    to_int(t, "TICKET_CNT", t.raw("ticket_cnt"), "INT", "ticket_cnt", "전표 안 마권 장수")
    to_int(t, "TOTAL_AMT", t.raw("total_amt"), "BIGINT", "total_amt", "취소는 음수 그대로")
    return [t]


def bet_ticket(b):
    t = Table("BET_TICKET", b)
    to_str(t, "ORDER_NO", "order_no", typ="VARCHAR(10)")
    to_int(t, "TICKET_SEQ", t.raw("ticket_seq"), src="ticket_seq")
    to_date(t, "RC_DT", t.raw("rc_date"), ["%Y%m%d"], "rc_date")
    to_int(t, "RC_NO", t.raw("rc_no"), src="rc_no")
    to_code(t, "BET_TYPE_CD", t.raw("bet_type_cd"), BET_TYPE, "BET_TYPE", "bet_type_cd",
            "단승/연승/복승 한글 → WIN/PLC/QNL")
    to_int(t, "CHUL_NO", t.raw("chul_no"), src="chul_no")
    to_str(t, "HR_NM", "hr_name")
    to_int(t, "CHUL_NO2", t.raw("chul_no2"), src="chul_no2", rule="복승만, 빈칸 NULL")
    to_str(t, "HR_NM2", "hr_name2")
    to_int(t, "UNIT_CNT", t.raw("ticket_cnt"), src="ticket_cnt", rule="구좌 수 (이름 충돌: bet_order.ticket_cnt와 구분)")
    t.exclude("unit_amt", "전부 100 (상수)")
    to_int(t, "BET_AMT", t.raw("bet_amt"), src="bet_amt", rule="취소는 음수 그대로")
    to_code(t, "TICKET_STAT_CD", t.raw("ticket_status"), TICKET_STAT, "TICKET_STAT", "ticket_status",
            "대문자 통일")
    return [t]


def mbr_master(b):
    t = Table("MBR_MASTER", b)
    to_str(t, "MBR_NO", "MBR_NO", typ="VARCHAR(8)")
    to_date(t, "BIRTH_DT", t.raw("BIRTH_DT"), ["%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"], "BIRTH_DT")
    to_date(t, "JOIN_DT", t.raw("JOIN_DT"), ["%Y%m%d"], "JOIN_DT")
    to_code(t, "REGION_CD", t.raw("REGION_NM"), REGION, "REGION", "REGION_NM", "정식 명칭 → 약칭")
    to_code(t, "MBR_GRADE_CD", t.raw("MBR_GRADE_CD"), MBR_GRADE, "MBR_GRADE", "MBR_GRADE_CD")
    to_code(t, "MBR_STAT_CD", t.raw("MBR_STAT_CD"), MBR_STAT, "MBR_STAT", "MBR_STAT_CD", "숫자 모양 코드, 문자 유지")
    return [t]


def snapshot_counts(t):
    for p in ["TOT", "Y1"]:
        to_int(t, f"{p}_RC_CNT", t.raw(f"{p}_RC_CNT"), src=f"{p}_RC_CNT")
        for k in ["1ST", "2ND", "3RD"]:
            to_int(t, f"{p}_{k}_CNT", t.raw(f"{p}_{k}"), src=f"{p}_{k}")


def hr_weekly_snapshot(b):
    t = Table("HR_WEEKLY_SNAPSHOT", b)
    to_date(t, "SNAPSHOT_DT", t.raw("SNAPSHOT_DT"), ["%Y%m%d"], "SNAPSHOT_DT")
    to_str(t, "HR_NM", "HR_NAME")
    t.exclude("PRD_NM", "전부 '제' (상수)")
    to_code(t, "HR_SEX_CD", t.raw("SEX_NM"), HR_SEX, "HR_SEX", "SEX_NM", "수/암/거 → M/F/G")
    to_date(t, "HR_BIRTH_DT", t.raw("BIRTH_RAW"), ["%Y/%m/%d"], "BIRTH_RAW")
    to_int(t, "HR_AGE", t.raw("AGE_RAW"), src="AGE_RAW")
    to_code(t, "HR_GRADE_CD", t.raw("GRADE_RAW"), HR_GRADE, "HR_GRADE", "GRADE_RAW", "제1~제6/미 → 1~6/NONE")
    to_str(t, "TR_GRP_NO", "TR_GRP_NO", "앞 0 유지", "VARCHAR(2)")

    tr = t.raw("TR_NAME")
    ext = tr.eq("외부마")
    rule_null(t, "TR_NM", ext, tr, "'외부마'는 사람 이름이 아님 → TR_EXTERNAL_YN=Y")
    t.add("TR_NM", tr.where(~ext, None), "VARCHAR", "TR_NAME", "'외부마' → NULL")
    t.add("TR_EXTERNAL_YN", ext.map({True: "Y", False: "N"}), "CHAR(1)", "TR_NAME", "'외부마'면 Y, 아니면 N")

    to_str(t, "OW_NM", "OW_NAME")
    snapshot_counts(t)
    to_int(t, "PRIZE_AMT", t.raw("PRIZE_AMT_RAW"), "BIGINT", "PRIZE_AMT_RAW")
    to_int(t, "RATING_VAL", t.raw("RATING_RAW"), src="RATING_RAW", rule="빈칸 NULL")

    ip = t.raw("INTRO_PRICE_RAW")
    m, fail = split_regex(ip, r"([\d,]+)천원\((.+)\)")
    own = ip.eq("자가생산")
    fail = fail & ~own
    t.issue("INTRO_AMT", fail, ip, "PARSE_FAIL", "'N천원(유형)' / '자가생산' 아님")
    rule_null(t, "INTRO_AMT", own, ip, "'자가생산'은 금액 없음")
    t.add("INTRO_AMT", m.map(lambda x: int(x.group(1).replace(",", "")) * 1000 if ok(x) else None).astype("Int64"),
          "BIGINT", "INTRO_PRICE_RAW", "천원 → 원 (×1,000)")
    t.add("INTRO_TYPE_NM", pd.Series([x.group(2) if ok(x) else None for x in m]).where(~own, "자가생산"),
          "VARCHAR", "INTRO_PRICE_RAW", "괄호 안 유형, '자가생산'은 그대로")

    to_str(t, "SIRE_NM", "SIRE_NAME")
    to_str(t, "DAM_NM", "DAM_NAME")
    return [t]


def tr_weekly_snapshot(b):
    t = Table("TR_WEEKLY_SNAPSHOT", b)
    to_date(t, "SNAPSHOT_DT", t.raw("SNAPSHOT_DT"), ["%Y%m%d"], "SNAPSHOT_DT")
    to_str(t, "TR_NM", "TR_NAME")
    to_str(t, "TR_GRP_NO", "GRP_NO", "이름 통일 GRP_NO → TR_GRP_NO, 앞 0 유지", "VARCHAR(2)")
    to_date(t, "TR_BIRTH_DT", t.raw("BIRTH_RAW"), ["%Y/%m/%d"], "BIRTH_RAW")
    to_int(t, "TR_AGE", t.raw("AGE_RAW"), src="AGE_RAW")
    to_date(t, "DEBUT_DT", t.raw("DEBUT_RAW"), ["%Y/%m/%d"], "DEBUT_RAW")
    snapshot_counts(t)
    return [t]


def rc_race(b):
    t = Table("RC_RACE", b)
    to_date(t, "RC_DT", t.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(t, "RC_NO", t.raw("RC_NO"), src="RC_NO")
    t.exclude("TITLE_RAW", "RC_DT·RC_NO와 중복")
    t.exclude("RC_DOW", "날짜에서 계산 (DIM_DATE)")
    to_code(t, "MEET_CD", t.raw("MEET_NM"), MEET, "MEET", "MEET_NM")

    day = t.raw("RC_DAY_RAW")
    m, fail = split_regex(day, r"제\s*(\d+)일")
    t.issue("RC_DAY_SEQ", fail, day, "PARSE_FAIL", "'제 N일' 아님")
    t.add("RC_DAY_SEQ", m.map(lambda x: int(x.group(1)) if ok(x) else None).astype("Int64"), "INT", "RC_DAY_RAW", "숫자만")

    dist = t.raw("RC_DIST_RAW")
    m, fail = split_regex(dist, r"(\d+)M")
    t.issue("RC_DIST_M", fail, dist, "PARSE_FAIL", "'NNNNM' 아님")
    t.add("RC_DIST_M", m.map(lambda x: int(x.group(1)) if ok(x) else None).astype("Int64"), "INT", "RC_DIST_RAW", "숫자만")

    rank = t.raw("RANK_RAW")
    m, fail = split_regex(rank, r"제(\d|OPEN)(?:등급)?(.*)")
    t.issue("RC_GRADE_CD", fail, rank, "PARSE_FAIL", "'제N등급...' 아님")
    grade_tok = m.map(lambda x: x.group(1) if ok(x) else None)
    budam_tok = m.map(lambda x: x.group(2).strip() or None if ok(x) else None)
    to_code(t, "RC_GRADE_CD", grade_tok, RC_GRADE, "RC_GRADE", "RANK_RAW", "RANK_RAW 앞부분 → 1~6/OPEN")
    to_code(t, "BUDAM_TYPE_CD", budam_tok, BUDAM_TYPE, "BUDAM_TYPE", "RANK_RAW",
            "RANK_RAW 뒷부분 핸디캡/별정A → HANDICAP/SPECIAL_A, 없으면 NULL")

    cond = t.raw("RC_COND_RAW")
    body = cond.map(lambda x: re.sub(r"^핸디캡\s*", "", x) if ok(x) else x)
    m, fail = split_regex(body, r"(제주마)(.*)")
    t.issue("HR_CLASS_NM", fail, cond, "PARSE_FAIL", "'제주마'로 시작하지 않음")
    t.add("HR_CLASS_NM", m.map(lambda x: x.group(1) if ok(x) else None), "VARCHAR", "RC_COND_RAW", "앞 '핸디캡' 제거 후 마종")
    title = m.map(lambda x: x.group(2).strip() if ok(x) else None)
    general = title.eq("일반")
    rule_null(t, "RC_TITLE_NM", general, cond, "'일반'은 경주명 없음")
    t.add("RC_TITLE_NM", title.where(~general & title.ne(""), None), "VARCHAR", "RC_COND_RAW", "마종 뒤 경주명, '일반'이면 NULL")

    wt = t.raw("WEATHER_TRACK_RAW")
    m, fail = split_regex(wt, r"날씨:\s*(\S+)\s+주로:\s*(\S+)\s*(?:\(\s*([\d.]+)%\))?")
    t.issue("WEATHER_CD", fail, wt, "PARSE_FAIL", "'날씨: X 주로: Y (N%)' 아님")
    to_code(t, "WEATHER_CD", m.map(lambda x: x.group(1) if ok(x) else None), WEATHER, "WEATHER", "WEATHER_TRACK_RAW")
    to_code(t, "TRACK_STAT_CD", m.map(lambda x: x.group(2) if ok(x) else None), TRACK_STAT, "TRACK_STAT", "WEATHER_TRACK_RAW")
    moist = m.map(lambda x: x.group(3) if ok(x) else None)
    rule_null(t, "TRACK_MOIST_RT", m.notna() & moist.isna(), wt, "함수율 표기 없음 (주로 '불량')")
    to_dec(t, "TRACK_MOIST_RT", moist, "DECIMAL(5,1)", "WEATHER_TRACK_RAW", "괄호 안 함수율(%)")

    pr = t.raw("PRIZE_RAW")
    amts = pr.map(lambda x: re.findall(r"([\d,]+)만원", x) if ok(x) else [])
    fail = pr.notna() & (~pr.map(lambda x: isinstance(x, str) and x.startswith("순위상금:")) | amts.map(len).ne(5))
    t.issue("PRIZE1_AMT", fail, pr, "PARSE_FAIL", "'순위상금: N만원 ×5' 아님")
    for i in range(5):
        v = amts.map(lambda a: int(a[i].replace(",", "")) * 10000 if len(a) == 5 else None)
        t.add(f"PRIZE{i + 1}_AMT", v.where(~fail, None).astype("Int64"), "BIGINT", "PRIZE_RAW",
              f"{i + 1}위 상금, 만원 → 원 (×10,000)")
    t.exclude("DIVIDEND_RAW", "RC_ODDS와 내용 중복")

    st = t.raw("START_TM_RAW")
    m, fail = split_regex(st, r"(\d{2}):(\d{2})")
    t.issue("START_TM", fail, st, "PARSE_FAIL", "'HH:MI' 아님")
    tm = m.map(lambda x: time(int(x.group(1)), int(x.group(2))) if ok(x) else None)
    t.add("START_TM", tm, "TIME", "START_TM_RAW", "HH:MI → HH:MI:00")
    rc_dt = t.cols["RC_DT"][0]
    start = pd.to_datetime(rc_dt.dt.strftime("%Y-%m-%d") + " " + tm.map(lambda x: x.strftime("%H:%M:%S") if ok(x) else ""),
                           format="%Y-%m-%d %H:%M:%S", errors="coerce")
    t.add("START_DTM", start, "TIMESTAMP", "RC_DATE + START_TM_RAW", "RC_DT + START_TM")
    return [t]


def rc_entry(b):
    t = Table("RC_ENTRY", b)
    to_date(t, "RC_DT", t.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(t, "RC_NO", t.raw("RC_NO"), src="RC_NO")
    t.exclude("ORD_RAW", "RC_RESULT.FINISH_ORD 사용 (중복)")
    to_int(t, "CHUL_NO", t.raw("CHUL_NO"), src="CHUL_NO")
    to_str(t, "HR_NM", "HR_NAME")
    t.exclude("HR_BREED", "전부 '제' (상수)")
    to_code(t, "HR_SEX_CD", t.raw("HR_SEX"), HR_SEX, "HR_SEX", "HR_SEX", "수/암/거 → M/F/G")
    to_int(t, "HR_AGE", t.raw("HR_AGE"), src="HR_AGE")
    to_dec(t, "BUDAM_KG", t.raw("WG_BUDAM_RAW"), "DECIMAL(4,1)", "WG_BUDAM_RAW", "부담중량(kg)")
    to_str(t, "JK_NM", "JK_NAME")
    to_str(t, "TR_NM", "TR_NAME")
    to_str(t, "OW_NM", "OW_NAME")
    to_int(t, "RATING_VAL", t.raw("RATING_RAW"), src="RATING_RAW", rule="빈칸 NULL")
    return [t]


def rc_odds(b):
    t = Table("RC_ODDS", b)
    to_date(t, "RC_DT", t.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(t, "RC_NO", t.raw("RC_NO"), src="RC_NO")
    t.exclude("ORD_RAW", "RC_RESULT.FINISH_ORD 사용 (중복)")
    to_int(t, "CHUL_NO", t.raw("CHUL_NO"), src="CHUL_NO")

    sect = t.b["SECTION_TIMES_RAW"]  # 고정폭이라 TRIM 전 원문으로 자른다
    too_long = sect.str.rstrip().str.len() > 49
    t.issue("SECT1_SEC", too_long, sect, "PARSE_FAIL", "7칸(49자) 초과")
    for i in range(7):
        piece = sect.map(lambda x: x[i * 7:(i + 1) * 7].strip() or None)
        sec = piece.map(lambda x: mmss_to_sec(x) if ok(x) else None)
        bad = sec.eq("FAIL")
        t.issue(f"SECT{i + 1}_SEC", bad, piece, "PARSE_FAIL", "'m:ss.s' 아님")
        sec = sec.where(~bad & ~too_long, None)
        to_dec(t, f"SECT{i + 1}_SEC", sec, "DECIMAL(5,1)", "SECTION_TIMES_RAW",
               f"7글자 고정폭 {i + 1}번째 칸, m:ss.s → 초, 빈 칸 NULL")
    t.trim_cnt["SECTION_TIMES_RAW"] = 0

    for col, src in [("WIN_ODDS", "WIN_ODDS_RAW"), ("PLC_ODDS", "PLACE_ODDS_RAW")]:
        raw_s = t.b[src].str.strip()
        rule_null(t, col, raw_s.eq("-----"), raw_s, "'-----' = 값 없음")
        to_dec(t, col, t.raw(src), "DECIMAL(6,1)", src, "'-----' → NULL")
    return [t]


def rc_result(b):
    t = Table("RC_RESULT", b)
    to_date(t, "RC_DT", t.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(t, "RC_NO", t.raw("RC_NO"), src="RC_NO")

    ordr = t.raw("ORD_RAW")
    stat = ordr.map(lambda x: ENTRY_STAT.get(x) if ok(x) else None)
    to_code(t, "ENTRY_STAT_CD", ordr, ENTRY_STAT, "ENTRY_STAT", "ORD_RAW", "1~10 RAN / 94 EXCLUDED / 95 SCRATCHED")
    not_ran = stat.isin(["EXCLUDED", "SCRATCHED"])
    rule_null(t, "FINISH_ORD", not_ran, ordr, "94·95는 순위 아님")
    to_int(t, "FINISH_ORD", ordr.where(stat.eq("RAN"), None), src="ORD_RAW", rule="RAN만 순위, 94·95는 NULL")

    to_int(t, "CHUL_NO", t.raw("CHUL_NO"), src="CHUL_NO")
    to_str(t, "HR_NM", "HR_NAME")

    wg = t.raw("WG_HR_RAW")
    m, fail = split_regex(wg, r"(\d+)([+-]\d+)?")
    zero = wg.eq("0")
    t.issue("HR_WGT_KG", fail, wg, "PARSE_FAIL", "'NNN±N' 아님")
    rule_null(t, "HR_WGT_KG", zero, wg, "'0' → 체중·증감 NULL (경주제외·출주취소)")
    t.add("HR_WGT_KG", m.map(lambda x: int(x.group(1)) if ok(x) else None).where(~zero, None).astype("Int64"),
          "INT", "WG_HR_RAW", "'279+14'의 279, '0'은 NULL")
    t.add("HR_WGT_DIFF_KG", m.map(lambda x: int(x.group(2)) if ok(x) and x.group(2) else None).where(~zero, None).astype("Int64"),
          "INT", "WG_HR_RAW", "'279+14'의 +14, 증감 없으면 NULL")

    rt = t.raw("RC_TIME_RAW")
    word = rt.isin(["경주제외", "출주취소"])
    rule_null(t, "RC_TIME_SEC", word, rt, "'경주제외'·'출주취소'는 기록 없음")
    sec = rt.where(~word, None).map(lambda x: mmss_to_sec(x) if ok(x) else None)
    bad = sec.eq("FAIL")
    t.issue("RC_TIME_SEC", bad, rt, "PARSE_FAIL", "'m:ss.s' 아님")
    to_dec(t, "RC_TIME_SEC", sec.where(~bad, None), "DECIMAL(5,1)", "RC_TIME_RAW", "m:ss.s → 초")

    mg_raw = t.b["MARGIN_RAW"].str.strip()  # 빈칸은 1착(FIRST)이라 NULL로 바꾸기 전 원문 사용

    def margin(x):
        if x == "":
            return "FIRST", None
        if x in MARGIN_WORD:
            return MARGIN_WORD[x], None
        mm = re.fullmatch(r"(\d+)?([½¼¾])?", x)
        if mm and (mm.group(1) or mm.group(2)):
            return "LEN", Decimal(mm.group(1) or 0) + FRACTION.get(mm.group(2), Decimal(0))
        return None, None

    parsed = mg_raw.map(margin)
    cd = parsed.map(lambda p: p[0])
    t.issue("MARGIN_CD", cd.isna(), mg_raw, "OUT_OF_CODE", "코드그룹 MARGIN")
    t.value_map("MARGIN_CD", mg_raw.map(lambda x: "(빈칸)" if x == "" else ("(숫자)" if re.fullmatch(r"[\d½¼¾]+", x) else x)), cd)
    to_dec(t, "MARGIN_LEN", parsed.map(lambda p: p[1]), "DECIMAL(5,2)", "MARGIN_RAW", "½=0.5 ¼=0.25 ¾=0.75, 말 길이 수")
    t.add("MARGIN_CD", cd, "CODE", "MARGIN_RAW", "숫자 LEN / 코 NOSE / 머리 HEAD / 목 NECK / 동순위 DH / - NA / 빈칸 FIRST")
    t.cols["MARGIN_CD"], t.cols["MARGIN_LEN"] = t.cols.pop("MARGIN_CD"), t.cols.pop("MARGIN_LEN")  # 순서: LEN, CD

    po_raw = t.raw("PASS_ORD_RAW")
    no_pass = po_raw.map(lambda x: ok(x) and re.fullmatch(r"[-\s]+", x) is not None)
    rule_null(t, "PASS_ORD_S1", no_pass, po_raw, "'-'와 공백뿐 = 통과 순위 기록 없음 (경주제외·출주취소마) → S1~S6 NULL")
    po = po_raw.where(~no_pass, None)
    parts = po.map(lambda x: x.split("-") if ok(x) else None)
    bad = po.notna() & parts.map(lambda p: ok(p) and len(p) != 6)
    t.issue("PASS_ORD_S1", bad, po, "PARSE_FAIL", "'-'로 나눈 칸이 6개 아님")
    for i in range(6):
        piece = parts.map(lambda p: (p[i].strip() or None) if ok(p) and len(p) == 6 else None)
        to_int(t, f"PASS_ORD_S{i + 1}", piece, src="PASS_ORD_RAW", rule=f"'-'로 나눈 {i + 1}번째 칸, 빈 칸 NULL")
    return [t]


def rc_sales(b):
    total_mask = b["POOL_NM"].str.strip().eq("합계")
    t = Table("RC_SALES", b[~total_mask])
    to_date(t, "RC_DT", t.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(t, "RC_NO", t.raw("RC_NO"), src="RC_NO")
    to_code(t, "BET_TYPE_CD", t.raw("POOL_NM"), BET_TYPE, "BET_TYPE", "POOL_NM", "단식/연식/복식/복연/쌍식/삼복/삼쌍 → 표준 승식")
    to_int(t, "SALES_AMT", t.raw("SALES_AMT_RAW"), "BIGINT", "SALES_AMT_RAW", "쉼표 제거")

    s = Table("RC_SALES_TOTAL", b[total_mask])
    to_date(s, "RC_DT", s.raw("RC_DATE"), ["%Y%m%d"], "RC_DATE")
    to_int(s, "RC_NO", s.raw("RC_NO"), src="RC_NO")
    to_int(s, "SALES_AMT", s.raw("SALES_AMT_RAW"), "BIGINT", "SALES_AMT_RAW", "POOL_NM='합계' 행, 쉼표 제거 (검증용)")
    return [t, s]


def hr_vet_hist(b):
    t = Table("HR_VET_HIST", b)
    t.add("VET_SEQ", t.rowno.astype("Int64"), "INT", "(새 키)", "Bronze 행 번호 (브리지 연결용)")
    to_date(t, "VET_DT", t.raw("VET_DT_RAW"), ["%Y.%m.%d"], "VET_DT_RAW")
    to_str(t, "HR_NM", "HR_NAME")
    to_str(t, "TR_GRP_NO", "TR_GRP_NO", "진료 기록 값 그대로", "VARCHAR(2)")
    to_str(t, "VET_PLACE_NM", "VET_PLACE_NM")
    to_str(t, "VET_NM", "VET_NM_RAW", "원본 진료명 그대로 (TRIM)")
    to_date(t, "REPORT_DT", t.raw("REPORT_DT"), ["%Y%m%d"], "REPORT_DT")

    names = t.raw("VET_NM_RAW")
    rows = [(rn, n.strip(), rn) for rn, v in zip(t.rowno, names) if ok(v)
            for n in v.split(",") if n.strip()]
    bb = pd.DataFrame(rows, columns=["VET_SEQ", "VET_TYPE_NM", "_SRC_ROW_NO"])
    g = Table("HR_VET_TYPE_BRIDGE", bb)
    g.add("VET_SEQ", bb["VET_SEQ"].astype("Int64"), "INT", "HR_VET_HIST.VET_SEQ", "진료 기록 연결 키")
    g.add("VET_TYPE_NM", bb["VET_TYPE_NM"], "VARCHAR", "VET_NM_RAW", "',' 로 나눈 진료명 1개")
    return [t, g]


def rc_change_event(b):
    t = Table("RC_CHANGE_EVENT", b)
    ev = t.b["RAW_JSON"].map(json.loads)

    def get(path):
        def f(d):
            for k in path.split("."):
                if not isinstance(d, dict) or k not in d:
                    return None
                d = d[k]
            v = str(d).strip()
            return None if v in NULL_TOKENS else v
        return ev.map(f)

    to_code(t, "EVENT_TYPE_CD", get("eventType"), EVENT_TYPE, "EVENT_TYPE", "eventType")
    to_date(t, "ANNOUNCE_DTM", get("announcedAt"), ["%Y%m%d %H:%M"], "announcedAt", "TIMESTAMP")
    to_date(t, "RC_DT", get("race.rcDate"), ["%Y/%m/%d"], "race.rcDate")
    to_int(t, "RC_NO", get("race.rcNo"), src="race.rcNo")
    to_int(t, "CHUL_NO", get("horse.chulNo"), src="horse.chulNo")
    t.add("HR_NM", get("horse.hrName"), "VARCHAR", "horse.hrName", "TRIM")
    t.add("BEF_JK_NM", get("change.before"), "VARCHAR", "change.before", "기수변경 전")
    t.add("AFT_JK_NM", get("change.after"), "VARCHAR", "change.after", "기수변경 후")
    to_dec(t, "BUDAM_KG", get("change.budamRaw"), "DECIMAL(4,1)", "change.budamRaw")
    t.add("CHG_REASON_NM", get("change.reason"), "VARCHAR", "change.reason", "기수변경 사유 (이름 충돌 구분)")
    t.add("SCRATCH_REASON_NM", get("reason"), "VARCHAR", "reason", "말취소 사유 (이름 충돌 구분)")

    tr = get("trackRaw")
    m, fail = split_regex(tr, r"(\S+)\s*(?:\(\s*([\d.]+)%\))?")
    t.issue("TRACK_STAT_CD", fail, tr, "PARSE_FAIL", "'주로상태 (N%)' 아님")
    to_code(t, "TRACK_STAT_CD", m.map(lambda x: x.group(1) if ok(x) else None), TRACK_STAT, "TRACK_STAT", "trackRaw")
    moist = m.map(lambda x: x.group(2) if ok(x) else None)
    rule_null(t, "TRACK_MOIST_RT", m.notna() & moist.isna(), tr, "함수율 표기 없음")
    to_dec(t, "TRACK_MOIST_RT", moist, "DECIMAL(5,1)", "trackRaw", "괄호 안 함수율(%)")
    return [t]


STEPS = [
    ("bet_order", bet_order), ("bet_ticket", bet_ticket), ("MBR_MASTER", mbr_master),
    ("HR_WEEKLY_SNAPSHOT", hr_weekly_snapshot), ("TR_WEEKLY_SNAPSHOT", tr_weekly_snapshot),
    ("RC_RACE", rc_race), ("RC_ENTRY", rc_entry), ("RC_ODDS", rc_odds), ("RC_RESULT", rc_result),
    ("RC_SALES", rc_sales), ("HR_VET_HIST", hr_vet_hist), ("race_change_events", rc_change_event),
]


# ---------------------------------------------------------------- 저장
def arrow_type(typ):
    if typ.startswith(("VARCHAR", "CHAR", "CODE")):
        return pa.string()
    if typ.startswith("DECIMAL"):
        p, s = map(int, re.findall(r"\d+", typ))
        return pa.decimal128(p, s)
    return {"INT": pa.int32(), "BIGINT": pa.int64(), "DATE": pa.date32(),
            "TIMESTAMP": pa.timestamp("s"), "TIME": pa.time32("s")}[typ]


def to_arrow(s, typ):
    at = arrow_type(typ)
    if pa.types.is_string(at):
        return pa.array([x if isinstance(x, str) else None for x in s.astype(object)], pa.string())
    if pa.types.is_decimal(at) or pa.types.is_time(at):
        return pa.array([x if ok(x) else None for x in s.astype(object)], at)
    if pa.types.is_integer(at):
        return pa.array(s.astype("Int64"), from_pandas=True).cast(at)
    return pa.array(s.astype("datetime64[ns]"), from_pandas=True).cast(at)


def save(t):
    arrays = {c: to_arrow(v, typ) for c, (v, typ) in t.cols.items()}
    arrays["_SRC_ROW_NO"] = pa.array(t.rowno.astype("int64"))
    pq.write_table(pa.table(arrays), C.SILVER_DIR / f"{t.name}.parquet")

    for c, (v, typ) in t.cols.items():
        src = next(d["SRC_COL"] for d in DICTIONARY if d["TABLE_NM"] == t.name and d["COL_NM"] == c)
        PROFILES.append({"TABLE_NM": t.name, "COL_NM": c, "SRC_COL": src, "ROW_CNT": len(v),
                         "NULL_CNT": int(pd.isna(v).sum()), "TRIM_CNT": t.trim_cnt.get(src, 0)})
    return len(t.b)


def main():
    C.SILVER_DIR.mkdir(parents=True, exist_ok=True)
    for bronze_name, fn in STEPS:
        b = pd.read_parquet(C.BRONZE_DIR / f"{bronze_name}.parquet")
        for t in fn(b):
            n = save(t)
            print(f"{bronze_name:<22} → {t.name:<20} {n:>8,}행")

    issues = (pd.concat(ISSUES, ignore_index=True) if ISSUES else
              pd.DataFrame(columns=["TABLE_NM", "SRC_ROW_NO", "COL_NM", "RAW_VAL", "ISSUE_CD", "NOTE"]))
    issues.sort_values(["TABLE_NM", "COL_NM", "SRC_ROW_NO", "ISSUE_CD"], kind="stable").to_csv(
        C.SILVER_ISSUE_LOG, index=False, encoding=C.CSV_ENCODING)

    prof = pd.DataFrame(PROFILES)
    cnt = issues.groupby(["TABLE_NM", "COL_NM", "ISSUE_CD"]).size().unstack(fill_value=0)
    for code in ["PARSE_FAIL", "OUT_OF_CODE", "RULE_NULL"]:
        col = f"{code}_CNT"
        prof[col] = [int(cnt[code].get((r.TABLE_NM, r.COL_NM), 0)) if code in cnt else 0 for r in prof.itertuples()]
    prof.to_csv(C.SILVER_COLUMN_PROFILE, index=False, encoding=C.CSV_ENCODING)

    pd.concat(VALUE_MAPS, ignore_index=True).to_csv(C.SILVER_VALUE_MAP, index=False, encoding=C.CSV_ENCODING)
    # 종합 데이터 사전: Silver 행만 다시 쓰고 Gold·AI Ready 행(LAYER가 SILVER가 아닌 행)은 그대로 둔다
    silver_dic = pd.DataFrame(DICTIONARY)
    silver_dic.insert(0, "LAYER", "SILVER")
    old = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False) if C.DATA_DICTIONARY.exists() else pd.DataFrame()
    other = old[old.LAYER.ne("SILVER")] if "LAYER" in old else old.iloc[0:0]
    pd.concat([silver_dic, other], ignore_index=True).to_csv(C.DATA_DICTIONARY, index=False, encoding=C.CSV_ENCODING)
    print(f"이슈 로그 {len(issues):,}건 → {C.SILVER_ISSUE_LOG.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
