# AS-IS: 원천 데이터 문제 정리

- 기준 원천: `data/00_origin/` 12개 파일 (제주 경마, 2026-05-22 ~ 2026-11-14, 경주 386개)
- 건수는 Bronze(원천 그대로)에서 직접 센 값입니다. 처리 방법은 `meta/mapping_rules.md` (팀 공용 매핑 규칙서)를 따릅니다.
- "Silver 처리"는 표준화 단계에서 한 일이고, "다음 단계"는 품질 관리(정제) 단계에서 처리할 문제입니다.

## 1. 이름이 제각각

| 문제 | 예 | 처리 |
|:--|:--|:--|
| 대소문자·표기 혼용 | `bet_order.order_no`(소문자 snake), `RC_RACE.RC_DATE`(대문자), JSON `rcDate`(camelCase) | Silver: 전부 UPPER_SNAKE |
| 같은 뜻, 다른 이름 | 회원 `member_no` / `MBR_NO`, 조교사 소속 조 `GRP_NO` / `TR_GRP_NO`, 말 성별 `SEX_NM` / `HR_SEX` | Silver: `MBR_NO`, `TR_GRP_NO`, `HR_SEX_CD`로 통일 |
| 같은 이름, 다른 뜻 | `ticket_cnt`: 전표의 마권 장수 / 마권의 구좌 수(금액÷100) | Silver: `TICKET_CNT` / `UNIT_CNT`로 분리 |
| 같은 이름, 다른 대상 | `BIRTH_RAW`·`AGE_RAW`: 말 스냅샷은 말, 조교사 스냅샷은 사람 | Silver: `HR_BIRTH_DT`/`TR_BIRTH_DT`, `HR_AGE`/`TR_AGE` |
| 사유 컬럼 두 개 | JSON `reason`(말취소) / `change.reason`(기수변경) | Silver: `SCRATCH_REASON_NM` / `CHG_REASON_NM` |

## 2. 날짜·시간 형식이 섞임

| 컬럼 | 섞인 형식 | 건수 |
|:--|:--|--:|
| `MBR_MASTER.BIRTH_DT` | `YYYYMMDD` / `YYYY-MM-DD` / `YYYY.MM.DD` / 빈칸 | 4,108 / 164 / 84 / 27 |
| `bet_order.sale_dtm` | `YYYY-MM-DD HH:MI:SS`(현장·앱) / `YYYYMMDDHHMISS`(장외 OTB) | 26,364 / 1,543 |
| 파일마다 다름 | `YYYYMMDD`(경주·스냅샷), `YYYY/MM/DD`(말·조교사 생일, JSON 경주일), `YYYY.MM.DD`(진료일), `YYYYMMDD HH:MI`(JSON 공지 시각), `HH:MI`(출발 시각) | — |

Silver: 형식을 순서대로 시도해서 DATE / TIMESTAMP / TIME으로 변환했습니다. 변환 실패는 0건입니다.

## 3. 코드값 불일치

| 컬럼 | 문제 | 건수 |
|:--|:--|--:|
| `bet_ticket.bet_type_cd` | 영문(WIN/PLC/QNL)과 한글(단승/연승/복승) 혼용 | 한글 28,823 |
| `RC_SALES.POOL_NM` | 같은 승식을 다른 한글로 씀 (단식·연식·복식 …) | 2,702 |
| `bet_ticket.ticket_status` | 대소문자 혼용 (sold / cancel / void) | 2,655 |
| `MBR_MASTER.REGION_NM` | 정식 명칭과 약칭 혼용 (서울특별시 / 서울) | 정식 명칭 339 |
| `bet_order.channel_cd` | 장외발매소가 OTB01~OTB37로 지점마다 다른 값, 빈칸 | OTB 1,543 / 빈칸 13 |
| `MBR_NO` | 소문자 회원번호 | 51 |
| 말 성별·등급, 날씨, 주로 상태 | 한글 값 (수/암/거, 제1~제6/미, 맑음/흐림, 건조/다습 …) | 전 행 |

Silver: 코드표(매핑 규칙서 6장)로 표준코드로 바꿨습니다. 코드표에 없는 값은 0건입니다. 원천값별 변환 건수는 `meta/silver_value_map.csv`에 있습니다.

## 4. 한 칸에 여러 값

| 컬럼 | 원천 예 | Silver 결과 |
|:--|:--|:--|
| `RC_RESULT.WG_HR_RAW` | `279+14` | 체중 279, 증감 +14 |
| `RC_RESULT.RC_TIME_RAW` | `1:13.2` | 73.2초 |
| `RC_RESULT.MARGIN_RAW` | `1½`, `코`, `머리`, 빈칸(1착) | 착차 길이 1.5 + 착차 코드 |
| `RC_RESULT.PASS_ORD_RAW` | `1-  -  - 1- 1- 1` | 통과 순위 6칸 |
| `RC_ODDS.SECTION_TIMES_RAW` | `0:48.8 0:16.7               0:24.4 …` | 구간 기록 7칸. 빈 구간이 공백이라 공백으로 나누면 칸이 밀려서 7글자 고정폭으로 자름 |
| `RC_RACE.WEATHER_TRACK_RAW` | `날씨: 흐림  주로: 다습  (14%)` | 날씨, 주로 상태, 함수율 |
| `RC_RACE.RANK_RAW` | `제5등급핸디캡` | 경주 등급 5 + 부담 방식 HANDICAP |
| `RC_RACE.PRIZE_RAW` | `순위상금: 700만원 322만원 …` | 1~5위 상금(원) |
| `RC_RACE.RC_COND_RAW` | `핸디캡  제주마제21회 KCTV배` | 마종 제주마 + 경주명 |
| `HR_WEEKLY_SNAPSHOT.INTRO_PRICE_RAW` | `3,000천원(개별)`, `자가생산` | 도입가(원) + 도입 유형 |
| `HR_VET_HIST.VET_NM_RAW` | `정치,낭치` (176행) | 브리지 테이블 1,664행 |
| `race_change_events.jsonl` | 중첩 JSON, 이벤트 종류마다 필드가 다름 | 표 1개로 펼침 |

## 5. 단위·표기

| 문제 | 예 | 처리 |
|:--|:--|:--|
| 금액 단위가 섞임 | 상금은 `만원`, 도입가는 `천원`, 매출은 쉼표 포함 문자열 | Silver: 전부 원 단위 정수 |
| 숫자 앞 0 | 조교사 조 `01`, `08` | Silver: 문자로 두고 앞 0 유지 |
| 거리 표기 | `0900M` | Silver: 900 (m) |
| '값 없음' 표시 | 배당률 `-----` 22건 | Silver: NULL (원천값은 이슈 로그에 기록) |

## 6. 의미가 다른 값이 같은 칸에

| 컬럼 | 문제 | 건수 | 처리 |
|:--|:--|--:|:--|
| `HR_WEEKLY_SNAPSHOT.TR_NAME` | 사람 이름 대신 `외부마` | 25,428 | Silver: `TR_NM` NULL + `TR_EXTERNAL_YN`=Y |
| `RC_RESULT.ORD_RAW` | 순위 칸에 `94`(경주제외)·`95`(출주취소) | 22 | Silver: 순위 NULL + `ENTRY_STAT_CD` |
| `RC_RESULT.WG_HR_RAW` / `RC_TIME_RAW` / `PASS_ORD_RAW` | 경주제외·출주취소마는 체중 `0`, 기록 `경주제외`, 통과순위 `-  -  -  -` | 22 | Silver: NULL (원천값은 이슈 로그에 기록) |
| `RC_SALES.POOL_NM` | 승식별 행 사이에 `합계` 행 | 386 | Silver: `RC_SALES_TOTAL`로 분리 |

## 7. 공백·빈칸

| 컬럼 | 문제 | 건수 |
|:--|:--|--:|
| `bet_ticket.hr_name` | 앞뒤 공백 | 5,164 |
| `bet_ticket.hr_name` | 빈칸 (마번은 있음) | 1,563 |
| `bet_order.member_no` | 앞뒤 공백 | 46 |
| `bet_order.member_no` | 빈칸 (비회원) | 4,921 |

## 8. 쓸모없는 컬럼

| 컬럼 | 이유 |
|:--|:--|
| `bet_ticket.unit_amt` | 전부 100 |
| `HR_WEEKLY_SNAPSHOT.PRD_NM`, `RC_ENTRY.HR_BREED` | 전부 '제' |
| `RC_ENTRY.ORD_RAW`, `RC_ODDS.ORD_RAW` | `RC_RESULT.ORD_RAW`와 같은 값 |
| `RC_RACE.TITLE_RAW`, `RC_DOW`, `DIVIDEND_RAW` | 다른 컬럼이나 테이블에 같은 내용이 있음 |

Silver에서 제외했고, 제외 사유는 `meta/data_dictionary.csv`에 남겼습니다. 원천값은 Bronze에 그대로 있습니다.

## 9. 다음 단계(품질 관리)에서 처리할 문제

표준화 단계에서는 행을 지우지 않기 때문에 아래 문제는 Silver에 그대로 남아 있습니다.

| 문제 | 건수 |
|:--|--:|
| `bet_ticket` 완전 중복 행 (같은 전표번호·마권 순번) | 1,052 |
| 전표 헤더(`bet_order`)의 장수·금액과 마권 상세(`bet_ticket`) 합계 불일치 (중복 제거 후 기준) | 93 |
