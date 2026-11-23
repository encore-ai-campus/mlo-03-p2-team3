# Silver 단계 기록 (표준화)

- **코드:** `src/02_normalize.py` (표준화), `src/02_normalize_check.py` (검증)
- **입력:** `data/01_bronze/*.parquet` (읽기만 함)
- **출력:** `data/02_silver/*.parquet` 14개 테이블 + `meta/`의 기록 파일 4개
- **규칙 근거:** `meta/mapping_rules.md` (팀 공용 매핑 규칙서)
- **컬럼별 뜻·값·NULL 이유:** `docs/SILVER_COLUMNS.md`

## 원칙

1. **이름·타입·코드·형식만 바꾸고 행은 지우지 않습니다.**
   - 중복 제거, 불일치 정리는 다음 품질 관리 단계에서 합니다.
2. **원천값을 버리지 않습니다.** 값이 있던 칸이 NULL이 되면 그 원천값을 이슈 로그에 남깁니다.
3. **모든 행에 `_SRC_ROW_NO`가 있습니다.** Bronze의 같은 행 번호를 찾으면 원천값을 볼 수 있습니다.

## 무엇을 어떻게 바꿨나

### 1) 컬럼명
- 전부 UPPER_SNAKE로 바꾸고, 규칙서 2장의 접미사(`_NO`, `_DT`, `_DTM`, `_NM`, `_CD`, `_AMT`, `_CNT`, `_KG`, `_SEC`, `_RT`, `_YN` …)를 붙였습니다.
  - 예: `member_no` → `MBR_NO`, `RC_DATE` → `RC_DT`, `HR_NAME` → `HR_NM`
- 이름 충돌을 정리했습니다 (규칙서 8장).
  - `ticket_cnt` → 전표는 `TICKET_CNT`, 마권은 `UNIT_CNT`
  - `GRP_NO` → `TR_GRP_NO`
  - `BIRTH_RAW` → `HR_BIRTH_DT` / `TR_BIRTH_DT`

### 2) 날짜·시간
섞여 있는 형식을 순서대로 시도하고, 어느 것에도 안 맞으면 NULL로 둔 뒤 기록합니다. 이번 데이터에서 변환 실패는 0건이었습니다.

| 표준 타입 | 원천 형식 예 |
|:--|:--|
| DATE | `20260522`, `2026-05-22`, `2026.05.22`, `2026/05/22` |
| TIMESTAMP (KST) | `2026-05-22 10:44:00`, `20260529103300`, `20260522 23:58` |
| TIME | `10:45` → `10:45:00` |

- `START_DTM`은 `RC_DT`와 `START_TM`을 합친 값입니다.
- 참고: Parquet 특성상 TIMESTAMP·TIME은 밀리초 단위로 저장됩니다. 값은 같습니다.

### 3) 데이터 타입

| 표준 타입 | 대상 | 규칙 |
|:--|:--|:--|
| VARCHAR | 번호·이름 (`ORDER_NO`, `MBR_NO`, `TR_GRP_NO`) | 숫자처럼 보여도 문자. `TR_GRP_NO`는 앞 0 유지 |
| INT / BIGINT | 건수, 순위, 나이, 마번 / 금액 | 쉼표·단위를 떼고 변환. 소수가 나오면 실패로 기록 |
| DECIMAL | 배당률(6,1), 부담중량(4,1), 기록·구간·함수율(5,1), 착차(5,2) | **반올림하지 않음.** 자릿수를 넘으면 실패로 기록 |

### 4) 논리값
- `HR_WEEKLY_SNAPSHOT.TR_EXTERNAL_YN`: 조교사 칸이 `외부마`면 Y, 아니면 N입니다. Y는 25,428건입니다.

### 5) 코드 표준화 (규칙서 6장)
코드 변환 결과는 `meta/silver_value_map.csv`에 원천값 → 표준코드, 건수로 남아 있습니다. 주요 변환은 다음과 같습니다.

| 컬럼 | 원천 → 표준 | 바뀐 건수 |
|:--|:--|--:|
| `BET_TICKET.BET_TYPE_CD` | 단승/연승/복승 → WIN/PLC/QNL | 28,823 |
| `BET_TICKET.TICKET_STAT_CD` | sold/cancel/void → 대문자 | 2,655 |
| `BET_ORDER.CHNL_CD` | OTB01~OTB37 → OTB (+ 지점 번호 분리), 빈칸 → UNKNOWN | 1,556 |
| `MBR_MASTER.REGION_CD` | 서울특별시 → 서울 등 | 339 |
| `RC_SALES.BET_TYPE_CD` | 단식/연식/복식/복연/쌍식/삼복/삼쌍 → WIN/PLC/QNL/QPL/EXA/TRI/TLA | 2,702 |
| 말 성별 | 수/암/거 → M/F/G | 전 행 |
| 말 등급 | 제1~제6/미 → 1~6/NONE | 전 행 |
| 날씨, 주로 상태, 착차, 출전 상태, 경마장 | 한글 → 영문 코드 | 전 행 |

- 코드표에 없는 값은 0건이었습니다.
- 코드표에 없는 값이 나오면 NULL로 두고 이슈 로그에 `OUT_OF_CODE`로 남깁니다.

### 6) 한 칸에 여러 값 쪼개기 (규칙서 7장)

| 원천 | 예 | 결과 |
|:--|:--|:--|
| `WG_HR_RAW` | `279+14` | `HR_WGT_KG` 279, `HR_WGT_DIFF_KG` +14 |
| `RC_TIME_RAW` | `1:13.2` | `RC_TIME_SEC` 73.2 |
| `MARGIN_RAW` | `1½` / `코` / 빈칸 | `MARGIN_LEN` 1.5 + `MARGIN_CD` LEN / NOSE / FIRST |
| `PASS_ORD_RAW` | `1-  -  - 1- 1- 1` | `PASS_ORD_S1`~`S6` |
| `SECTION_TIMES_RAW` | `0:48.8 0:16.7               0:24.4 …` | `SECT1_SEC`~`SECT7_SEC`. 7글자 고정폭으로 자름 |
| `WEATHER_TRACK_RAW` | `날씨: 흐림  주로: 다습  (14%)` | `WEATHER_CD`, `TRACK_STAT_CD`, `TRACK_MOIST_RT` |
| `RANK_RAW` | `제5등급핸디캡` | `RC_GRADE_CD` 5, `BUDAM_TYPE_CD` HANDICAP |
| `PRIZE_RAW` | `순위상금: 700만원 …` | `PRIZE1_AMT`~`PRIZE5_AMT` (원) |
| `RC_COND_RAW` | `핸디캡  제주마제21회 KCTV배` | `HR_CLASS_NM` 제주마, `RC_TITLE_NM` 제21회 KCTV배 |
| `INTRO_PRICE_RAW` | `3,000천원(개별)` | `INTRO_AMT` 3,000,000, `INTRO_TYPE_NM` 개별 |
| `VET_NM_RAW` | `정치,낭치` | 브리지 테이블 2행 |
| JSON | 중첩 구조 | `RC_CHANGE_EVENT` 표로 펼침 |

### 7) 빈 값·공백
- 앞뒤 공백을 제거했습니다. `BET_TICKET.HR_NM` 5,164건, `BET_ORDER.MBR_NO` 46건입니다.
- 빈칸, 공백만 있는 값, `-----`는 NULL로 바꿨습니다.
- **예외:** 착차가 빈칸이면 `FIRST`(1착), 채널이 빈칸이면 `UNKNOWN`입니다.

### 8) 제외한 컬럼 (규칙서 9장)
- 제외한 컬럼: `unit_amt`, `PRD_NM`, `HR_BREED`, `RC_ENTRY/RC_ODDS.ORD_RAW`, `TITLE_RAW`, `RC_DOW`, `DIVIDEND_RAW`
- 사유는 `meta/data_dictionary.csv`에 `COL_NM=(제외)`로 남겼고, 원천값은 Bronze에 그대로 있습니다.

### 9) 테이블 분리
- `RC_SALES`의 '합계' 386행 → `RC_SALES_TOTAL`
- `HR_VET_HIST`의 진료명 → `HR_VET_TYPE_BRIDGE` 1,664행

## 기록 파일 (`meta/`)

| 파일 | 열면 알 수 있는 것 |
|:--|:--|
| `data_dictionary.csv` | 종합 데이터 사전 중 `LAYER = SILVER` 행: Silver 컬럼마다 타입, 어느 원천 컬럼에서 왔는지, 어떤 규칙을 적용했는지 (162줄) |
| `silver_value_map.csv` | 코드 컬럼에서 원천값이 어떤 표준코드로 몇 건 바뀌었는지 |
| `silver_issue_log.csv` | 원천에 값이 있었는데 NULL이 된 칸 전부. `SRC_ROW_NO`, `RAW_VAL`(원천값), `ISSUE_CD`, `NOTE`(사유) |
| `silver_column_profile.csv` | 컬럼별 행 수, NULL 수, TRIM 수, 변환 실패·코드표 밖·규칙상 NULL 건수 |

### 이슈 로그 내용 (38,305건, 모두 `RULE_NULL`)

`RULE_NULL`은 규칙에 따라 일부러 NULL로 둔 값입니다. 실패는 아니지만 원천값을 보존하려고 기록했습니다.

| 테이블.컬럼 | 건수 | 원천값과 사유 |
|:--|--:|:--|
| HR_WEEKLY_SNAPSHOT.TR_NM | 25,428 | `외부마`는 사람 이름이 아님 → `TR_EXTERNAL_YN`=Y |
| HR_WEEKLY_SNAPSHOT.INTRO_AMT | 12,363 | `자가생산`은 금액 없음 |
| RC_RACE.RC_TITLE_NM | 361 | `일반`은 경주명 없음 |
| RC_RACE.TRACK_MOIST_RT | 21 | 주로 `불량`은 함수율 표기 없음 |
| RC_ODDS.WIN_ODDS / PLC_ODDS | 22 / 22 | `-----` = 값 없음 |
| RC_RESULT.FINISH_ORD | 22 | `94`·`95`는 순위 아님 |
| RC_RESULT.HR_WGT_KG | 22 | 뛰지 않은 말의 체중 `0` |
| RC_RESULT.RC_TIME_SEC | 22 | `경주제외`·`출주취소` 글자 |
| RC_RESULT.PASS_ORD_S1 | 22 | `-  -  -  -` = 통과 순위 기록 없음 |

- 변환 실패(`PARSE_FAIL`)와 코드표 밖 값(`OUT_OF_CODE`)은 0건입니다.

## 검증 결과 (`src/02_normalize_check.py`)

| 점검 | 기대 | 결과 |
|:--|--:|--:|
| 14개 테이블 행 수 | 규칙서 11장 | 전부 일치 |
| 행 보존 (Bronze 행이 빠짐·중복 없이 Silver에 있는지) | 전 테이블 | O |
| RC_SALES + RC_SALES_TOTAL = Bronze RC_SALES | 3,088 | 3,088 |
| 브리지 행 = 진료명 항목 수 | 1,664 | 1,664 |
| 변환 실패 (날짜·일시 포함) | 0 | 0 |
| 코드표 밖 값 | 0 | 0 |
| MBR_MASTER.BIRTH_DT NULL | 27 | 27 |
| RC_ODDS.WIN_ODDS NULL | 22 | 22 |
| RC_RACE.TRACK_MOIST_RT NULL | 21 | 21 |
| RC_RESULT.FINISH_ORD NULL | 22 | 22 |
| TR_EXTERNAL_YN = Y | 25,428 | 25,428 |
| 진료명 여러 개인 행 | 176 | 176 |
| RC_SALES_TOTAL 경주당 1행 | 386 | 386 |
| 원천값 보존 (NULL이 된 원천값 수 = 로그 수, 1:1 컬럼 115개) | 불일치 0 | 0 |
| Bronze 컬럼이 전부 데이터 사전에 (사용 또는 제외로) 있는지 | 누락 0 | 0 |
| 재실행 시 Bronze·Silver·meta 파일 해시 | 동일 | 동일 |

## 진행 중 나온 차이

| 차이 | 원인 | 처리 |
|:--|:--|:--|
| `PASS_ORD_RAW` 22건이 처음에 변환 실패로 잡힘 | 뛰지 않은 말은 값이 `-  -  -  -`라서 '-'로 나누면 6칸이 아니라 5칸 | 기록 없음으로 보고 S1~S6 NULL. 이슈 로그에 `RULE_NULL`로 기록. → 팀 합의로 규칙서 12장에 반영됨 |
| 원천값 보존 검증에서 `WIN_ODDS`·`PLC_ODDS` 불일치 | 검증 스크립트가 `-----`를 처음부터 빈칸으로 취급해 로그 22건과 맞지 않음 (데이터 문제 아님) | 검증 기준을 더 엄격하게 고침 (완전 빈 문자열만 값 없음으로 봄) → 통과 |

## Silver에 그대로 남아 있는 문제 (다음 단계)

→ 품질 관리(`src/03_quality.py`)에서 처리했습니다. 표준화 결과는 그대로 두고 `data/02_silver/clean/`과 `_excluded/`에 따로 저장합니다. 결과는 `docs/품질관리.md`에 있습니다.

| 문제 | 건수 |
|:--|--:|
| `BET_TICKET` 완전 중복 행 | 1,052 |
| 전표(`BET_ORDER`)와 마권 합계의 장수·금액 불일치 (중복 제거 후 기준) | 93 |
| 취소 전표인데 원래 전표번호(`ORIG_ORDER_NO`)가 없음 | 644 |
