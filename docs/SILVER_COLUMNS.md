# Silver 컬럼 사전

> `src/make_column_docs.py`가 만든 문서입니다. 건수·값 목록·범위는 데이터에서 계산합니다. 데이터가 바뀌면 다시 실행하세요.

- **타입**: 표준 타입 (`meta/data_dictionary.csv`). CODE는 코드표 값만 들어가는 문자 컬럼입니다.
- **NULL**: 빈 값 수와 이유
  - '규칙': 원천에 값이 있었는데 규칙에 따라 NULL로 둔 것입니다. 원천값은 `meta/silver_issue_log.csv`에 있습니다.
  - '원천 빈칸·해당 없음': 원천이 빈칸이었거나, 해당 사항이 없는 것입니다 (예: 복승이 아니라서 두 번째 말 없음).
- **값**: 코드는 값마다 건수와 뜻을, 숫자·날짜는 최솟값~최댓값을, 글자는 고유 개수와 예시를 보여줍니다.
- **원천 → 규칙**: 어느 Bronze 컬럼에서 어떤 규칙으로 만들었나
- 모든 테이블 마지막 컬럼 `_SRC_ROW_NO`는 Bronze 행 번호입니다. 같은 번호의 Bronze 행에 원천값이 있습니다.

## BET_ORDER

- 한 행 = 전표 1건 · **27,907행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `ORDER_NO` | 전표번호 | VARCHAR(10) | 0 | 고유 27,907개. 예: `BC00489449`, `BC00489459`, `BC00489476` | `order_no` → TRIM, 빈칸 NULL |
| `ORDER_TYPE_CD` | 전표 종류 | CODE | 0 | `SALE` 23,802 구매<br>`CANCEL` 4,105 취소 | `order_type_cd` → 코드그룹 ORDER_TYPE 매핑 |
| `ORIG_ORDER_NO` | 취소 전표가 가리키는 원래 구매 전표번호 | VARCHAR(10) | 24,446 (원천 빈칸·해당 없음 24,446) | 고유 2,962개. 예: `BS00489465`, `BS00489560`, `BS00489564` | `orig_order_no` → TRIM, 빈칸 NULL |
| `MBR_NO` | 회원번호 (대문자, 공백 제거). NULL = 비회원 | VARCHAR(8) | 4,921 (원천 빈칸·해당 없음 4,921) | 고유 4,314개. 예: `M0016321`, `M0017592`, `M0013293` | `member_no` → TRIM + 대문자, 빈칸 NULL(비회원) |
| `CHNL_CD` | 판매 채널 | CODE | 0 | `ONSITE` 25,991 현장<br>`OTB` 1,543 장외발매소<br>`APP` 360 온라인 앱<br>`UNKNOWN` 13 원천 빈칸 | `channel_cd` → ONSITE/APP 그대로, OTBnn→OTB, 빈칸→UNKNOWN |
| `OTB_BRANCH_NO` | 장외발매소 지점 번호 (OTB일 때만) | VARCHAR(2) | 26,364 (원천 빈칸·해당 없음 26,364) | 고유 37개. 예: `01`, `12`, `19` | `channel_cd` → OTBnn의 nn |
| `SALE_DTM` | 판매 일시 (KST) | TIMESTAMP | 0 | 2026-05-22 07:01:00 ~ 2026-11-14 15:56:00 | `sale_dtm` → 형식 %Y-%m-%d %H:%M:%S → %Y%m%d%H%M%S 순서로 시도 |
| `BIZ_DT` | 영업일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `biz_date` → 형식 %Y%m%d 순서로 시도 |
| `TICKET_CNT` | 전표 안 마권 장수 | INT | 0 | 1 ~ 674 | `ticket_cnt` → 전표 안 마권 장수 |
| `TOTAL_AMT` | 전표 총액(원). 취소는 음수 | BIGINT | 0 | -453900 ~ 448500 | `total_amt` → 취소는 음수 그대로 |

## BET_TICKET

- 한 행 = 전표 안의 마권 1개 · **523,416행**
- 제외한 원천 컬럼: `unit_amt` (전부 100 (상수))

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `ORDER_NO` | 전표번호 | VARCHAR(10) | 0 | 고유 27,907개. 예: `BC00489449`, `BC00489459`, `BC00489476` | `order_no` → TRIM, 빈칸 NULL |
| `TICKET_SEQ` | 전표 안 마권 순번 | INT | 0 | 1 ~ 674 | `ticket_seq` → 정수 변환 |
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `rc_date` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `rc_no` → 정수 변환 |
| `BET_TYPE_CD` | 승식 | CODE | 0 | `WIN` 255,993 단승식: 1착 1두<br>`PLC` 160,114 연승식: 1~3착 안 1두<br>`QNL` 107,309 복승식: 1·2착 2두 순서 무관 | `bet_type_cd` → 단승/연승/복승 한글 → WIN/PLC/QNL |
| `CHUL_NO` | 고른 말의 마번 | INT | 0 | 1 ~ 10 | `chul_no` → 정수 변환 |
| `HR_NM` | 고른 말의 마명 | VARCHAR | 1,563 (원천 빈칸·해당 없음 1,563) | 고유 833개. 예: `일사만리`, `홍의여걸`, `청룡시대` | `hr_name` → TRIM, 빈칸 NULL |
| `CHUL_NO2` | 두 번째 말의 마번 (복승만) | INT | 416,107 (원천 빈칸·해당 없음 416,107) | 1 ~ 10 | `chul_no2` → 복승만, 빈칸 NULL |
| `HR_NM2` | 두 번째 말의 마명 (복승만) | VARCHAR | 416,107 (원천 빈칸·해당 없음 416,107) | 고유 832개. 예: `한백제왕`, `소문그대로`, `한빛제일` | `hr_name2` → TRIM, 빈칸 NULL |
| `UNIT_CNT` | 구좌 수 (금액 ÷ 100). 취소는 음수 | INT | 0 | -500 ~ 500 | `ticket_cnt` → 구좌 수 (이름 충돌: bet_order.ticket_cnt와 구분) |
| `BET_AMT` | 마권 금액(원). 취소는 음수 | INT | 0 | -50000 ~ 50000 | `bet_amt` → 취소는 음수 그대로 |
| `TICKET_STAT_CD` | 마권 상태 | CODE | 0 | `SOLD` 512,032 정상 발매<br>`CANCEL` 9,610 발매 취소<br>`VOID` 1,774 출전취소로 무효 | `ticket_status` → 대문자 통일 |

## MBR_MASTER

- 한 행 = 회원 1명 · **4,383행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `MBR_NO` | 회원번호 | VARCHAR(8) | 0 | 고유 4,383개. 예: `M0012346`, `M0012347`, `M0012348` | `MBR_NO` → TRIM, 빈칸 NULL |
| `BIRTH_DT` | 생년월일 | DATE | 27 (원천 빈칸·해당 없음 27) | 1936-07-04 ~ 2005-09-08 | `BIRTH_DT` → 형식 %Y%m%d → %Y-%m-%d → %Y.%m.%d 순서로 시도 |
| `JOIN_DT` | 가입일 | DATE | 0 | 2021-06-21 ~ 2026-11-03 | `JOIN_DT` → 형식 %Y%m%d 순서로 시도 |
| `REGION_CD` | 거주 지역 (약칭) | CODE | 0 | `제주` 1,430<br>`경북` 314<br>`인천` 308<br>`경기` 307<br>`부산` 303<br>`대전` 295<br>`광주` 293<br>`경남` 287<br>`대구` 285<br>`전남` 284<br>`서울` 277 | `REGION_NM` → 정식 명칭 → 약칭 |
| `MBR_GRADE_CD` | 회원 등급 | CODE | 0 | `NORMAL` 3,287 일반<br>`GOLD` 876 골드<br>`VIP` 220 VIP | `MBR_GRADE_CD` → 코드그룹 MBR_GRADE 매핑 |
| `MBR_STAT_CD` | 회원 상태 (숫자 모양이지만 문자 코드) | CODE | 0 | `10` 3,479 정상<br>`20` 812 휴면<br>`90` 92 탈퇴 | `MBR_STAT_CD` → 숫자 모양 코드, 문자 유지 |

## HR_WEEKLY_SNAPSHOT

- 한 행 = 주간 기준일의 말 1두 상태 · **52,642행**
- 제외한 원천 컬럼: `PRD_NM` (전부 '제' (상수))

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `SNAPSHOT_DT` | 스냅샷 기준일 | DATE | 0 | 2026-05-20 ~ 2026-11-18 | `SNAPSHOT_DT` → 형식 %Y%m%d 순서로 시도 |
| `HR_NM` | 마명 (말 연결 키) | VARCHAR | 0 | 고유 1,250개. 예: `가라공주`, `가문의여신`, `가속의힘` | `HR_NAME` → TRIM, 빈칸 NULL |
| `HR_SEX_CD` | 말 성별 | CODE | 0 | `G` 25,934 거세마<br>`F` 18,797 암말<br>`M` 7,911 수말 | `SEX_NM` → 수/암/거 → M/F/G |
| `HR_BIRTH_DT` | 말 생일 | DATE | 0 | 2010-01-23 ~ 2024-08-10 | `BIRTH_RAW` → 형식 %Y/%m/%d 순서로 시도 |
| `HR_AGE` | 말 나이 | INT | 0 | 2 ~ 16 | `AGE_RAW` → 정수 변환 |
| `HR_GRADE_CD` | 말 등급 | CODE | 0 | `5` 12,325 5등급<br>`4` 10,419 4등급<br>`6` 10,040 6등급<br>`NONE` 8,258 미등급<br>`3` 6,190 3등급<br>`1` 2,836 1등급<br>`2` 2,574 2등급 | `GRADE_RAW` → 제1~제6/미 → 1~6/NONE |
| `TR_GRP_NO` | 소속 조 번호 (앞 0 유지). 88 = 외부마 | VARCHAR(2) | 0 | 고유 19개. 예: `88`, `08`, `09` | `TR_GRP_NO` → 앞 0 유지 |
| `TR_NM` | 조교사 이름. NULL = 외부마 | VARCHAR | 25,428 (규칙 25,428: '외부마'는 사람 이름이 아님 → TR_EXTERNAL_YN=Y) | 고유 18개. 예: `문성호`, `강태종`, `강영진` | `TR_NAME` → '외부마' → NULL |
| `TR_EXTERNAL_YN` | 외부마 여부 | CHAR(1) | 0 | `N` 27,214 소속 있음<br>`Y` 25,428 외부마 (소속 조교사 없음) | `TR_NAME` → '외부마'면 Y, 아니면 N |
| `OW_NM` | 마주 이름 | VARCHAR | 0 | 고유 168개. 예: `조종호`, `김영구`, `고영조` | `OW_NAME` → TRIM, 빈칸 NULL |
| `TOT_RC_CNT` | 통산 출전 수 | INT | 0 | 0 ~ 142 | `TOT_RC_CNT` → 정수 변환 |
| `TOT_1ST_CNT` | 통산 1착 수 | INT | 0 | 0 ~ 34 | `TOT_1ST` → 정수 변환 |
| `TOT_2ND_CNT` | 통산 2착 수 | INT | 0 | 0 ~ 20 | `TOT_2ND` → 정수 변환 |
| `TOT_3RD_CNT` | 통산 3착 수 | INT | 0 | 0 ~ 20 | `TOT_3RD` → 정수 변환 |
| `Y1_RC_CNT` | 최근 1년 출전 수 | INT | 0 | 0 ~ 25 | `Y1_RC_CNT` → 정수 변환 |
| `Y1_1ST_CNT` | 최근 1년 1착 수 | INT | 0 | 0 ~ 8 | `Y1_1ST` → 정수 변환 |
| `Y1_2ND_CNT` | 최근 1년 2착 수 | INT | 0 | 0 ~ 6 | `Y1_2ND` → 정수 변환 |
| `Y1_3RD_CNT` | 최근 1년 3착 수 | INT | 0 | 0 ~ 6 | `Y1_3RD` → 정수 변환 |
| `PRIZE_AMT` | 상금 합계(원) | BIGINT | 0 | 0 ~ 1171053260 | `PRIZE_AMT_RAW` → 정수 변환 |
| `RATING_VAL` | 레이팅 (말 능력 점수) | INT | 18,298 (원천 빈칸·해당 없음 18,298) | 1 ~ 143 | `RATING_RAW` → 빈칸 NULL |
| `INTRO_AMT` | 도입 가격(원). 자가생산은 NULL | BIGINT | 12,363 (규칙 12,363: '자가생산'은 금액 없음) | 1000000 ~ 150000000 | `INTRO_PRICE_RAW` → 천원 → 원 (×1,000) |
| `INTRO_TYPE_NM` | 도입 유형 | VARCHAR | 0 | `개별` 40,279<br>`자가생산` 12,363 | `INTRO_PRICE_RAW` → 괄호 안 유형, '자가생산'은 그대로 |
| `SIRE_NM` | 부마 (아버지 말) | VARCHAR | 0 | 고유 85개. 예: `화룡특급`, `오라태양`, `일대태수` | `SIRE_NAME` → TRIM, 빈칸 NULL |
| `DAM_NM` | 모마 (어머니 말) | VARCHAR | 397 (원천 빈칸·해당 없음 397) | 고유 617개. 예: `희망여신`, `가문의전설`, `세계의보물` | `DAM_NAME` → TRIM, 빈칸 NULL |

## TR_WEEKLY_SNAPSHOT

- 한 행 = 주간 기준일의 조교사 1명 상태 · **954행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `SNAPSHOT_DT` | 스냅샷 기준일 | DATE | 0 | 2026-05-20 ~ 2026-11-18 | `SNAPSHOT_DT` → 형식 %Y%m%d 순서로 시도 |
| `TR_NM` | 조교사 이름 | VARCHAR | 0 | 고유 18개. 예: `강대은`, `강영진`, `강태종` | `TR_NAME` → TRIM, 빈칸 NULL |
| `TR_GRP_NO` | 소속 조 번호 (앞 0 유지). 88 = 외부마 | VARCHAR(2) | 0 | 고유 18개. 예: `03`, `15`, `09` | `GRP_NO` → 이름 통일 GRP_NO → TR_GRP_NO, 앞 0 유지 |
| `TR_BIRTH_DT` | 조교사 생일 | DATE | 0 | 1964-01-04 ~ 1972-05-14 | `BIRTH_RAW` → 형식 %Y/%m/%d 순서로 시도 |
| `TR_AGE` | 조교사 나이 | INT | 0 | 54 ~ 62 | `AGE_RAW` → 정수 변환 |
| `DEBUT_DT` | 조교사 데뷔일 | DATE | 0 | 1994-01-01 ~ 2025-10-01 | `DEBUT_RAW` → 형식 %Y/%m/%d 순서로 시도 |
| `TOT_RC_CNT` | 조교사 관리마의 통산 출전 수 | INT | 0 | 183 ~ 14145 | `TOT_RC_CNT` → 정수 변환 |
| `TOT_1ST_CNT` | 통산 1착 수 | INT | 0 | 10 ~ 1559 | `TOT_1ST` → 정수 변환 |
| `TOT_2ND_CNT` | 통산 2착 수 | INT | 0 | 14 ~ 1418 | `TOT_2ND` → 정수 변환 |
| `TOT_3RD_CNT` | 통산 3착 수 | INT | 0 | 18 ~ 1433 | `TOT_3RD` → 정수 변환 |
| `Y1_RC_CNT` | 최근 1년 출전 수 | INT | 0 | 183 ~ 545 | `Y1_RC_CNT` → 정수 변환 |
| `Y1_1ST_CNT` | 최근 1년 1착 수 | INT | 0 | 6 ~ 118 | `Y1_1ST` → 정수 변환 |
| `Y1_2ND_CNT` | 최근 1년 2착 수 | INT | 0 | 10 ~ 87 | `Y1_2ND` → 정수 변환 |
| `Y1_3RD_CNT` | 최근 1년 3착 수 | INT | 0 | 14 ~ 71 | `Y1_3RD` → 정수 변환 |

## RC_RACE

- 한 행 = 경주 1개 · **386행**
- 제외한 원천 컬럼: `TITLE_RAW` (RC_DT·RC_NO와 중복), `RC_DOW` (날짜에서 계산 (DIM_DATE)), `DIVIDEND_RAW` (RC_ODDS와 내용 중복)

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `MEET_CD` | 경마장 | CODE | 0 | `JEJU` 386 제주 | `MEET_NM` → 코드그룹 MEET 매핑 |
| `RC_DAY_SEQ` | 개최 일차 | INT | 0 | 40 ~ 91 | `RC_DAY_RAW` → 숫자만 |
| `RC_DIST_M` | 경주 거리(m) | INT | 0 | 900 ~ 1610 | `RC_DIST_RAW` → 숫자만 |
| `RC_GRADE_CD` | 경주 등급 | CODE | 0 | `5` 114 5등급 경주<br>`4` 100 4등급 경주<br>`6` 75 6등급 경주<br>`3` 59 3등급 경주<br>`2` 19 2등급 경주<br>`1` 13 1등급 경주<br>`OPEN` 6 오픈 경주 (등급 구분 없음) | `RANK_RAW` → RANK_RAW 앞부분 → 1~6/OPEN |
| `BUDAM_TYPE_CD` | 부담 방식. NULL = 표기 없음 | CODE | 6 (원천 빈칸·해당 없음 6) | `HANDICAP` 305 핸디캡 (능력에 따라 부담중량을 다르게)<br>`SPECIAL_A` 75 별정A | `RANK_RAW` → RANK_RAW 뒷부분 핸디캡/별정A → HANDICAP/SPECIAL_A, 없으면 NULL |
| `HR_CLASS_NM` | 마종 | VARCHAR | 0 | `제주마` 386 | `RC_COND_RAW` → 앞 '핸디캡' 제거 후 마종 |
| `RC_TITLE_NM` | 경주명 (특별 경주만). NULL = 일반 경주 | VARCHAR | 361 (규칙 361: '일반'은 경주명 없음) | 고유 25개. 예: `제21회 KCTV배`, `제주마사랑`, `(주)한라산배 희망제주! 기념경주` | `RC_COND_RAW` → 마종 뒤 경주명, '일반'이면 NULL |
| `WEATHER_CD` | 날씨 | CODE | 0 | `CLEAR` 268 맑음<br>`CLOUDY` 93 흐림<br>`RAIN` 21 비<br>`FOG` 4 안개 | `WEATHER_TRACK_RAW` → 코드그룹 WEATHER 매핑 |
| `TRACK_STAT_CD` | 주로 상태 | CODE | 0 | `DRY` 215 건조<br>`MOIST` 57 다습<br>`GOOD` 53 양호<br>`SATURATED` 40 포화<br>`SLOPPY` 21 불량 (가장 젖음) | `WEATHER_TRACK_RAW` → 코드그룹 TRACK_STAT 매핑 |
| `TRACK_MOIST_RT` | 함수율(%). 주로 '불량'은 표기 없음 | DECIMAL(5,1) | 21 (규칙 21: 함수율 표기 없음 (주로 '불량')) | 2.0 ~ 18.0 | `WEATHER_TRACK_RAW` → 괄호 안 함수율(%) |
| `PRIZE1_AMT` | 1위 상금(원) | BIGINT | 0 | 7000000 ~ 75000000 | `PRIZE_RAW` → 1위 상금, 만원 → 원 (×10,000) |
| `PRIZE2_AMT` | 2위 상금(원) | BIGINT | 0 | 3220000 ~ 34500000 | `PRIZE_RAW` → 2위 상금, 만원 → 원 (×10,000) |
| `PRIZE3_AMT` | 3위 상금(원) | BIGINT | 0 | 2100000 ~ 22500000 | `PRIZE_RAW` → 3위 상금, 만원 → 원 (×10,000) |
| `PRIZE4_AMT` | 4위 상금(원) | BIGINT | 0 | 980000 ~ 10500000 | `PRIZE_RAW` → 4위 상금, 만원 → 원 (×10,000) |
| `PRIZE5_AMT` | 5위 상금(원) | BIGINT | 0 | 700000 ~ 7500000 | `PRIZE_RAW` → 5위 상금, 만원 → 원 (×10,000) |
| `START_TM` | 출발 시각 | TIME | 0 | 10:45:00 ~ 19:55:00 | `START_TM_RAW` → HH:MI → HH:MI:00 |
| `START_DTM` | 출발 일시 (경주일 + 출발 시각) | TIMESTAMP | 0 | 2026-05-22 10:45:00 ~ 2026-11-14 16:35:00 | `RC_DATE + START_TM_RAW` → RC_DT + START_TM |

## RC_ENTRY

- 한 행 = 출전마 1두 · **3,666행**
- 제외한 원천 컬럼: `ORD_RAW` (RC_RESULT.FINISH_ORD 사용 (중복)), `HR_BREED` (전부 '제' (상수))

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `CHUL_NO` | 마번 | INT | 0 | 1 ~ 10 | `CHUL_NO` → 정수 변환 |
| `HR_NM` | 마명 (말 연결 키) | VARCHAR | 0 | 고유 833개. 예: `센돌이`, `전설마루`, `달의울림` | `HR_NAME` → TRIM, 빈칸 NULL |
| `HR_SEX_CD` | 말 성별 | CODE | 0 | `G` 1,936 거세마<br>`F` 1,164 암말<br>`M` 566 수말 | `HR_SEX` → 수/암/거 → M/F/G |
| `HR_AGE` | 말 나이 | INT | 0 | 2 ~ 15 | `HR_AGE` → 정수 변환 |
| `BUDAM_KG` | 부담중량(kg) | DECIMAL(4,1) | 0 | 51.0 ~ 64.0 | `WG_BUDAM_RAW` → 부담중량(kg) |
| `JK_NM` | 기수 이름 | VARCHAR | 0 | 고유 24개. 예: `박성광`, `이성민`, `전현준` | `JK_NAME` → TRIM, 빈칸 NULL |
| `TR_NM` | 조교사 이름 | VARCHAR | 0 | 고유 18개. 예: `이태용`, `고영덕`, `최기호` | `TR_NAME` → TRIM, 빈칸 NULL |
| `OW_NM` | 마주 이름 | VARCHAR | 0 | 고유 160개. 예: `오치영`, `김창균`, `문귀임` | `OW_NAME` → TRIM, 빈칸 NULL |
| `RATING_VAL` | 레이팅 (말 능력 점수) | INT | 716 (원천 빈칸·해당 없음 716) | 1 ~ 143 | `RATING_RAW` → 빈칸 NULL |

## RC_ODDS

- 한 행 = 출전마 1두의 배당률·구간 기록 · **3,666행**
- 제외한 원천 컬럼: `ORD_RAW` (RC_RESULT.FINISH_ORD 사용 (중복))

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `CHUL_NO` | 마번 | INT | 0 | 1 ~ 10 | `CHUL_NO` → 정수 변환 |
| `SECT1_SEC` | 1번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 22 (원천 빈칸·해당 없음 22) | 45.3 ~ 62.0 | `SECTION_TIMES_RAW` → 7글자 고정폭 1번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT2_SEC` | 2번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 22 (원천 빈칸·해당 없음 22) | 16.2 ~ 23.3 | `SECTION_TIMES_RAW` → 7글자 고정폭 2번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT3_SEC` | 3번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 3,640 (원천 빈칸·해당 없음 3,640) | 17.0 ~ 19.9 | `SECTION_TIMES_RAW` → 7글자 고정폭 3번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT4_SEC` | 4번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 3,399 (원천 빈칸·해당 없음 3,399) | 9.2 ~ 35.5 | `SECTION_TIMES_RAW` → 7글자 고정폭 4번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT5_SEC` | 5번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 22 (원천 빈칸·해당 없음 22) | 23.6 ~ 86.9 | `SECTION_TIMES_RAW` → 7글자 고정폭 5번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT6_SEC` | 6번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 22 (원천 빈칸·해당 없음 22) | 38.2 ~ 103.2 | `SECTION_TIMES_RAW` → 7글자 고정폭 6번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `SECT7_SEC` | 7번째 구간 기록(초). NULL = 그 구간 기록 없음 | DECIMAL(5,1) | 22 (원천 빈칸·해당 없음 22) | 14.4 ~ 25.3 | `SECTION_TIMES_RAW` → 7글자 고정폭 7번째 칸, m:ss.s → 초, 빈 칸 NULL |
| `WIN_ODDS` | 단승 배당률(배). NULL = 뛰지 않은 말 | DECIMAL(6,1) | 22 (규칙 22: '-----' = 값 없음) | 1.2 ~ 195.6 | `WIN_ODDS_RAW` → '-----' → NULL |
| `PLC_ODDS` | 연승 배당률(배). NULL = 뛰지 않은 말 | DECIMAL(6,1) | 22 (규칙 22: '-----' = 값 없음) | 1.0 ~ 32.3 | `PLACE_ODDS_RAW` → '-----' → NULL |

## RC_RESULT

- 한 행 = 출전마 1두의 경주 결과 · **3,666행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `ENTRY_STAT_CD` | 출전 상태 | CODE | 0 | `RAN` 3,644 출주 (실제로 뜀)<br>`EXCLUDED` 18 경주제외 (원천 94)<br>`SCRATCHED` 4 출주취소 (원천 95) | `ORD_RAW` → 1~10 RAN / 94 EXCLUDED / 95 SCRATCHED |
| `FINISH_ORD` | 착순. NULL = 뛰지 않은 말 | INT | 22 (규칙 22: 94·95는 순위 아님) | 1 ~ 10 | `ORD_RAW` → RAN만 순위, 94·95는 NULL |
| `CHUL_NO` | 마번 | INT | 0 | 1 ~ 10 | `CHUL_NO` → 정수 변환 |
| `HR_NM` | 마명 (말 연결 키) | VARCHAR | 0 | 고유 833개. 예: `센돌이`, `전설마루`, `달의울림` | `HR_NAME` → TRIM, 빈칸 NULL |
| `HR_WGT_KG` | 말 체중(kg) | INT | 22 (규칙 22: '0' → 체중·증감 NULL (경주제외·출주취소)) | 210 ~ 341 | `WG_HR_RAW` → '279+14'의 279, '0'은 NULL |
| `HR_WGT_DIFF_KG` | 지난번 대비 체중 증감(kg). NULL = 첫 측정 또는 뛰지 않음 | INT | 389 (원천 빈칸·해당 없음 389) | -35 ~ 34 | `WG_HR_RAW` → '279+14'의 +14, 증감 없으면 NULL |
| `RC_TIME_SEC` | 경주 기록(초) | DECIMAL(5,1) | 22 (규칙 22: '경주제외'·'출주취소'는 기록 없음) | 71.1 ~ 138.5 | `RC_TIME_RAW` → m:ss.s → 초 |
| `MARGIN_LEN` | 착차 길이(마신). MARGIN_CD가 LEN일 때만 | DECIMAL(5,2) | 969 (원천 빈칸·해당 없음 969) | 0.50 ~ 72.00 | `MARGIN_RAW` → ½=0.5 ¼=0.25 ¾=0.75, 말 길이 수 |
| `MARGIN_CD` | 착차 종류 | CODE | 0 | `LEN` 2,697 마신 (말 몸 길이 단위)<br>`FIRST` 386 1착 (원천 빈칸)<br>`NECK` 223 목 차이<br>`HEAD` 191 머리 차이<br>`NOSE` 146 코 차이<br>`NA` 22 해당 없음, 뛰지 않음 (원천 '-')<br>`DH` 1 동착 (원천 '동순위') | `MARGIN_RAW` → 숫자 LEN / 코 NOSE / 머리 HEAD / 목 NECK / 동순위 DH / - NA / 빈칸 FIRST |
| `PASS_ORD_S1` | 1번째 구간 통과 순위. NULL = 기록 없음 | INT | 22 (규칙 22: '-'와 공백뿐 = 통과 순위 기록 없음 (경주제외·출주취소마) → S1~S6 NULL) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 1번째 칸, 빈 칸 NULL |
| `PASS_ORD_S2` | 2번째 구간 통과 순위. NULL = 기록 없음 | INT | 3,640 (규칙 22: S1과 같은 행 (통과 순위 기록 없음); 원천 빈칸·해당 없음 3,618) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 2번째 칸, 빈 칸 NULL |
| `PASS_ORD_S3` | 3번째 구간 통과 순위. NULL = 기록 없음 | INT | 3,471 (규칙 22: S1과 같은 행 (통과 순위 기록 없음); 원천 빈칸·해당 없음 3,449) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 3번째 칸, 빈 칸 NULL |
| `PASS_ORD_S4` | 4번째 구간 통과 순위. NULL = 기록 없음 | INT | 22 (규칙 22: S1과 같은 행 (통과 순위 기록 없음)) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 4번째 칸, 빈 칸 NULL |
| `PASS_ORD_S5` | 5번째 구간 통과 순위. NULL = 기록 없음 | INT | 22 (규칙 22: S1과 같은 행 (통과 순위 기록 없음)) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 5번째 칸, 빈 칸 NULL |
| `PASS_ORD_S6` | 6번째 구간 통과 순위. NULL = 기록 없음 | INT | 22 (규칙 22: S1과 같은 행 (통과 순위 기록 없음)) | 1 ~ 10 | `PASS_ORD_RAW` → '-'로 나눈 6번째 칸, 빈 칸 NULL |

## RC_SALES

- 한 행 = 경주 1개 × 승식 1개의 매출 · **2,702행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `BET_TYPE_CD` | 승식 | CODE | 0 | `WIN` 386 단승식: 1착 1두<br>`PLC` 386 연승식: 1~3착 안 1두<br>`QNL` 386 복승식: 1·2착 2두 순서 무관<br>`QPL` 386 복연승식: 1~3착 안 2두 순서 무관<br>`EXA` 386 쌍승식: 1·2착 순서대로<br>`TRI` 386 삼복승식: 1~3착 순서 무관<br>`TLA` 386 삼쌍승식: 1~3착 순서대로 | `POOL_NM` → 단식/연식/복식/복연/쌍식/삼복/삼쌍 → 표준 승식 |
| `SALES_AMT` | 매출액(원) | BIGINT | 0 | 4327400 ~ 1066430100 | `SALES_AMT_RAW` → 쉼표 제거 |

## RC_SALES_TOTAL

- 한 행 = 경주 1개의 매출 합계 (원천 '합계' 행, 검증용) · **386행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `RC_DT` | 경주일 | DATE | 0 | 2026-05-22 ~ 2026-11-14 | `RC_DATE` → 형식 %Y%m%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 0 | 1 ~ 9 | `RC_NO` → 정수 변환 |
| `SALES_AMT` | 경주 전체 매출 합계(원) | BIGINT | 0 | 520775500 ~ 3015130800 | `SALES_AMT_RAW` → POOL_NM='합계' 행, 쉼표 제거 (검증용) |

## HR_VET_HIST

- 한 행 = 말 진료 1건 · **1,488행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `VET_SEQ` | 진료 기록 번호 (Bronze 행 번호, 브리지 연결 키) | INT | 0 | 1 ~ 1488 | `(새 키)` → Bronze 행 번호 (브리지 연결용) |
| `VET_DT` | 진료일 | DATE | 0 | 2026-05-16 ~ 2026-11-18 | `VET_DT_RAW` → 형식 %Y.%m.%d 순서로 시도 |
| `HR_NM` | 마명 (말 연결 키) | VARCHAR | 0 | 고유 569개. 예: `대방가`, `사라호`, `색달미소` | `HR_NAME` → TRIM, 빈칸 NULL |
| `TR_GRP_NO` | 진료 기록상의 소속 조 (스냅샷과 다를 수 있음) | VARCHAR(2) | 0 | 고유 18개. 예: `05`, `19`, `06` | `TR_GRP_NO` → 진료 기록 값 그대로 |
| `VET_PLACE_NM` | 진료 장소 | VARCHAR | 0 | `KRA 제주경마` 1,488 | `VET_PLACE_NM` → TRIM, 빈칸 NULL |
| `VET_NM` | 원본 진료명 (쉼표로 여러 개일 수 있음) | VARCHAR | 0 | 고유 78개. 예: `우전지파행`, `좌전지파행`, `기타 파행` | `VET_NM_RAW` → 원본 진료명 그대로 (TRIM) |
| `REPORT_DT` | 진료 보고일 | DATE | 0 | 2026-05-20 ~ 2026-11-18 | `REPORT_DT` → 형식 %Y%m%d 순서로 시도 |

## HR_VET_TYPE_BRIDGE

- 한 행 = 진료 1건 × 진료명 1개 (한 칸에 여러 개였던 진료명을 나눈 것) · **1,664행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `VET_SEQ` | 진료 기록 번호 (Bronze 행 번호, 브리지 연결 키) | INT | 0 | 1 ~ 1488 | `HR_VET_HIST.VET_SEQ` → 진료 기록 연결 키 |
| `VET_TYPE_NM` | 진료명 1개 | VARCHAR | 0 | 고유 54개. 예: `우전지파행`, `좌전지파행`, `기타 파행` | `VET_NM_RAW` → ',' 로 나눈 진료명 1개 |

## RC_CHANGE_EVENT

- 한 행 = 변경 공지 1건 · **149행**

| 컬럼 | 뜻 | 타입 | NULL | 값 | 원천 → 규칙 |
|:--|:--|:--|:--|:--|:--|
| `EVENT_TYPE_CD` | 공지 종류 | CODE | 0 | `JOCKEY_CHANGE` 75 기수변경<br>`TRACK_STATUS` 52 주로상태<br>`SCRATCH` 22 말취소 | `eventType` → 코드그룹 EVENT_TYPE 매핑 |
| `ANNOUNCE_DTM` | 공지 일시 | TIMESTAMP | 0 | 2026-05-22 23:58:00 ~ 2026-11-14 23:58:00 | `announcedAt` → 형식 %Y%m%d %H:%M 순서로 시도 |
| `RC_DT` | 경주일. NULL = 주로상태 공지 | DATE | 52 (원천 빈칸·해당 없음 52) | 2026-05-23 ~ 2026-11-14 | `race.rcDate` → 형식 %Y/%m/%d 순서로 시도 |
| `RC_NO` | 경주번호 (그날 몇 번째 경주) | INT | 52 (원천 빈칸·해당 없음 52) | 1 ~ 9 | `race.rcNo` → 정수 변환 |
| `CHUL_NO` | 마번 | INT | 52 (원천 빈칸·해당 없음 52) | 1 ~ 10 | `horse.chulNo` → 정수 변환 |
| `HR_NM` | 마명 (말 연결 키) | VARCHAR | 52 (원천 빈칸·해당 없음 52) | 고유 88개. 예: `원평가속도`, `백두무대`, `천명자` | `horse.hrName` → TRIM |
| `BEF_JK_NM` | 변경 전 기수 | VARCHAR | 74 (원천 빈칸·해당 없음 74) | `곽용남` 22<br>`전현준` 17<br>`김홍권` 11<br>`안득수` 5<br>`양민재` 5<br>`김다영` 3<br>`임재광` 3<br>`나유나` 2<br>`문현진` 2<br>`김경휴` 2<br>`한영민` 2<br>`김한남` 1 | `change.before` → 기수변경 전 |
| `AFT_JK_NM` | 변경 후 기수 | VARCHAR | 74 (원천 빈칸·해당 없음 74) | 고유 21개. 예: `임재광`, `김준호`, `이성민` | `change.after` → 기수변경 후 |
| `BUDAM_KG` | 변경 후 부담중량(kg) | DECIMAL(4,1) | 74 (원천 빈칸·해당 없음 74) | 51.0 ~ 60.0 | `change.budamRaw` → 소수 변환 |
| `CHG_REASON_NM` | 기수변경 사유 | VARCHAR | 74 (원천 빈칸·해당 없음 74) | 고유 14개. 예: `감기몸살`, `현기증`, `7R 이후 무릎 통증` | `change.reason` → 기수변경 사유 (이름 충돌 구분) |
| `SCRATCH_REASON_NM` | 말취소 사유 | VARCHAR | 127 (원천 빈칸·해당 없음 127) | `오른 앞다리 절음` 9<br>`왼 앞다리 절음` 8<br>`오른 뒷다리 절음` 2<br>`왼 뒷다리 절음` 2<br>`양 앞다리 절음` 1 | `reason` → 말취소 사유 (이름 충돌 구분) |
| `TRACK_STAT_CD` | 주로 상태 | CODE | 97 (원천 빈칸·해당 없음 97) | `DRY` 28 건조<br>`MOIST` 9 다습<br>`GOOD` 7 양호<br>`SLOPPY` 4 불량 (가장 젖음)<br>`SATURATED` 4 포화 | `trackRaw` → 코드그룹 TRACK_STAT 매핑 |
| `TRACK_MOIST_RT` | 함수율(%) | DECIMAL(5,1) | 97 (원천 빈칸·해당 없음 97) | 2.0 ~ 20.0 | `trackRaw` → 괄호 안 함수율(%) |
