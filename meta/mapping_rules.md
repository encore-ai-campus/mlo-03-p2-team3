# 원천 → 표준 매핑 규칙서 (팀 공용)

> 기준 원천: 최신 `masahoe_betting_source_win.zip` (데이터셋 12개)
>
> 이 문서는 **각자 자기 파이프라인에서 적용할 규칙**이다. 원천(`source/`)은 고치지 않는다.
> 4명이 같은 규칙을 적용하면, 나중에 합칠 때 테이블·컬럼·코드가 그대로 맞는다.
> 적용 단계(Bronze 적재 직후 / Silver)는 팀에서 정한 대로 한다.

## 1. 공통 원칙

| 원칙         | 내용                                                    |
|:-----------|:------------------------------------------------------|
| 원천은 그대로    | 원천 파일은 수정·삭제하지 않는다. 표준화는 우리 테이블에 적재하면서 한다             |
| 행은 지우지 않는다 | 표준화 단계에서는 이름·타입·코드·형식만 바꾼다. 중복 제거·불일치 처리 같은 정제는 별도 단계 |
| 빈 값        | 빈 문자열, 공백만 있는 값, '-----' 같은 '값 없음' 표시는 전부 NULL        |
| 문자열        | 앞뒤 공백 제거(TRIM)                                        |
| 인코딩        | UTF-8 (CSV로 내보낼 때는 UTF-8-SIG)                         |
| 시간대        | 모든 일시는 KST                                            |
| 단위         | 금액은 원, 무게는 kg, 시간 길이는 초, 거리는 m                        |

## 2. 네이밍 규칙

- 테이블·컬럼 이름은 전부 **UPPER_SNAKE** (원천의 소문자 snake, camelCase는 바꾼다)

| 구분     | 원천에 보이는 후보                   | 표준    | 예                |
|:-------|:-----------------------------|:------|:-----------------|
| 회원     | USER / MEMBER / MBR / U      | MBR   | MBR_NO           |
| 식별 번호  | NO / NUM / ID                | _NO   | ORDER_NO, MBR_NO |
| 순번     | SEQ / NO                     | _SEQ  | TICKET_SEQ       |
| 일자     | DATE / DT                    | _DT   | RC_DT, BIRTH_DT  |
| 일시     | DATETIME / DTM / TIME / AT   | _DTM  | SALE_DTM         |
| 시각     | TIME / TM                    | _TM   | START_TM         |
| 이름     | NAME / NM                    | _NM   | HR_NM            |
| 코드     | CD / CODE / TYPE / STATUS    | _CD   | TICKET_STAT_CD   |
| 금액     | AMT / AMOUNT / PRICE / PRIZE | _AMT  | BET_AMT          |
| 건수     | CNT / COUNT / QTY            | _CNT  | TOT_1ST_CNT      |
| 무게     | WG / WGT / KG                | _KG   | BUDAM_KG         |
| 시간 길이  | TIME / SEC                   | _SEC  | RC_TIME_SEC      |
| 비율(%)  | RT / RATE / PCT              | _RT   | TRACK_MOIST_RT   |
| 배당률(배) | ODDS                         | _ODDS | WIN_ODDS         |
| 여부     | YN / FLAG / IS_              | _YN   | TR_EXTERNAL_YN   |
| 값      | VAL / SCORE                  | _VAL  | RATING_VAL       |
| 원문     | _RAW                         | 쓰지 않음 | 쪼갠 표준 컬럼으로 바꾼다   |

**주제어:** RC 경주, HR 말, JK 기수, TR 조교사, OW 마주, MBR 회원, ORDER 전표, TICKET 마권, CHNL 채널, VET 진료, BET 승식. `ORD`는 착순과 헷갈리므로 전표에 쓰지 않고, 착순은 `FINISH_ORD`로 쓴다.

## 3. 테이블 이름 매핑

| 원천                               | 표준 테이블                           | 비고                                       |
|:---------------------------------|:---------------------------------|:-----------------------------------------|
| bet/bet_order.csv                | BET_ORDER                        |                                          |
| bet/bet_ticket.csv               | BET_TICKET                       |                                          |
| mbr/MBR_MASTER.csv               | MBR_MASTER                       |                                          |
| hms/HR_WEEKLY_SNAPSHOT.csv       | HR_WEEKLY_SNAPSHOT               |                                          |
| hms/TR_WEEKLY_SNAPSHOT.csv       | TR_WEEKLY_SNAPSHOT               |                                          |
| rms/RC_RACE.csv                  | RC_RACE                          |                                          |
| rms/RC_ENTRY.csv                 | RC_ENTRY                         |                                          |
| rms/RC_ODDS.csv                  | RC_ODDS                          |                                          |
| rms/RC_RESULT.csv                | RC_RESULT                        |                                          |
| rms/RC_SALES.csv                 | RC_SALES + RC_SALES_TOTAL        | POOL_NM='합계' 행은 RC_SALES_TOTAL로 따로 (검증용) |
| vms/HR_VET_HIST.csv              | HR_VET_HIST + HR_VET_TYPE_BRIDGE | 진료명 한 칸 여러 개 → 브리지                       |
| mongodb/race_change_events.jsonl | RC_CHANGE_EVENT                  | JSON을 펼쳐서 표로                             |

## 4. 타입 규칙

| 구분       | 표준 타입                                | 대상                          | 규칙                                     |
|:---------|:-------------------------------------|:----------------------------|:---------------------------------------|
| 식별 번호    | VARCHAR                              | ORDER_NO, MBR_NO, TR_GRP_NO | 숫자처럼 보여도 문자. TR_GRP_NO는 앞 0 유지(01, 08) |
| 정수       | INT / BIGINT                         | 건수, 금액, 순위, 나이, 마번, 경주번호    | 금액은 BIGINT. 쉼표·단위 떼고 변환                |
| 소수       | DECIMAL                              | 배당률, 부담중량, 기록(초), 함수율       |                                        |
| 코드       | VARCHAR + 코드표                        | BET_TYPE_CD 등               | 5장 코드표에 있는 값만 허용                       |
| 숫자 모양 코드 | VARCHAR                              | MBR_STAT_CD(10/20/90)       | 숫자로 바꾸지 않는다                            |
| 날짜       | DATE (YYYY-MM-DD)                    | _DT                         |                                        |
| 일시       | TIMESTAMP (YYYY-MM-DD HH:MI:SS, KST) | _DTM                        |                                        |
| 시각       | TIME (HH:MI:SS)                      | _TM                         |                                        |

## 5. 날짜·시간 형식 규칙

| 원천 형식               | 나오는 곳                                                                                 | 표준                                           |
|:--------------------|:--------------------------------------------------------------------------------------|:---------------------------------------------|
| YYYYMMDD            | RC_DATE, rc_date, biz_date, SNAPSHOT_DT, JOIN_DT, REPORT_DT, MBR_MASTER.BIRTH_DT(대부분) | DATE                                         |
| YYYY-MM-DD          | MBR_MASTER.BIRTH_DT 일부                                                                | DATE                                         |
| YYYY.MM.DD          | MBR_MASTER.BIRTH_DT 일부, HR_VET_HIST.VET_DT_RAW                                        | DATE                                         |
| YYYY/MM/DD          | HR·TR 스냅샷 BIRTH_RAW, DEBUT_RAW, race_change_events.race.rcDate                        | DATE                                         |
| YYYY-MM-DD HH:MI:SS | bet_order.sale_dtm (현장·앱)                                                             | TIMESTAMP                                    |
| YYYYMMDDHHMISS      | bet_order.sale_dtm (장외 OTB)                                                           | TIMESTAMP                                    |
| YYYYMMDD HH:MI      | race_change_events.announcedAt                                                        | TIMESTAMP (초 = 00)                           |
| HH:MI               | RC_RACE.START_TM_RAW                                                                  | TIME (초 = 00) + START_DTM = RC_DT + START_TM |

- 한 컬럼에 형식이 섞인 곳(`sale_dtm` 2종, 회원 `BIRTH_DT` 3종)은 **모든 형식을 차례로 시도**하고, 어느 것에도 안 맞으면 NULL

## 6. 코드 매핑표 (원천값 → 표준코드)

| 코드그룹        | 원천값                                                                                                      | 표준코드                                       | 뜻                                   |
|:------------|:---------------------------------------------------------------------------------------------------------|:-------------------------------------------|:------------------------------------|
| BET_TYPE    | WIN, 단승, 단식                                                                                              | WIN                                        | 단승식: 1착 1두                          |
| BET_TYPE    | PLC, 연승, 연식                                                                                              | PLC                                        | 연승식: 1~3착 안 1두                      |
| BET_TYPE    | QNL, 복승, 복식                                                                                              | QNL                                        | 복승식: 1·2착 2두 순서 무관                  |
| BET_TYPE    | 복연                                                                                                       | QPL                                        | 복연승식: 1~3착 안 2두 순서 무관               |
| BET_TYPE    | 쌍식                                                                                                       | EXA                                        | 쌍승식: 1·2착 순서대로                      |
| BET_TYPE    | 삼복                                                                                                       | TRI                                        | 삼복승식: 1~3착 순서 무관                    |
| BET_TYPE    | 삼쌍                                                                                                       | TLA                                        | 삼쌍승식: 1~3착 순서대로                     |
| BET_TYPE    | 합계                                                                                                       | (코드 아님)                                    | RC_SALES_TOTAL로 분리                  |
| TICKET_STAT | SOLD, sold                                                                                               | SOLD                                       | 정상 발매                               |
| TICKET_STAT | CANCEL, cancel                                                                                           | CANCEL                                     | 발매 취소                               |
| TICKET_STAT | VOID, void                                                                                               | VOID                                       | 출전취소 무효                             |
| ORDER_TYPE  | SALE / CANCEL                                                                                            | 그대로                                        |                                     |
| CHNL        | ONSITE                                                                                                   | ONSITE                                     | 현장                                  |
| CHNL        | APP                                                                                                      | APP                                        | 온라인                                 |
| CHNL        | OTB01 ~ OTB37                                                                                            | OTB                                        | 장외발매소. 뒤 숫자는 OTB_BRANCH_NO로         |
| CHNL        | (빈칸)                                                                                                     | UNKNOWN                                    |                                     |
| MBR_STAT    | 10 / 20 / 90                                                                                             | 그대로                                        | 정상 / 휴면 / 탈퇴                        |
| MBR_GRADE   | VIP / GOLD / NORMAL                                                                                      | 그대로                                        |                                     |
| REGION      | 서울특별시 → 서울, 부산광역시 → 부산, 경기도 → 경기, 경상북도 → 경북, 경상남도 → 경남, 전라남도 → 전남, 제주특별자치도 → 제주 (대구·인천·광주·대전 광역시도 같은 방식) | 약칭                                         | 약칭은 그대로                             |
| HR_SEX      | 수 / 암 / 거                                                                                                | M / F / G                                  | 수말 / 암말 / 거세마                       |
| HR_GRADE    | 제1 ~ 제6 / 미                                                                                              | 1 ~ 6 / NONE                               | 말 등급                                |
| RC_GRADE    | RANK_RAW 앞부분 '제1등급' ~ '제6등급', '제OPEN'                                                                    | 1 ~ 6 / OPEN                               | 경주 등급                               |
| BUDAM_TYPE  | RANK_RAW 뒷부분 '핸디캡' / '별정A' / 없음                                                                          | HANDICAP / SPECIAL_A / NULL                | 부담 방식                               |
| ENTRY_STAT  | ORD_RAW 1~10 / 94 / 95                                                                                   | RAN / EXCLUDED / SCRATCHED                 | 94=경주제외, 95=출주취소 (FINISH_ORD는 NULL) |
| MARGIN      | 숫자·분수 / 코 / 머리 / 목 / 동순위 / - / 빈칸                                                                        | LEN / NOSE / HEAD / NECK / DH / NA / FIRST | 빈칸 = 1착                             |
| WEATHER     | 맑음 / 흐림 / 비 / 안개                                                                                         | CLEAR / CLOUDY / RAIN / FOG                |                                     |
| TRACK_STAT  | 건조 / 양호 / 다습 / 포화 / 불량                                                                                   | DRY / GOOD / MOIST / SATURATED / SLOPPY    | 수분 적음 → 많음                          |
| EVENT_TYPE  | JOCKEY_CHANGE / SCRATCH / TRACK_STATUS                                                                   | 그대로                                        | 기수변경 / 말취소 / 주로상태                   |
| MEET        | 제주                                                                                                       | JEJU                                       |                                     |

## 7. 쪼개기 규칙 (한 칸에 여러 값)

| 원천 컬럼                              | 원천 예                                                         | 표준 결과                                                                       | 규칙                                                         |
|:-----------------------------------|:-------------------------------------------------------------|:----------------------------------------------------------------------------|:-----------------------------------------------------------|
| RC_RESULT.WG_HR_RAW                | '279+14'                                                     | HR_WGT_KG=279, HR_WGT_DIFF_KG=+14                                           | 증감 없는 첫 측정('279')은 DIFF NULL. 출주취소마의 '0'은 둘 다 NULL         |
| RC_RESULT.RC_TIME_RAW              | '1:13.2'                                                     | RC_TIME_SEC=73.2                                                            | '경주제외', '출주취소' 글자는 NULL                                    |
| RC_RESULT.ORD_RAW                  | '1' ~ '10', '94', '95'                                       | FINISH_ORD + ENTRY_STAT_CD                                                  | 94·95는 순위 아님                                               |
| RC_RESULT.MARGIN_RAW               | '1½', '¾', '코'                                               | MARGIN_LEN=1.5 / 0.75 / NULL, MARGIN_CD                                     | ½=0.5, ¼=0.25, ¾=0.75                                      |
| RC_RESULT.PASS_ORD_RAW             | '1-  -  - 1- 1- 1'                                           | PASS_ORD_S1 ~ S6                                                            | '-'로 나눈 위치 기준, 빈 칸은 NULL                                   |
| RC_ODDS.SECTION_TIMES_RAW          | '0:48.8 0:16.7      0:24.4 …'                                | SECT1_SEC ~ SECT7_SEC                                                       | **공백으로 나누지 말고 7글자 고정폭 위치로 자를 것** (빈 구간이 있어서 공백 분리하면 칸이 밀림) |
| RC_RACE.WEATHER_TRACK_RAW          | '날씨: 흐림  주로: 다습  (14%)'                                      | WEATHER_CD, TRACK_STAT_CD, TRACK_MOIST_RT=14.0                              | 주로 '불량'은 함수율 표기가 없음 → NULL                                 |
| RC_RACE.RANK_RAW                   | '제5등급핸디캡'                                                    | RC_GRADE_CD=5, BUDAM_TYPE_CD=HANDICAP                                       |                                                            |
| RC_RACE.PRIZE_RAW                  | '순위상금: 700만원 322만원 …'                                        | PRIZE1_AMT ~ PRIZE5_AMT                                                     | 만원 → 원 (×10,000), 쉼표 제거                                    |
| RC_RACE.RC_COND_RAW                | '제주마일반', '핸디캡  제주마제21회 KCTV배'                                | HR_CLASS_NM='제주마', RC_TITLE_NM                                              | 앞의 '핸디캡' 제거, '일반'이면 RC_TITLE_NM NULL                       |
| RC_RACE.RC_DAY_RAW / RC_DIST_RAW   | '제 40일', '1000M'                                             | RC_DAY_SEQ=40, RC_DIST_M=1000                                               | 숫자만                                                        |
| RC_RACE.START_TM_RAW               | '10:45'                                                      | START_TM='10:45:00', START_DTM='2026-05-22 10:45:00'                        |                                                            |
| HR_WEEKLY_SNAPSHOT.INTRO_PRICE_RAW | '3,000천원(개별)', '자가생산'                                        | INTRO_AMT=3000000, INTRO_TYPE_NM=개별                                         | 천원 → 원. '자가생산'은 금액 NULL, 유형=자가생산                           |
| HR_WEEKLY_SNAPSHOT.TR_NAME         | '외부마'                                                        | TR_NM=NULL, TR_EXTERNAL_YN=Y                                                | 사람 이름이 아님. TR_GRP_NO=88과 같이 나옴                             |
| RC_SALES.SALES_AMT_RAW             | '12,548,000'                                                 | SALES_AMT=12548000                                                          | 쉼표 제거                                                      |
| bet_order.channel_cd               | 'OTB13'                                                      | CHNL_CD=OTB, OTB_BRANCH_NO=13                                               |                                                            |
| HR_VET_HIST.VET_NM_RAW             | '정치,낭치'                                                      | HR_VET_TYPE_BRIDGE: (VET_SEQ, 정치), (VET_SEQ, 낭치)                            | 원본 진료명은 VET_NM에 그대로 두고, VET_SEQ(행 번호)로 연결                  |
| race_change_events (JSON)          | {race: {rcDate, rcNo}, horse: {chulNo, hrName}, change: {…}} | RC_DT, RC_NO, CHUL_NO, HR_NM, BEF_JK_NM, AFT_JK_NM, BUDAM_KG, CHG_REASON_NM | TRACK_STATUS 이벤트는 경주·말 칸이 NULL                             |

## 8. 이름 충돌 주의

| 원천                      | 문제                                                 | 표준                                         |
|:------------------------|:---------------------------------------------------|:-------------------------------------------|
| ticket_cnt              | bet_order = 전표 안 마권 장수 / bet_ticket = 구좌 수(금액÷100) | BET_ORDER.TICKET_CNT / BET_TICKET.UNIT_CNT |
| BIRTH_RAW               | 말 생일 / 조교사 생일                                      | HR_BIRTH_DT / TR_BIRTH_DT                  |
| AGE_RAW                 | 말 나이 / 조교사 나이                                      | HR_AGE / TR_AGE                            |
| GRP_NO vs TR_GRP_NO     | 둘 다 조교사 소속 조                                       | TR_GRP_NO 하나로                              |
| SEX_NM vs HR_SEX        | 둘 다 말 성별                                           | HR_SEX_CD 하나로                              |
| reason vs change.reason | 말취소 사유 / 기수변경 사유                                   | SCRATCH_REASON_NM / CHG_REASON_NM          |
| ORD_RAW                 | RC_ENTRY·RC_ODDS·RC_RESULT 세 곳에 같은 값               | RC_RESULT의 FINISH_ORD만 쓴다                  |

## 9. 쓰지 않는 컬럼

| 원천 컬럼                             | 이유                |
|:----------------------------------|:------------------|
| bet_ticket.unit_amt               | 전부 100 (상수)       |
| HR_WEEKLY_SNAPSHOT.PRD_NM         | 전부 '제'            |
| RC_ENTRY.HR_BREED                 | 전부 '제'            |
| RC_ENTRY.ORD_RAW, RC_ODDS.ORD_RAW | RC_RESULT와 중복     |
| RC_RACE.TITLE_RAW                 | RC_DT·RC_NO와 중복   |
| RC_RACE.RC_DOW                    | 날짜에서 계산(DIM_DATE) |
| RC_RACE.DIVIDEND_RAW              | RC_ODDS와 내용 중복    |

## 10. 테이블별 컬럼 매핑

### BET_ORDER

| 원천 컬럼         | 표준 컬럼                  | 표준 타입            | 규칙                       |
|:--------------|:-----------------------|:-----------------|:-------------------------|
| order_no      | ORDER_NO               | VARCHAR(10)      |                          |
| order_type_cd | ORDER_TYPE_CD          | CODE             |                          |
| orig_order_no | ORIG_ORDER_NO          | VARCHAR(10)      | 빈칸 NULL                  |
| member_no     | MBR_NO                 | VARCHAR(8)       | TRIM + 대문자, 빈칸 NULL(비회원) |
| channel_cd    | CHNL_CD, OTB_BRANCH_NO | CODE, VARCHAR(2) | 6장 CHNL                  |
| sale_dtm      | SALE_DTM               | TIMESTAMP        | 형식 2종                    |
| biz_date      | BIZ_DT                 | DATE             |                          |
| ticket_cnt    | TICKET_CNT             | INT              | 마권 장수                    |
| total_amt     | TOTAL_AMT              | BIGINT           | 취소는 음수                   |

### BET_TICKET

| 원천 컬럼         | 표준 컬럼          | 표준 타입       | 규칙             |
|:--------------|:---------------|:------------|:---------------|
| order_no      | ORDER_NO       | VARCHAR(10) |                |
| ticket_seq    | TICKET_SEQ     | INT         |                |
| rc_date       | RC_DT          | DATE        |                |
| rc_no         | RC_NO          | INT         |                |
| bet_type_cd   | BET_TYPE_CD    | CODE        | 한글 단승/연승/복승 포함 |
| chul_no       | CHUL_NO        | INT         |                |
| hr_name       | HR_NM          | VARCHAR     | TRIM, 빈칸 NULL  |
| chul_no2      | CHUL_NO2       | INT         | 복승만            |
| hr_name2      | HR_NM2         | VARCHAR     |                |
| ticket_cnt    | UNIT_CNT       | INT         | ⚠ 구좌 수         |
| unit_amt      | (제외)           |             |                |
| bet_amt       | BET_AMT        | INT         | 취소는 음수         |
| ticket_status | TICKET_STAT_CD | CODE        | 대문자            |

### MBR_MASTER

| 원천 컬럼        | 표준 컬럼        | 표준 타입      | 규칙    |
|:-------------|:-------------|:-----------|:------|
| MBR_NO       | MBR_NO       | VARCHAR(8) |       |
| BIRTH_DT     | BIRTH_DT     | DATE       | 형식 3종 |
| JOIN_DT      | JOIN_DT      | DATE       |       |
| REGION_NM    | REGION_CD    | CODE       | 약칭    |
| MBR_GRADE_CD | MBR_GRADE_CD | CODE       |       |
| MBR_STAT_CD  | MBR_STAT_CD  | CODE       | 문자 유지 |

### HR_WEEKLY_SNAPSHOT

| 원천 컬럼                                    | 표준 컬럼                                                | 표준 타입            | 규칙         |
|:-----------------------------------------|:-----------------------------------------------------|:-----------------|:-----------|
| SNAPSHOT_DT                              | SNAPSHOT_DT                                          | DATE             |            |
| HR_NAME                                  | HR_NM                                                | VARCHAR          |            |
| PRD_NM                                   | (제외)                                                 |                  |            |
| SEX_NM                                   | HR_SEX_CD                                            | CODE             |            |
| BIRTH_RAW                                | HR_BIRTH_DT                                          | DATE             | YYYY/MM/DD |
| AGE_RAW                                  | HR_AGE                                               | INT              |            |
| GRADE_RAW                                | HR_GRADE_CD                                          | CODE             |            |
| TR_GRP_NO                                | TR_GRP_NO                                            | VARCHAR(2)       | 앞 0 유지     |
| TR_NAME                                  | TR_NM, TR_EXTERNAL_YN                                | VARCHAR, CHAR(1) | '외부마' 처리   |
| OW_NAME                                  | OW_NM                                                | VARCHAR          |            |
| TOT_RC_CNT / TOT_1ST / TOT_2ND / TOT_3RD | TOT_RC_CNT / TOT_1ST_CNT / TOT_2ND_CNT / TOT_3RD_CNT | INT              |            |
| Y1_RC_CNT / Y1_1ST / Y1_2ND / Y1_3RD     | Y1_RC_CNT / Y1_1ST_CNT / Y1_2ND_CNT / Y1_3RD_CNT     | INT              |            |
| PRIZE_AMT_RAW                            | PRIZE_AMT                                            | BIGINT           |            |
| RATING_RAW                               | RATING_VAL                                           | INT              | 빈칸 NULL    |
| INTRO_PRICE_RAW                          | INTRO_AMT, INTRO_TYPE_NM                             | BIGINT, VARCHAR  | 천원→원       |
| SIRE_NAME                                | SIRE_NM                                              | VARCHAR          |            |
| DAM_NAME                                 | DAM_NM                                               | VARCHAR          |            |

### TR_WEEKLY_SNAPSHOT

| 원천 컬럼        | 표준 컬럼         | 표준 타입      | 규칙      |
|:-------------|:--------------|:-----------|:--------|
| SNAPSHOT_DT  | SNAPSHOT_DT   | DATE       |         |
| TR_NAME      | TR_NM         | VARCHAR    |         |
| GRP_NO       | TR_GRP_NO     | VARCHAR(2) | ⚠ 이름 통일 |
| BIRTH_RAW    | TR_BIRTH_DT   | DATE       |         |
| AGE_RAW      | TR_AGE        | INT        |         |
| DEBUT_RAW    | DEBUT_DT      | DATE       |         |
| TOT_* / Y1_* | HR 스냅샷과 같은 규칙 | INT        |         |

### RC_RACE

| 원천 컬럼             | 표준 컬럼                                     | 표준 타입            | 규칙   |
|:------------------|:------------------------------------------|:-----------------|:-----|
| RC_DATE           | RC_DT                                     | DATE             |      |
| RC_NO             | RC_NO                                     | INT              |      |
| TITLE_RAW         | (제외)                                      |                  |      |
| RC_DOW            | (제외)                                      |                  |      |
| MEET_NM           | MEET_CD                                   | CODE             | JEJU |
| RC_DAY_RAW        | RC_DAY_SEQ                                | INT              |      |
| RC_DIST_RAW       | RC_DIST_M                                 | INT              |      |
| RANK_RAW          | RC_GRADE_CD, BUDAM_TYPE_CD                | CODE ×2          |      |
| RC_COND_RAW       | HR_CLASS_NM, RC_TITLE_NM                  | VARCHAR ×2       |      |
| WEATHER_TRACK_RAW | WEATHER_CD, TRACK_STAT_CD, TRACK_MOIST_RT | CODE ×2, DECIMAL |      |
| PRIZE_RAW         | PRIZE1_AMT ~ PRIZE5_AMT                   | BIGINT ×5        |      |
| DIVIDEND_RAW      | (제외)                                      |                  |      |
| START_TM_RAW      | START_TM, START_DTM                       | TIME, TIMESTAMP  |      |

### RC_ENTRY

| 원천 컬럼        | 표준 컬럼      | 표준 타입        | 규칙           |
|:-------------|:-----------|:-------------|:-------------|
| RC_DATE      | RC_DT      | DATE         |              |
| RC_NO        | RC_NO      | INT          |              |
| ORD_RAW      | (제외)       |              | RC_RESULT 사용 |
| CHUL_NO      | CHUL_NO    | INT          |              |
| HR_NAME      | HR_NM      | VARCHAR      |              |
| HR_BREED     | (제외)       |              |              |
| HR_SEX       | HR_SEX_CD  | CODE         |              |
| HR_AGE       | HR_AGE     | INT          |              |
| WG_BUDAM_RAW | BUDAM_KG   | DECIMAL(4,1) |              |
| JK_NAME      | JK_NM      | VARCHAR      |              |
| TR_NAME      | TR_NM      | VARCHAR      |              |
| OW_NAME      | OW_NM      | VARCHAR      |              |
| RATING_RAW   | RATING_VAL | INT          | 빈칸 NULL      |

### RC_ODDS

| 원천 컬럼             | 표준 컬럼                 | 표준 타입        | 규칙           |
|:------------------|:----------------------|:-------------|:-------------|
| RC_DATE           | RC_DT                 | DATE         |              |
| RC_NO             | RC_NO                 | INT          |              |
| ORD_RAW           | (제외)                  |              |              |
| CHUL_NO           | CHUL_NO               | INT          |              |
| SECTION_TIMES_RAW | SECT1_SEC ~ SECT7_SEC | DECIMAL      | 7글자 고정폭      |
| WIN_ODDS_RAW      | WIN_ODDS              | DECIMAL(6,1) | '-----' NULL |
| PLACE_ODDS_RAW    | PLC_ODDS              | DECIMAL(6,1) | '-----' NULL |

### RC_RESULT

| 원천 컬럼        | 표준 컬럼                     | 표준 타입         | 규칙   |
|:-------------|:--------------------------|:--------------|:-----|
| RC_DATE      | RC_DT                     | DATE          |      |
| RC_NO        | RC_NO                     | INT           |      |
| ORD_RAW      | FINISH_ORD, ENTRY_STAT_CD | INT, CODE     |      |
| CHUL_NO      | CHUL_NO                   | INT           |      |
| HR_NAME      | HR_NM                     | VARCHAR       |      |
| WG_HR_RAW    | HR_WGT_KG, HR_WGT_DIFF_KG | INT ×2        |      |
| RC_TIME_RAW  | RC_TIME_SEC               | DECIMAL(5,1)  |      |
| MARGIN_RAW   | MARGIN_LEN, MARGIN_CD     | DECIMAL, CODE |      |
| PASS_ORD_RAW | PASS_ORD_S1 ~ S6          | INT           |      |

### RC_SALES

| 원천 컬럼         | 표준 컬럼       | 표준 타입   | 규칙        |
|:--------------|:------------|:--------|:----------|
| RC_DATE       | RC_DT       | DATE    |           |
| RC_NO         | RC_NO       | INT     |           |
| POOL_NM       | BET_TYPE_CD | CODE    | '합계' 행 분리 |
| SALES_AMT_RAW | SALES_AMT   | BIGINT  | 쉼표 제거     |

### HR_VET_HIST

| 원천 컬럼        | 표준 컬럼                                     | 표준 타입      | 규칙             |
|:-------------|:------------------------------------------|:-----------|:---------------|
| (새 키)        | VET_SEQ                                   | INT        | 행 번호 (브리지 연결용) |
| VET_DT_RAW   | VET_DT                                    | DATE       | YYYY.MM.DD     |
| HR_NAME      | HR_NM                                     | VARCHAR    |                |
| TR_GRP_NO    | TR_GRP_NO                                 | VARCHAR(2) | 진료 기록 값 그대로    |
| VET_PLACE_NM | VET_PLACE_NM                              | VARCHAR    |                |
| VET_NM_RAW   | VET_NM (+ HR_VET_TYPE_BRIDGE.VET_TYPE_NM) | VARCHAR    |                |
| REPORT_DT    | REPORT_DT                                 | DATE       |                |

### RC_CHANGE_EVENT

| 원천 컬럼                        | 표준 컬럼                         | 표준 타입         | 규칙         |
|:-----------------------------|:------------------------------|:--------------|:-----------|
| eventType                    | EVENT_TYPE_CD                 | CODE          |            |
| announcedAt                  | ANNOUNCE_DTM                  | TIMESTAMP     |            |
| race.rcDate                  | RC_DT                         | DATE          | YYYY/MM/DD |
| race.rcNo                    | RC_NO                         | INT           |            |
| horse.chulNo                 | CHUL_NO                       | INT           |            |
| horse.hrName                 | HR_NM                         | VARCHAR       |            |
| change.before / change.after | BEF_JK_NM / AFT_JK_NM         | VARCHAR       |            |
| change.budamRaw              | BUDAM_KG                      | DECIMAL       |            |
| change.reason                | CHG_REASON_NM                 | VARCHAR       |            |
| reason                       | SCRATCH_REASON_NM             | VARCHAR       |            |
| trackRaw                     | TRACK_STAT_CD, TRACK_MOIST_RT | CODE, DECIMAL |            |

## 11. 적용 후 맞는지 확인하는 기준

규칙대로 적용하면 아래 숫자가 나와야 해. 4명이 같은 숫자가 나오면 규칙을 똑같이 적용한 거야.

| 표준 테이블             |     행 수 |
|:-------------------|--------:|
| BET_ORDER          |  27,907 |
| BET_TICKET         | 523,416 |
| MBR_MASTER         |   4,383 |
| HR_WEEKLY_SNAPSHOT |  52,642 |
| TR_WEEKLY_SNAPSHOT |     954 |
| RC_RACE            |     386 |
| RC_ENTRY           |   3,666 |
| RC_ODDS            |   3,666 |
| RC_RESULT          |   3,666 |
| RC_SALES           |   2,702 |
| RC_SALES_TOTAL     |     386 |
| HR_VET_HIST        |   1,488 |
| HR_VET_TYPE_BRIDGE |   1,664 |
| RC_CHANGE_EVENT    |     149 |

| 확인 항목                                 | 기대값                     |
|:--------------------------------------|:------------------------|
| 코드표에 없는 코드 값                          | 0건 (전 코드 컬럼)            |
| 날짜·일시 변환 실패                           | 0건                      |
| MBR_MASTER.BIRTH_DT NULL              | 27 (원천이 빈 칸)            |
| RC_ODDS.WIN_ODDS NULL                 | 22 ('-----')            |
| RC_RACE.TRACK_MOIST_RT NULL           | 21 (주로 '불량'은 함수율 표기 없음) |
| RC_RESULT.FINISH_ORD NULL             | 22 (경주제외·출주취소)          |
| HR_WEEKLY_SNAPSHOT.TR_EXTERNAL_YN = Y | 25,428                  |
| HR_VET_HIST 중 진료명 여러 개                | 176 → 브리지 1,664행        |
| RC_SALES_TOTAL                        | 386 (경주마다 1행)           |

> 표준화 단계는 행을 지우지 않으므로, BET_TICKET의 완전 중복 1,052행·헤더 불일치 93건 같은 더러움은 그대로 남는다. 그건 다음 정제 단계에서 처리 (`meta/dq_log.csv` 참고).

## 12. 현재 브랜치의 Silver 적용 세부 규칙

아래 항목은 팀 파이프라인 합의안에 따라 적용한다.

| 원천·대상 | 처리 |
|---|---|
| `RC_RESULT.PASS_ORD_RAW` | 하이픈과 공백만 있는 값은 `PASS_ORD_S1`~`PASS_ORD_S6`을 모두 NULL로 두고 원천값을 이슈 로그에 기록 |
| `RC_RESULT.WG_HR_RAW` | `0`이면 `HR_WGT_KG`와 `HR_WGT_DIFF_KG` 모두 NULL. 현재 원천에서는 경주제외 18행과 출주취소 4행이 해당 |
| `SECT1_SEC`~`SECT7_SEC`, `TRACK_MOIST_RT`, `MARGIN_LEN` | 구간 기록과 함수율은 `DECIMAL(5,1)`, 착차는 `DECIMAL(5,2)` |
| DECIMAL 변환 | 지정한 정밀도 범위를 벗어나거나 반올림해야 저장할 수 있는 값은 `PARSE_FAIL`로 기록 |
| `VET_SEQ` | Bronze의 `_SRC_ROW_NO`를 사용. 헤더를 제외한 첫 데이터 행의 번호는 1 |
| `RC_ODDS.SECTION_TIMES_RAW` | 양끝 공백을 제거하기 전에 원문을 7글자씩 잘라 위치를 유지 |

빈 착차는 `FIRST`, 빈 발매 채널은 `UNKNOWN`으로 표준화한다.

## 13. Gold 이름 규칙 (D-017)

1~12장은 Silver 기준이다. Gold는 처음에 데이터 사전에 없고 이름을 검사하지 않아, 팩트마다 이름 체계가 달라졌다. 지금은 Gold·AI Ready 컬럼도 종합 데이터 사전(`data_dictionary.csv`, `LAYER = GOLD / AI_READY`)에 있다. 이 장은 Gold에서 **새로 만드는 컬럼**과 **Silver에서 가져오는 컬럼**의 이름 규칙을 정하고, `src/common/04_gold_naming_check.py`가 모든 Gold 테이블에 대해 검사한다.

### 13.1 규칙

| 항목 | 규칙 | 예 |
|:--|:--|:--|
| Silver에서 가져온 컬럼 | **이름을 바꾸지 않는다** | `HR_SEX_CD`, `ORIG_ORDER_NO`, `Y1_RC_CNT`는 Gold에서도 같은 이름 |
| 새로 만든 컬럼 | 2장의 주제어(`HR_`, `MBR_`, `RC_`, `TR_`, `CHNL_`)와 접미사(`_AMT`, `_CNT`, `_DT`, `_DTM`, `_SEC`, `_RT`, `_YN`, `_CD`, `_NM`)를 따른다 | `PURCHASE_AMT`, `CANCEL_ORDER_CNT`, `FIRST_CANCEL_DTM` |
| 테이블 | 팩트 `FCT_`, 차원 `DIM_`, 브리지 `BRIDGE_` | `FCT_RACE_ENTRY`, `DIM_HORSE` |
| 대리키 | `차원이름_KEY`, 정수, 미상은 `0`. 주제어로 줄이지 않는다 | `HORSE_KEY`, `MEMBER_KEY`, `TRAINER_KEY` |
| 날짜 키 | 경주일은 `DATE_KEY`, 그 외 역할은 `역할_DT_KEY` | `SALE_DT_KEY`, `VET_DT_KEY`, `PURCHASE_DT_KEY` |
| 여부 | `_YN`, 값은 `Y`/`N`. 판단할 수 없으면 NULL | `ANALYSIS_ELIGIBLE_YN`, `HEADER_MISMATCH_YN` |
| 비율·확률 | `_RT` | `EXPECT_WIN_RT`, `Y1_WIN_RT` |
| 시간대·순번처럼 접미사가 없는 정수 | `_NO` | `SALE_HOUR_NO` |
| 추적 컬럼 | `_`로 시작(원천 행 번호) 또는 `_ID`(행 식별자) | `_SRC_ROW_NO`, `ENTRY_ROW_ID` |
| 같은 개념 | 팩트·차원이 달라도 이름 하나만 쓴다 | 나이대는 `AGE_GROUP_NM` |

### 13.2 결정한 것

| 항목 | 결정 | 고려한 다른 안 |
|:--|:--|:--|
| 역할 날짜 키 | `_DT_KEY` (진료가 이미 사용, 바뀌는 곳이 적음) | `_DATE_KEY` |
| 경주일 키 | `DATE_KEY` 유지 (출전·매출이 이미 사용) | 모든 팩트를 `RC_DT_KEY`로 |
| 취소 라벨 `HAS_VERIFIED_CUSTOMER_CANCEL` | `VERIFIED_CANCEL_YN` (Y/N/NULL) | 학습 라벨이라 0/1 정수 유지, 이름만 `VERIFIED_CANCEL_FLAG` |

### 13.3 바꾼 이름 (2026-11-23, 43개)

값은 그대로 두고 이름만 바꿨다. 여부 3개(`VERIFIED_CANCEL_YN`, `HEADER_MISMATCH_YN`, `ANALYSIS_ELIGIBLE_YN`)만 값 형식이 1/0에서 Y/N으로 바뀌었다. 바꾸기 전·후 Gold 15개·AI Ready 3개 파일을 비교해 행 수와 모든 값이 같음을 확인했다.

**원주: 공통 차원·출전 (4)**

| 테이블 | 전 | 후 | 비고 |
|:--|:--|:--|:--|
| `DIM_MEMBER` | `MEMBER_TYPE_CD` | `MBR_TYPE_CD` | 매출·취소 코드도 읽음 |
| `DIM_HORSE` | `AGE_BAND_NM` | `AGE_GROUP_NM` | 진료 `DIM_AGE_GROUP`과 같은 개념 |
| `FCT_RACE_ENTRY` | `EXPECT_WIN` | `EXPECT_WIN_RT` | AI Ready 생성 코드도 읽음 |
| `DIM_DATE` | `RACE_DAY_YN` | `RC_DAY_YN` | 주제어 `RC_` |

**희정: 매출 (2)**

| 테이블 | 전 | 후 |
|:--|:--|:--|
| `FCT_RACE_SALES` | `SALE_DATE_KEY` | `SALE_DT_KEY` |
| `FCT_RACE_SALES` | `SALE_HOUR` | `SALE_HOUR_NO` |

**은빈: 50대 단승 취소 `FCT_BET_SELECTION_CANCEL_50S` (37)**

| 전 | 후 | 전 | 후 |
|:--|:--|:--|:--|
| `ORIGINAL_ORDER_NO` | `ORIG_ORDER_NO` | `RECENT1Y_WIN_RATE_BAND` | `Y1_WIN_RT_BAND_CD` |
| `PURCHASE_DATE_KEY` | `PURCHASE_DT_KEY` | `CAREER_STARTS` | `TOT_RC_CNT` |
| `CANCEL_DATE_KEY` | `CANCEL_DT_KEY` | `CAREER_WINS` | `TOT_1ST_CNT` |
| `RACE_DATE_KEY` | `DATE_KEY` | `CAREER_WIN_RATE` | `TOT_WIN_RT` |
| `SNAPSHOT_DATE_KEY` | `SNAPSHOT_DT_KEY` | `HAS_VERIFIED_CUSTOMER_CANCEL` | `VERIFIED_CANCEL_YN` (13.2) |
| `AGE_AT_PURCHASE` | `MBR_AGE` | `CANCEL_LABEL_STATUS` | `CANCEL_LABEL_STAT_CD` |
| `PURCHASE_AT` | `PURCHASE_DTM` | `CANCEL_TRANSACTION_COUNT` | `CANCEL_ORDER_CNT` |
| `HORSE_AGE_AT_RACE` | `HR_AGE` | `RAW_LINKED_CANCEL_AMOUNT_KRW` | `RAW_CANCEL_AMT` |
| `HORSE_SEX_AT_RACE` | `HR_SEX_CD` | `VERIFIED_CANCEL_AMOUNT_KRW` | `VERIFIED_CANCEL_AMT` |
| `PURCHASE_DETAIL_COUNT` | `PURCHASE_DETAIL_CNT` | `VERIFIED_CANCEL_STAKE_UNITS` | `VERIFIED_CANCEL_UNIT_CNT` |
| `PURCHASE_STAKE_UNITS` | `PURCHASE_UNIT_CNT` | `FIRST_CANCEL_AT` | `FIRST_CANCEL_DTM` |
| `PURCHASE_AMOUNT_KRW` | `PURCHASE_AMT` | `CANCEL_DELAY_SECONDS` | `CANCEL_DELAY_SEC` |
| `HORSE_SNAPSHOT_DATE` | `SNAPSHOT_DT` | `LATE_CANCEL_DETAIL_COUNT` | `LATE_CANCEL_DETAIL_CNT` |
| `SNAPSHOT_AGE_DAYS` | `SNAPSHOT_AGE_DAY_CNT` | `UNRESOLVED_CANCEL_ORDER_COUNT` | `UNRESOLVED_CANCEL_ORDER_CNT` |
| `RECENT1Y_STARTS` | `Y1_RC_CNT` | `HEADER_DETAIL_MISMATCH` (1/0) | `HEADER_MISMATCH_YN` (Y/N) |
| `RECENT1Y_WINS` | `Y1_1ST_CNT` | `OBSERVATION_END_AT` | `OBSERVATION_END_DTM` |
| `RECENT1Y_WIN_RATE` | `Y1_WIN_RT` | `ANALYSIS_ELIGIBLE` (1/0) | `ANALYSIS_ELIGIBLE_YN` (Y/N) |
| `EXCLUSION_REASONS` | `EXCLUDE_REASON_CD` | `DQ_DATASET_VERSION` | `CLEAN_VERSION_CD` |
| `RULE_VERSION` | `RULE_VERSION_CD` | | |

세은(진료)은 바꿀 것 없음. 대리키(`*_KEY`)와 `FACT_ID`, `CHUL_NO`, `BET_TYPE_CD`, `*_ROW_ID`는 규칙에 맞아 그대로 둔다.

### 13.4 검증

- `src/common/04_gold_naming_check.py`: 모든 Gold 테이블·컬럼이 13.1을 지키는지, `_YN` 값이 Y/N/NULL인지 확인한다. 바꾸기 전 Gold에서는 42건이 걸렸다(`AGE_BAND_NM`은 "같은 개념 두 이름"이라 패턴으로는 잡히지 않아 직접 확인).
- 같은 검사가 종합 데이터 사전의 GOLD·AI_READY 행과 실제 파일의 컬럼 이름·순서·타입을 대조한다.
- 새 Gold 컬럼을 만들면 사전에 행을 추가하고 이 검사가 통과해야 한다.
