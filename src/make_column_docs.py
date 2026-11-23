"""Bronze·Silver 컬럼 사전 문서 생성 → docs/BRONZE_COLUMNS.md, docs/SILVER_COLUMNS.md

- 컬럼 뜻·코드 뜻: 아래 사전에 사람이 쓴 설명 (근거: meta/mapping_rules.md)
- 건수·예시·값 목록·범위: 실행할 때 데이터에서 계산 (데이터가 바뀌면 다시 실행)
"""
import json
import re

import pandas as pd

import config as C

# ---------------------------------------------------------------- 테이블 설명
BRONZE_TABLES = {
    "bet_order": "전표 1건 (마권을 한 번 사거나 취소한 영수증)",
    "bet_ticket": "전표 안의 마권 1개 (어느 경주, 어느 말에 얼마를 걸었나)",
    "MBR_MASTER": "회원 1명",
    "HR_WEEKLY_SNAPSHOT": "주간 기준일(SNAPSHOT_DT)의 말 1두 상태",
    "TR_WEEKLY_SNAPSHOT": "주간 기준일의 조교사 1명 상태",
    "RC_RACE": "경주 1개",
    "RC_ENTRY": "경주에 나온 말 1두 (출전표)",
    "RC_ODDS": "출전마 1두의 배당률·구간 기록",
    "RC_RESULT": "출전마 1두의 경주 결과",
    "RC_SALES": "경주 1개 × 승식 풀 1개의 매출 (+ 경주마다 '합계' 1행)",
    "HR_VET_HIST": "말 진료 1건",
    "race_change_events": "변경 공지 1건 (기수변경 / 말취소 / 주로상태). MongoDB JSON",
}

SILVER_TABLES = {
    "BET_ORDER": "전표 1건", "BET_TICKET": "전표 안의 마권 1개", "MBR_MASTER": "회원 1명",
    "HR_WEEKLY_SNAPSHOT": "주간 기준일의 말 1두 상태", "TR_WEEKLY_SNAPSHOT": "주간 기준일의 조교사 1명 상태",
    "RC_RACE": "경주 1개", "RC_ENTRY": "출전마 1두", "RC_ODDS": "출전마 1두의 배당률·구간 기록",
    "RC_RESULT": "출전마 1두의 경주 결과", "RC_SALES": "경주 1개 × 승식 1개의 매출",
    "RC_SALES_TOTAL": "경주 1개의 매출 합계 (원천 '합계' 행, 검증용)", "HR_VET_HIST": "말 진료 1건",
    "HR_VET_TYPE_BRIDGE": "진료 1건 × 진료명 1개 (한 칸에 여러 개였던 진료명을 나눈 것)",
    "RC_CHANGE_EVENT": "변경 공지 1건",
}

# ---------------------------------------------------------------- Bronze 컬럼 뜻 (파일명, 컬럼) 우선, 없으면 ("*", 컬럼)
B = {
    ("*", "RC_DATE"): "경주일", ("*", "rc_date"): "경주일", ("*", "RC_NO"): "경주번호 (그날 몇 번째 경주)",
    ("*", "rc_no"): "경주번호", ("*", "CHUL_NO"): "마번 (경주에서 받은 출전 번호)", ("*", "chul_no"): "고른 말의 마번",
    ("*", "HR_NAME"): "마명 (말 이름). 말 고유 ID가 없어 이름이 연결 키", ("*", "TR_NAME"): "조교사 이름",
    ("*", "OW_NAME"): "마주 (말 주인) 이름", ("*", "RATING_RAW"): "레이팅 (말 능력 점수). 빈칸 많음",
    ("*", "SNAPSHOT_DT"): "스냅샷 기준일 (매주)", ("*", "ORD_RAW"): "착순. 1~10 = 순위, 94 = 경주제외, 95 = 출주취소",
    ("*", "TOT_RC_CNT"): "통산 출전 수", ("*", "TOT_1ST"): "통산 1착 수", ("*", "TOT_2ND"): "통산 2착 수",
    ("*", "TOT_3RD"): "통산 3착 수", ("*", "Y1_RC_CNT"): "최근 1년 출전 수", ("*", "Y1_1ST"): "최근 1년 1착 수",
    ("*", "Y1_2ND"): "최근 1년 2착 수", ("*", "Y1_3RD"): "최근 1년 3착 수",
    ("*", "TR_GRP_NO"): "소속 조 번호 (조교사 1명 = 조 1개). 88 = 외부마",

    ("bet_order", "order_no"): "전표번호", ("bet_order", "order_type_cd"): "전표 종류. SALE 구매 / CANCEL 취소",
    ("bet_order", "orig_order_no"): "취소 전표가 가리키는 원래 구매 전표번호",
    ("bet_order", "member_no"): "회원번호. 빈칸 = 비회원. 앞뒤 공백·소문자가 섞여 있음",
    ("bet_order", "channel_cd"): "판매 채널. ONSITE 현장 / APP 앱 / OTBnn 장외발매소 nn번 지점",
    ("bet_order", "sale_dtm"): "판매 일시. 현장·앱과 장외(OTB)의 형식이 다름",
    ("bet_order", "biz_date"): "영업일", ("bet_order", "ticket_cnt"): "전표 안 마권 장수",
    ("bet_order", "total_amt"): "전표 총액(원). 취소는 음수",

    ("bet_ticket", "order_no"): "전표번호 (bet_order와 연결)", ("bet_ticket", "ticket_seq"): "전표 안 마권 순번",
    ("bet_ticket", "bet_type_cd"): "승식. 영문(WIN/PLC/QNL)과 한글(단승/연승/복승) 섞임",
    ("bet_ticket", "hr_name"): "고른 말의 마명. 앞뒤 공백·빈칸 있음",
    ("bet_ticket", "chul_no2"): "두 번째 말의 마번 (복승만)", ("bet_ticket", "hr_name2"): "두 번째 말의 마명 (복승만)",
    ("bet_ticket", "ticket_cnt"): "구좌 수 (금액 ÷ 100). 취소는 음수. ⚠ bet_order.ticket_cnt와 뜻이 다름",
    ("bet_ticket", "unit_amt"): "구좌당 금액. 전부 100", ("bet_ticket", "bet_amt"): "마권 금액(원). 취소는 음수",
    ("bet_ticket", "ticket_status"): "마권 상태. SOLD 정상 / CANCEL 발매취소 / VOID 출전취소로 무효. 대소문자 섞임",

    ("MBR_MASTER", "MBR_NO"): "회원번호", ("MBR_MASTER", "BIRTH_DT"): "생년월일. 형식 3종 섞임",
    ("MBR_MASTER", "JOIN_DT"): "가입일", ("MBR_MASTER", "REGION_NM"): "거주 지역. 정식 명칭(서울특별시)과 약칭(서울) 섞임",
    ("MBR_MASTER", "MBR_GRADE_CD"): "회원 등급", ("MBR_MASTER", "MBR_STAT_CD"): "회원 상태. 10 정상 / 20 휴면 / 90 탈퇴",

    ("HR_WEEKLY_SNAPSHOT", "PRD_NM"): "산지 표시로 보임. 전부 '제'(상수)",
    ("HR_WEEKLY_SNAPSHOT", "SEX_NM"): "말 성별. 수 / 암 / 거(거세마)", ("HR_WEEKLY_SNAPSHOT", "BIRTH_RAW"): "말 생일",
    ("HR_WEEKLY_SNAPSHOT", "AGE_RAW"): "말 나이", ("HR_WEEKLY_SNAPSHOT", "GRADE_RAW"): "말 등급. 제1~제6, 미(미등급)",
    ("HR_WEEKLY_SNAPSHOT", "TR_NAME"): "조교사 이름. '외부마' = 사람 이름이 아니라 소속 조교사가 없는 말 표시",
    ("HR_WEEKLY_SNAPSHOT", "PRIZE_AMT_RAW"): "상금 합계(원)",
    ("HR_WEEKLY_SNAPSHOT", "INTRO_PRICE_RAW"): "도입 가격과 유형. '3,000천원(개별)' 또는 '자가생산'",
    ("HR_WEEKLY_SNAPSHOT", "SIRE_NAME"): "부마 (아버지 말)", ("HR_WEEKLY_SNAPSHOT", "DAM_NAME"): "모마 (어머니 말)",

    ("TR_WEEKLY_SNAPSHOT", "GRP_NO"): "소속 조 번호 (HR 쪽 TR_GRP_NO와 같은 뜻, 이름만 다름)",
    ("TR_WEEKLY_SNAPSHOT", "BIRTH_RAW"): "조교사 생일", ("TR_WEEKLY_SNAPSHOT", "AGE_RAW"): "조교사 나이",
    ("TR_WEEKLY_SNAPSHOT", "DEBUT_RAW"): "조교사 데뷔일",
    ("TR_WEEKLY_SNAPSHOT", "TOT_RC_CNT"): "조교사 관리마의 통산 출전 수",

    ("RC_RACE", "TITLE_RAW"): "경주 제목 문자열. 날짜·경주번호와 중복", ("RC_RACE", "RC_DOW"): "요일",
    ("RC_RACE", "MEET_NM"): "경마장", ("RC_RACE", "RC_DAY_RAW"): "개최 일차 ('제 40일')",
    ("RC_RACE", "RC_DIST_RAW"): "경주 거리 ('1000M')", ("RC_RACE", "RANK_RAW"): "경주 등급 + 부담 방식 ('제5등급핸디캡')",
    ("RC_RACE", "RC_COND_RAW"): "경주 조건: 마종 + 경주명 ('제주마일반' = 일반 경주)",
    ("RC_RACE", "WEATHER_TRACK_RAW"): "날씨 + 주로 상태 + 함수율(%)",
    ("RC_RACE", "PRIZE_RAW"): "1~5위 상금 (만원 단위)", ("RC_RACE", "DIVIDEND_RAW"): "배당 요약 문자열. RC_ODDS와 내용 중복",
    ("RC_RACE", "START_TM_RAW"): "출발 시각 (HH:MI)",

    ("RC_ENTRY", "ORD_RAW"): "착순 (RC_RESULT와 같은 값)", ("RC_ENTRY", "HR_BREED"): "품종 표시로 보임. 전부 '제'(상수)",
    ("RC_ENTRY", "HR_SEX"): "말 성별. 수 / 암 / 거", ("RC_ENTRY", "HR_AGE"): "말 나이",
    ("RC_ENTRY", "WG_BUDAM_RAW"): "부담중량(kg). 말이 지고 뛰는 무게", ("RC_ENTRY", "JK_NAME"): "기수 이름 (변경 반영된 최종)",

    ("RC_ODDS", "ORD_RAW"): "착순 (RC_RESULT와 같은 값)",
    ("RC_ODDS", "SECTION_TIMES_RAW"): "구간별 기록 'm:ss.s'를 7칸 고정폭(7글자)으로 이어 붙인 것. 빈 구간은 공백",
    ("RC_ODDS", "WIN_ODDS_RAW"): "단승 배당률(배). '-----' = 없음", ("RC_ODDS", "PLACE_ODDS_RAW"): "연승 배당률(배). '-----' = 없음",

    ("RC_RESULT", "WG_HR_RAW"): "말 체중(kg) + 지난번 대비 증감 ('279+14'). 뛰지 않은 말은 '0'",
    ("RC_RESULT", "RC_TIME_RAW"): "경주 기록 'm:ss.s'. 뛰지 않은 말은 '경주제외'/'출주취소' 글자",
    ("RC_RESULT", "MARGIN_RAW"): "착차 (앞 말과의 거리). 숫자·분수 = 마신, 코/머리/목, 동순위, '-', 빈칸 = 1착",
    ("RC_RESULT", "PASS_ORD_RAW"): "구간별 통과 순위를 '-'로 이은 것 (6칸)",

    ("RC_SALES", "POOL_NM"): "승식 풀 이름. 단식/연식/복식/복연/쌍식/삼복/삼쌍, 합계",
    ("RC_SALES", "SALES_AMT_RAW"): "매출액(원). 쉼표 포함 문자열",

    ("HR_VET_HIST", "VET_DT_RAW"): "진료일 (YYYY.MM.DD)", ("HR_VET_HIST", "TR_GRP_NO"): "진료 기록상의 소속 조",
    ("HR_VET_HIST", "VET_PLACE_NM"): "진료 장소", ("HR_VET_HIST", "VET_NM_RAW"): "진료명. 한 칸에 쉼표로 여러 개",
    ("HR_VET_HIST", "REPORT_DT"): "진료 보고일 (진료일보다 0~4일 늦음)",

    ("race_change_events", "RAW_JSON"): "JSON 한 줄 원문 그대로. 아래 키로 펼쳐서 설명",
    ("race_change_events", "eventType"): "공지 종류. JOCKEY_CHANGE 기수변경 / SCRATCH 말취소 / TRACK_STATUS 주로상태",
    ("race_change_events", "announcedAt"): "공지 일시 (YYYYMMDD HH:MI)", ("race_change_events", "race.rcDate"): "경주일 (YYYY/MM/DD)",
    ("race_change_events", "race.rcNo"): "경주번호", ("race_change_events", "horse.chulNo"): "마번",
    ("race_change_events", "horse.hrName"): "마명", ("race_change_events", "change.before"): "변경 전 기수",
    ("race_change_events", "change.after"): "변경 후 기수", ("race_change_events", "change.budamRaw"): "변경 후 부담중량(kg)",
    ("race_change_events", "change.reason"): "기수변경 사유", ("race_change_events", "reason"): "말취소 사유",
    ("race_change_events", "trackRaw"): "주로 상태 + 함수율 ('다습 ( 14.0%)')",
}

# ---------------------------------------------------------------- Silver 컬럼 뜻 (테이블, 컬럼) 우선, 없으면 ("*", 컬럼)
S = {
    ("*", "RC_DT"): "경주일", ("*", "RC_NO"): "경주번호 (그날 몇 번째 경주)", ("*", "CHUL_NO"): "마번",
    ("*", "HR_NM"): "마명 (말 연결 키)", ("*", "TR_NM"): "조교사 이름", ("*", "OW_NM"): "마주 이름",
    ("*", "JK_NM"): "기수 이름", ("*", "HR_SEX_CD"): "말 성별", ("*", "HR_AGE"): "말 나이",
    ("*", "RATING_VAL"): "레이팅 (말 능력 점수)", ("*", "SNAPSHOT_DT"): "스냅샷 기준일",
    ("*", "TR_GRP_NO"): "소속 조 번호 (앞 0 유지). 88 = 외부마", ("*", "ORDER_NO"): "전표번호",
    ("*", "TOT_RC_CNT"): "통산 출전 수", ("*", "TOT_1ST_CNT"): "통산 1착 수", ("*", "TOT_2ND_CNT"): "통산 2착 수",
    ("*", "TOT_3RD_CNT"): "통산 3착 수", ("*", "Y1_RC_CNT"): "최근 1년 출전 수", ("*", "Y1_1ST_CNT"): "최근 1년 1착 수",
    ("*", "Y1_2ND_CNT"): "최근 1년 2착 수", ("*", "Y1_3RD_CNT"): "최근 1년 3착 수",
    ("*", "BET_TYPE_CD"): "승식", ("*", "TRACK_STAT_CD"): "주로 상태", ("*", "TRACK_MOIST_RT"): "함수율(%)",
    ("*", "BUDAM_KG"): "부담중량(kg)", ("*", "VET_SEQ"): "진료 기록 번호 (Bronze 행 번호, 브리지 연결 키)",
    ("*", "SALES_AMT"): "매출액(원)",

    ("BET_ORDER", "ORDER_TYPE_CD"): "전표 종류", ("BET_ORDER", "ORIG_ORDER_NO"): "취소 전표가 가리키는 원래 구매 전표번호",
    ("BET_ORDER", "MBR_NO"): "회원번호 (대문자, 공백 제거). NULL = 비회원", ("BET_ORDER", "CHNL_CD"): "판매 채널",
    ("BET_ORDER", "OTB_BRANCH_NO"): "장외발매소 지점 번호 (OTB일 때만)", ("BET_ORDER", "SALE_DTM"): "판매 일시 (KST)",
    ("BET_ORDER", "BIZ_DT"): "영업일", ("BET_ORDER", "TICKET_CNT"): "전표 안 마권 장수",
    ("BET_ORDER", "TOTAL_AMT"): "전표 총액(원). 취소는 음수",

    ("BET_TICKET", "TICKET_SEQ"): "전표 안 마권 순번", ("BET_TICKET", "CHUL_NO"): "고른 말의 마번",
    ("BET_TICKET", "HR_NM"): "고른 말의 마명", ("BET_TICKET", "CHUL_NO2"): "두 번째 말의 마번 (복승만)",
    ("BET_TICKET", "HR_NM2"): "두 번째 말의 마명 (복승만)", ("BET_TICKET", "UNIT_CNT"): "구좌 수 (금액 ÷ 100). 취소는 음수",
    ("BET_TICKET", "BET_AMT"): "마권 금액(원). 취소는 음수", ("BET_TICKET", "TICKET_STAT_CD"): "마권 상태",

    ("MBR_MASTER", "MBR_NO"): "회원번호", ("MBR_MASTER", "BIRTH_DT"): "생년월일", ("MBR_MASTER", "JOIN_DT"): "가입일",
    ("MBR_MASTER", "REGION_CD"): "거주 지역 (약칭)", ("MBR_MASTER", "MBR_GRADE_CD"): "회원 등급",
    ("MBR_MASTER", "MBR_STAT_CD"): "회원 상태 (숫자 모양이지만 문자 코드)",

    ("HR_WEEKLY_SNAPSHOT", "HR_BIRTH_DT"): "말 생일", ("HR_WEEKLY_SNAPSHOT", "HR_GRADE_CD"): "말 등급",
    ("HR_WEEKLY_SNAPSHOT", "TR_NM"): "조교사 이름. NULL = 외부마", ("HR_WEEKLY_SNAPSHOT", "TR_EXTERNAL_YN"): "외부마 여부",
    ("HR_WEEKLY_SNAPSHOT", "PRIZE_AMT"): "상금 합계(원)", ("HR_WEEKLY_SNAPSHOT", "INTRO_AMT"): "도입 가격(원). 자가생산은 NULL",
    ("HR_WEEKLY_SNAPSHOT", "INTRO_TYPE_NM"): "도입 유형", ("HR_WEEKLY_SNAPSHOT", "SIRE_NM"): "부마 (아버지 말)",
    ("HR_WEEKLY_SNAPSHOT", "DAM_NM"): "모마 (어머니 말)",

    ("TR_WEEKLY_SNAPSHOT", "TR_BIRTH_DT"): "조교사 생일", ("TR_WEEKLY_SNAPSHOT", "TR_AGE"): "조교사 나이",
    ("TR_WEEKLY_SNAPSHOT", "DEBUT_DT"): "조교사 데뷔일", ("TR_WEEKLY_SNAPSHOT", "TOT_RC_CNT"): "조교사 관리마의 통산 출전 수",

    ("RC_RACE", "MEET_CD"): "경마장", ("RC_RACE", "RC_DAY_SEQ"): "개최 일차", ("RC_RACE", "RC_DIST_M"): "경주 거리(m)",
    ("RC_RACE", "RC_GRADE_CD"): "경주 등급", ("RC_RACE", "BUDAM_TYPE_CD"): "부담 방식. NULL = 표기 없음",
    ("RC_RACE", "HR_CLASS_NM"): "마종", ("RC_RACE", "RC_TITLE_NM"): "경주명 (특별 경주만). NULL = 일반 경주",
    ("RC_RACE", "WEATHER_CD"): "날씨", ("RC_RACE", "TRACK_MOIST_RT"): "함수율(%). 주로 '불량'은 표기 없음",
    **{("RC_RACE", f"PRIZE{i}_AMT"): f"{i}위 상금(원)" for i in range(1, 6)},
    ("RC_RACE", "START_TM"): "출발 시각", ("RC_RACE", "START_DTM"): "출발 일시 (경주일 + 출발 시각)",

    ("RC_ODDS", "WIN_ODDS"): "단승 배당률(배). NULL = 뛰지 않은 말", ("RC_ODDS", "PLC_ODDS"): "연승 배당률(배). NULL = 뛰지 않은 말",
    **{("RC_ODDS", f"SECT{i}_SEC"): f"{i}번째 구간 기록(초). NULL = 그 구간 기록 없음" for i in range(1, 8)},

    ("RC_RESULT", "ENTRY_STAT_CD"): "출전 상태", ("RC_RESULT", "FINISH_ORD"): "착순. NULL = 뛰지 않은 말",
    ("RC_RESULT", "HR_WGT_KG"): "말 체중(kg)", ("RC_RESULT", "HR_WGT_DIFF_KG"): "지난번 대비 체중 증감(kg). NULL = 첫 측정 또는 뛰지 않음",
    ("RC_RESULT", "RC_TIME_SEC"): "경주 기록(초)", ("RC_RESULT", "MARGIN_CD"): "착차 종류",
    ("RC_RESULT", "MARGIN_LEN"): "착차 길이(마신). MARGIN_CD가 LEN일 때만",
    **{("RC_RESULT", f"PASS_ORD_S{i}"): f"{i}번째 구간 통과 순위. NULL = 기록 없음" for i in range(1, 7)},

    ("RC_SALES_TOTAL", "SALES_AMT"): "경주 전체 매출 합계(원)",

    ("HR_VET_HIST", "VET_DT"): "진료일", ("HR_VET_HIST", "TR_GRP_NO"): "진료 기록상의 소속 조 (스냅샷과 다를 수 있음)",
    ("HR_VET_HIST", "VET_PLACE_NM"): "진료 장소", ("HR_VET_HIST", "VET_NM"): "원본 진료명 (쉼표로 여러 개일 수 있음)",
    ("HR_VET_HIST", "REPORT_DT"): "진료 보고일", ("HR_VET_TYPE_BRIDGE", "VET_TYPE_NM"): "진료명 1개",

    ("RC_CHANGE_EVENT", "EVENT_TYPE_CD"): "공지 종류", ("RC_CHANGE_EVENT", "ANNOUNCE_DTM"): "공지 일시",
    ("RC_CHANGE_EVENT", "RC_DT"): "경주일. NULL = 주로상태 공지", ("RC_CHANGE_EVENT", "BEF_JK_NM"): "변경 전 기수",
    ("RC_CHANGE_EVENT", "AFT_JK_NM"): "변경 후 기수", ("RC_CHANGE_EVENT", "BUDAM_KG"): "변경 후 부담중량(kg)",
    ("RC_CHANGE_EVENT", "CHG_REASON_NM"): "기수변경 사유", ("RC_CHANGE_EVENT", "SCRATCH_REASON_NM"): "말취소 사유",
}

# ---------------------------------------------------------------- 코드 뜻 (매핑 규칙서 6장)
CODES = {
    "ORDER_TYPE_CD": {"SALE": "구매", "CANCEL": "취소"},
    "CHNL_CD": {"ONSITE": "현장", "APP": "온라인 앱", "OTB": "장외발매소", "UNKNOWN": "원천 빈칸"},
    "BET_TYPE_CD": {"WIN": "단승식: 1착 1두", "PLC": "연승식: 1~3착 안 1두", "QNL": "복승식: 1·2착 2두 순서 무관",
                    "QPL": "복연승식: 1~3착 안 2두 순서 무관", "EXA": "쌍승식: 1·2착 순서대로",
                    "TRI": "삼복승식: 1~3착 순서 무관", "TLA": "삼쌍승식: 1~3착 순서대로"},
    "TICKET_STAT_CD": {"SOLD": "정상 발매", "CANCEL": "발매 취소", "VOID": "출전취소로 무효"},
    "MBR_GRADE_CD": {"VIP": "VIP", "GOLD": "골드", "NORMAL": "일반"},
    "MBR_STAT_CD": {"10": "정상", "20": "휴면", "90": "탈퇴"},
    "HR_SEX_CD": {"M": "수말", "F": "암말", "G": "거세마"},
    "HR_GRADE_CD": {**{str(i): f"{i}등급" for i in range(1, 7)}, "NONE": "미등급"},
    "RC_GRADE_CD": {**{str(i): f"{i}등급 경주" for i in range(1, 7)}, "OPEN": "오픈 경주 (등급 구분 없음)"},
    "BUDAM_TYPE_CD": {"HANDICAP": "핸디캡 (능력에 따라 부담중량을 다르게)", "SPECIAL_A": "별정A"},
    "ENTRY_STAT_CD": {"RAN": "출주 (실제로 뜀)", "EXCLUDED": "경주제외 (원천 94)", "SCRATCHED": "출주취소 (원천 95)"},
    "MARGIN_CD": {"FIRST": "1착 (원천 빈칸)", "LEN": "마신 (말 몸 길이 단위)", "NOSE": "코 차이", "HEAD": "머리 차이",
                  "NECK": "목 차이", "DH": "동착 (원천 '동순위')", "NA": "해당 없음, 뛰지 않음 (원천 '-')"},
    "WEATHER_CD": {"CLEAR": "맑음", "CLOUDY": "흐림", "RAIN": "비", "FOG": "안개"},
    "TRACK_STAT_CD": {"DRY": "건조", "GOOD": "양호", "MOIST": "다습", "SATURATED": "포화", "SLOPPY": "불량 (가장 젖음)"},
    "EVENT_TYPE_CD": {"JOCKEY_CHANGE": "기수변경", "SCRATCH": "말취소", "TRACK_STATUS": "주로상태"},
    "MEET_CD": {"JEJU": "제주"},
    "TR_EXTERNAL_YN": {"Y": "외부마 (소속 조교사 없음)", "N": "소속 있음"},
}


# ---------------------------------------------------------------- 도구
def esc(x, n=40):
    s = str(x)
    s = s if len(s) <= n else s[:n] + "…"
    return s.replace("|", "\\|")


def pattern(x):
    x = re.sub(r"\d", "9", x)
    x = re.sub(r"[가-힣]", "가", x)
    x = re.sub(r"[A-Z]", "A", x)
    return re.sub(r"[a-z]", "a", x)


def desc(d, table, col):
    return d.get((table, col)) or d.get(("*", col)) or ""


def bronze_values(s):
    s = s.astype(str)
    blank = int(s.str.strip().eq("").sum())
    vals = s[s.str.strip().ne("")]
    vc = vals.value_counts()
    if len(vc) <= 12:
        shown = ", ".join(f"`{esc(v)}` {c:,}" for v, c in vc.items())
    else:
        shown = f"고유 {len(vc):,}개. 예: " + ", ".join(f"`{esc(v)}`" for v in vals.drop_duplicates().head(3))
        pats = vals.map(pattern).value_counts()
        # 자릿수만 다른 숫자(9 / 99 / 999)는 같은 형식으로 보고, 모양이 실제로 다를 때만 표시
        shapes = pd.Series(pats.index).str.replace(r"9+", "9", regex=True).str.replace(r"가+", "가", regex=True).nunique()
        if shapes > 1 and len(pats) <= 6 and pats.index.str.contains("9").any():
            shown += "<br>형식: " + ", ".join(f"`{esc(p)}` {c:,}" for p, c in pats.items())
    return blank, shown


def flatten_events(df):
    rows = []
    for s in df["RAW_JSON"]:
        j, r = json.loads(s), {}
        for k, v in j.items():
            if isinstance(v, dict):
                r.update({f"{k}.{kk}": str(vv) for kk, vv in v.items()})
            else:
                r[k] = str(v)
        rows.append(r)
    return pd.DataFrame(rows).fillna("")


# ---------------------------------------------------------------- Bronze 문서
def bronze_doc():
    out = ["# Bronze 컬럼 사전", "",
           "> `src/make_column_docs.py`가 만든 문서입니다. 건수·예시는 데이터에서 계산합니다. 데이터가 바뀌면 다시 실행하세요.", "",
           "- Bronze는 원천 값을 **그대로**(전부 문자열) 둡니다. 그래서 여기 보이는 값이 원천 파일의 값입니다.",
           "- **빈칸**: 빈 문자열이거나 공백만 있는 칸의 수",
           "- **값**: 값 종류가 12개 이하이면 전부 표시하고, 많으면 예시 3개를 보여줍니다.",
           "- **형식**: 숫자를 9, 한글을 가, 영문을 A/a로 바꿔 모양별로 센 것입니다. 한 컬럼에 형식이 섞여 있으면 표시합니다.",
           "- **Silver에서**: 이 원천 컬럼이 Silver의 어느 컬럼이 되었는지 (`meta/data_dictionary.csv` 기준)", "",
           "## 모든 Bronze 테이블에 붙은 메타 컬럼", "",
           "| 컬럼 | 뜻 |", "|:--|:--|",
           "| `_SRC_SYSTEM` | 원천 시스템 (bet / mbr / hms / rms / vms / mongodb) |",
           "| `_LOAD_FILE` | 원천 파일 경로 (`data/00_origin/` 기준) |",
           "| `_LOAD_DTM` | 적재 시각 (KST). 원천 파일 해시가 같으면 처음 기록한 시각을 다시 씀 |",
           "| `_SRC_ROW_NO` | 원천 파일의 데이터 행 번호 (첫 데이터 행 = 1). Silver·이슈 로그가 이 번호로 원천 행을 가리킴 |", ""]
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    silver_of = {"bet_order": ["BET_ORDER"], "bet_ticket": ["BET_TICKET"], "RC_SALES": ["RC_SALES", "RC_SALES_TOTAL"],
                 "HR_VET_HIST": ["HR_VET_HIST", "HR_VET_TYPE_BRIDGE"], "race_change_events": ["RC_CHANGE_EVENT"]}
    for src in C.SOURCES:
        name = src["bronze"]
        df = pd.read_parquet(C.BRONZE_DIR / f"{name}.parquet")
        if name == "race_change_events":
            df = flatten_events(df)
        tables = silver_of.get(name, [name])
        d = dic[dic.TABLE_NM.isin(tables)]
        out += [f"## {name}", "",
                f"- 원천: `data/00_origin/{src['file']}` · 시스템 `{src['system']}` · **{len(df):,}행**",
                f"- 한 행 = {BRONZE_TABLES[name]}"]
        if name == "race_change_events":
            out += ["- Bronze에는 `RAW_JSON` 한 컬럼에 원문이 들어 있습니다. 아래는 그 JSON을 키별로 펼쳐서 센 것입니다.",
                    "- 공지 종류마다 있는 키가 달라서, 없는 키는 빈칸으로 셉니다."]
        out += ["", "| 컬럼 | 뜻 | 빈칸 | 값 | Silver에서 |", "|:--|:--|--:|:--|:--|"]
        for c in [c for c in df.columns if not c.startswith("_")]:
            blank, shown = bronze_values(df[c])
            tgt = d[d.SRC_COL.str.split(r" \+ ").map(lambda xs: c in xs)]
            tgt_s = ", ".join(
                "(제외: " + r.RULE + ")" if r.COL_NM == "(제외)" else (f"{r.TABLE_NM}." if len(tables) > 1 else "") + f"`{r.COL_NM}`"
                for r in tgt.itertuples())
            out.append(f"| `{c}` | {desc(B, name, c)} | {blank:,} | {shown} | {tgt_s} |")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- Silver 문서
def silver_values(s, col, typ):
    nn = s.dropna()
    if col in CODES or (typ.startswith(("CODE", "CHAR", "VARCHAR")) and nn.nunique() <= 12):
        vc = nn.astype(str).value_counts()
        mean = CODES.get(col, {})
        if len(vc) > 12:
            return f"고유 {len(vc):,}개. 예: " + ", ".join(f"`{esc(v)}`" for v in vc.index[:5])
        return "<br>".join(f"`{esc(v)}` {c:,}" + (f" {mean[v]}" if v in mean else "") for v, c in vc.items())
    if len(nn) == 0:
        return "(전부 NULL)"
    if typ in ("INT", "BIGINT"):
        nn = nn.astype("int64")
    if typ.startswith(("VARCHAR", "CHAR", "CODE")):
        return f"고유 {nn.nunique():,}개. 예: " + ", ".join(f"`{esc(v)}`" for v in nn.drop_duplicates().head(3))
    return f"{esc(nn.min())} ~ {esc(nn.max())}"


def silver_doc():
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    issues = pd.read_csv(C.SILVER_ISSUE_LOG, dtype=str, keep_default_na=False)
    rn = issues[issues.ISSUE_CD == "RULE_NULL"].groupby(["TABLE_NM", "COL_NM", "NOTE"]).size()
    out = ["# Silver 컬럼 사전", "",
           "> `src/make_column_docs.py`가 만든 문서입니다. 건수·값 목록·범위는 데이터에서 계산합니다. 데이터가 바뀌면 다시 실행하세요.", "",
           "- **타입**: 표준 타입 (`meta/data_dictionary.csv`). CODE는 코드표 값만 들어가는 문자 컬럼입니다.",
           "- **NULL**: 빈 값 수와 이유",
           "  - '규칙': 원천에 값이 있었는데 규칙에 따라 NULL로 둔 것입니다. 원천값은 `meta/silver_issue_log.csv`에 있습니다.",
           "  - '원천 빈칸·해당 없음': 원천이 빈칸이었거나, 해당 사항이 없는 것입니다 (예: 복승이 아니라서 두 번째 말 없음).",
           "- **값**: 코드는 값마다 건수와 뜻을, 숫자·날짜는 최솟값~최댓값을, 글자는 고유 개수와 예시를 보여줍니다.",
           "- **원천 → 규칙**: 어느 Bronze 컬럼에서 어떤 규칙으로 만들었나",
           "- 모든 테이블 마지막 컬럼 `_SRC_ROW_NO`는 Bronze 행 번호입니다. 같은 번호의 Bronze 행에 원천값이 있습니다.", ""]
    for t, meaning in SILVER_TABLES.items():
        df = pd.read_parquet(C.SILVER_DIR / f"{t}.parquet")
        d = dic[dic.TABLE_NM == t]
        excl = d[d.COL_NM == "(제외)"]
        out += [f"## {t}", "", f"- 한 행 = {meaning} · **{len(df):,}행**"]
        if len(excl):
            out.append("- 제외한 원천 컬럼: " + ", ".join(f"`{r.SRC_COL}` ({r.RULE})" for r in excl.itertuples()))
        out += ["", "| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |", "|:--|:--|:--|:--|:--|:--|"]
        for r in d[d.COL_NM != "(제외)"].itertuples():
            s = df[r.COL_NM]
            n_null = int(s.isna().sum())
            parts = [f"규칙 {n:,}: {note}" for (tt, cc, note), n in rn.items() if tt == t and cc == r.COL_NM]
            ruled = sum(n for (tt, cc, _), n in rn.items() if tt == t and cc == r.COL_NM)
            if r.COL_NM.startswith("PASS_ORD_S") and r.COL_NM != "PASS_ORD_S1":
                same = sum(n for (tt, cc, _), n in rn.items() if tt == t and cc == "PASS_ORD_S1")
                parts.append(f"규칙 {same:,}: S1과 같은 행 (통과 순위 기록 없음)")
                ruled += same
            if n_null - ruled > 0:
                parts.append(f"원천 빈칸·해당 없음 {n_null - ruled:,}")
            null_s = f"{n_null:,}" + (" (" + "; ".join(parts) + ")" if n_null and parts else "")
            out.append(f"| `{r.COL_NM}` | {desc(S, t, r.COL_NM)} | {r.DATA_TYPE} | {esc(null_s, 200)} | "
                       f"{silver_values(s, r.COL_NM, r.DATA_TYPE)} | `{esc(r.SRC_COL)}` → {esc(r.RULE, 80)} |")
        out.append("")
    return "\n".join(out)


def main():
    docs = C.ROOT / "docs"
    (docs / "BRONZE_COLUMNS.md").write_text(bronze_doc(), encoding="utf-8")
    (docs / "SILVER_COLUMNS.md").write_text(silver_doc(), encoding="utf-8")
    missing_b = [(s["bronze"], c) for s in C.SOURCES
                 for c in (flatten_events(pd.read_parquet(C.BRONZE_DIR / "race_change_events.parquet")).columns
                           if s["bronze"] == "race_change_events" else pd.read_parquet(C.BRONZE_DIR / f"{s['bronze']}.parquet").columns)
                 if not c.startswith("_") and not desc(B, s["bronze"], c)]
    dic = pd.read_csv(C.DATA_DICTIONARY, dtype=str, keep_default_na=False)
    missing_s = [(r.TABLE_NM, r.COL_NM) for r in dic[dic.COL_NM != "(제외)"].itertuples() if not desc(S, r.TABLE_NM, r.COL_NM)]
    print("docs/BRONZE_COLUMNS.md, docs/SILVER_COLUMNS.md 생성")
    print("뜻이 비어 있는 컬럼 - Bronze:", missing_b or "없음", "/ Silver:", missing_s or "없음")


if __name__ == "__main__":
    main()
