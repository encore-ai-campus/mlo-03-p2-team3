# Bronze 컬럼 사전

[데이터 안내](DATA_GUIDE.md) · [원천 현황](AS-IS.md) · [Bronze](BRONZE.md) · [Bronze 컬럼](BRONZE_COLUMNS.md) · [Silver](SILVER.md) · [Silver 컬럼](SILVER_COLUMNS.md)

> 기록 기준: 2026-11-20 (KST). 완료·미수행·계획을 구분합니다.

## 읽는 방법

현재 Parquet의 실제 스키마와 값을 확인한 컬럼 사전입니다. 원천 컬럼 순서를 그대로 기록하고 마지막에 출처 두 컬럼을 표시합니다.
CSV 컬럼은 원문 보존을 위해 문자열로 저장하며 표준 타입은 아직 적용하지 않았습니다.
`string`/`large_string`은 실제 Arrow 문자열 타입이고, `struct<...>`는 JSON 중첩 객체입니다.
예시는 Markdown 코드 안에 원문을 넣었습니다. 긴 예시는 말줄임 표시를 붙였습니다.
NULL 수는 실제 Arrow null, 빈 문자열 수는 정확히 길이 0인 값의 수입니다. JSON 객체 내부 null은 상위 컬럼 null 집계와 다릅니다.

## 모든 파일의 공통 출처 컬럼

| 컬럼 | 의미 | 형식·정책 |
| --- | --- | --- |
| source_file | 원천 파일명과 확장자 | 경로 제외. 예: bet_order.csv |
| ingested_at | 해당 원천 내용의 최초 성공 수집 시각 | 문자열 YYYY-MM-DD HH:MI:SS, KST. 같은 경로·SHA-256·시트는 기존 성공 이력 재사용 |

파일명만으로 다른 폴더의 동명 파일을 구분할 수는 없습니다. 전체 경로와 시트는 별도 수집 이력에서 확인합니다.

## race_change_events

원천: `../data/00_origin/event/race_change_events.jsonl`<br>
Bronze: `data/01_bronze/event/race_change_events.parquet`<br>
행 수: **149**, 원천 컬럼 **7개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `eventType` | 이벤트 종류 원천값 | `string` | `TRACK_STATUS` | 0 | 0 |
| `announcedAt` | 발표 일시 원문 | `string` | `20260522 23:58` | 0 | 0 |
| `trackRaw` | 주로 상태 원문 | `string` | `다습      ( 14.0%)` | 97 | 0 |
| `race` | 경주 정보 중첩 객체 | `struct<rcDate: string, rcNo: string>` | `{"rcDate": "2026/05/23", "rcNo": "1"}` | 52 | — |
| `horse` | 말 정보 중첩 객체 | `struct<chulNo: string, hrName: string>` | `{"chulNo": "6", "hrName": "원평가속도"}` | 52 | — |
| `change` | 변경 내역 중첩 객체 | `struct<before: string, after: string, budamRaw: string, reason: string>` | `{"before": "나유나", "after": "임재광", "budamRaw": "55.0", "reason": "감기몸살"}` | 74 | — |
| `reason` | 취소 사유 원문 | `string` | `오른 앞다리 절음` | 127 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `race_change_events.jsonl` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

### JSON 중첩 필드 의미

아래 필드는 독립된 최상위 컬럼으로 펼치지 않았습니다. 상위 struct 안의 원천 필드이며 이벤트 종류에 따라 존재하지 않을 수 있습니다.

| 중첩 경로 | 의미 | 현재 타입·처리 |
| --- | --- | --- |
| race.rcDate | 변경 대상 경주일 | string; YYYY/MM/DD 원문 |
| race.rcNo | 변경 대상 경주번호 | string; 원문 유지 |
| horse.chulNo | 변경 대상 출전마 번호 | string; 원문 유지 |
| horse.hrName | 변경 대상 말 이름 | string; 공백 포함 원문 유지 |
| change.before | 변경 전 기수명 | string; 원문 유지 |
| change.after | 변경 후 기수명 | string; 원문 유지 |
| change.budamRaw | 변경 관련 부담중량 원문 | string; 숫자로 변환하지 않음 |
| change.reason | 변경 사유 | string; 원문 유지 |

## HR_VET_HIST

원천: `../data/00_origin/horse/HR_VET_HIST.csv`<br>
Bronze: `data/01_bronze/horse/HR_VET_HIST.parquet`<br>
행 수: **1,488**, 원천 컬럼 **6개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `VET_DT_RAW` | 진료일 원문 | `large_string` | `2026.05.16` | 0 | 0 |
| `HR_NAME` | 말 이름 | `large_string` | `대방가` | 0 | 0 |
| `TR_GRP_NO` | 조교사 조 번호 원문 | `large_string` | `05` | 0 | 0 |
| `VET_PLACE_NM` | 진료 장소 명칭 | `large_string` | `KRA 제주경마` | 0 | 0 |
| `VET_NM_RAW` | 진료명 원문; 여러 값이 함께 있을 수 있음 | `large_string` | `우전지파행` | 0 | 0 |
| `REPORT_DT` | 보고일 원문 | `large_string` | `20260520` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `HR_VET_HIST.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## HR_WEEKLY_SNAPSHOT

원천: `../data/00_origin/horse/HR_WEEKLY_SNAPSHOT.csv`<br>
Bronze: `data/01_bronze/horse/HR_WEEKLY_SNAPSHOT.parquet`<br>
행 수: **52,642**, 원천 컬럼 **23개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `SNAPSHOT_DT` | 스냅샷 기준일 원문 | `large_string` | `20260520` | 0 | 0 |
| `HR_NAME` | 말 이름 | `large_string` | `가라공주` | 0 | 0 |
| `PRD_NM` | 원천 생산지 명칭 | `large_string` | `제` | 0 | 0 |
| `SEX_NM` | 말 성별 원천 명칭 | `large_string` | `암` | 0 | 0 |
| `BIRTH_RAW` | 출생일 원문 | `large_string` | `2022/05/15` | 0 | 0 |
| `AGE_RAW` | 나이 원문 | `large_string` | `4` | 0 | 0 |
| `GRADE_RAW` | 말 등급 원문 | `large_string` | `제6` | 0 | 0 |
| `TR_GRP_NO` | 조교사 조 번호 원문 | `large_string` | `88` | 0 | 0 |
| `TR_NAME` | 조교사 이름 또는 외부마 표시 | `large_string` | `외부마` | 0 | 0 |
| `OW_NAME` | 마주 이름 | `large_string` | `조종호` | 0 | 0 |
| `TOT_RC_CNT` | 통산 출전 횟수 원문 | `large_string` | `5` | 0 | 0 |
| `TOT_1ST` | 통산 1위 횟수 원문 | `large_string` | `0` | 0 | 0 |
| `TOT_2ND` | 통산 2위 횟수 원문 | `large_string` | `1` | 0 | 0 |
| `TOT_3RD` | 통산 3위 횟수 원문 | `large_string` | `0` | 0 | 0 |
| `Y1_RC_CNT` | 최근 1년 출전 횟수 원문 | `large_string` | `5` | 0 | 0 |
| `Y1_1ST` | 최근 1년 1위 횟수 원문 | `large_string` | `0` | 0 | 0 |
| `Y1_2ND` | 최근 1년 2위 횟수 원문 | `large_string` | `1` | 0 | 0 |
| `Y1_3RD` | 최근 1년 3위 횟수 원문 | `large_string` | `0` | 0 | 0 |
| `PRIZE_AMT_RAW` | 상금 금액 원문 | `large_string` | `3220000` | 0 | 0 |
| `RATING_RAW` | 레이팅 원문 | `large_string` | `1` | 0 | 18,298 |
| `INTRO_PRICE_RAW` | 도입 가격·도입 구분 원문 | `large_string` | `3,000천원(개별)` | 0 | 0 |
| `SIRE_NAME` | 부마 이름 | `large_string` | `화룡특급` | 0 | 0 |
| `DAM_NAME` | 모마 이름 | `large_string` | `희망여신` | 0 | 397 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `HR_WEEKLY_SNAPSHOT.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## TR_WEEKLY_SNAPSHOT

원천: `../data/00_origin/horse/TR_WEEKLY_SNAPSHOT.csv`<br>
Bronze: `data/01_bronze/horse/TR_WEEKLY_SNAPSHOT.parquet`<br>
행 수: **954**, 원천 컬럼 **14개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `SNAPSHOT_DT` | 스냅샷 기준일 원문 | `large_string` | `20260520` | 0 | 0 |
| `TR_NAME` | 조교사 이름 또는 외부마 표시 | `large_string` | `강대은` | 0 | 0 |
| `GRP_NO` | 조교사 조 번호 원문 | `large_string` | `03` | 0 | 0 |
| `BIRTH_RAW` | 출생일 원문 | `large_string` | `1964/01/04` | 0 | 0 |
| `AGE_RAW` | 나이 원문 | `large_string` | `62` | 0 | 0 |
| `DEBUT_RAW` | 데뷔일 원문 | `large_string` | `2002/04/29` | 0 | 0 |
| `TOT_RC_CNT` | 통산 출전 횟수 원문 | `large_string` | `8211` | 0 | 0 |
| `TOT_1ST` | 통산 1위 횟수 원문 | `large_string` | `828` | 0 | 0 |
| `TOT_2ND` | 통산 2위 횟수 원문 | `large_string` | `826` | 0 | 0 |
| `TOT_3RD` | 통산 3위 횟수 원문 | `large_string` | `843` | 0 | 0 |
| `Y1_RC_CNT` | 최근 1년 출전 횟수 원문 | `large_string` | `293` | 0 | 0 |
| `Y1_1ST` | 최근 1년 1위 횟수 원문 | `large_string` | `23` | 0 | 0 |
| `Y1_2ND` | 최근 1년 2위 횟수 원문 | `large_string` | `29` | 0 | 0 |
| `Y1_3RD` | 최근 1년 3위 횟수 원문 | `large_string` | `17` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `TR_WEEKLY_SNAPSHOT.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## MBR_MASTER

원천: `../data/00_origin/member/MBR_MASTER.csv`<br>
Bronze: `data/01_bronze/member/MBR_MASTER.parquet`<br>
행 수: **4,383**, 원천 컬럼 **6개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `MBR_NO` | 회원번호 | `large_string` | `M0012346` | 0 | 0 |
| `BIRTH_DT` | 생년월일 원문 | `large_string` | `1957-10-25` | 0 | 27 |
| `JOIN_DT` | 가입일 원문 | `large_string` | `20220323` | 0 | 0 |
| `REGION_NM` | 거주 지역 원천 명칭 | `large_string` | `경북` | 0 | 0 |
| `MBR_GRADE_CD` | 회원 등급 코드 | `large_string` | `NORMAL` | 0 | 0 |
| `MBR_STAT_CD` | 회원 상태 코드 | `large_string` | `10` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `MBR_MASTER.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## bet_order

원천: `../data/00_origin/order/bet_order.csv`<br>
Bronze: `data/01_bronze/order/bet_order.parquet`<br>
행 수: **27,907**, 원천 컬럼 **9개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `order_no` | 전표번호 | `large_string` | `BC00489449` | 0 | 0 |
| `order_type_cd` | 전표 구분 코드 | `large_string` | `CANCEL` | 0 | 0 |
| `orig_order_no` | 원 전표번호 | `large_string` | `BS00489465` | 0 | 24,446 |
| `member_no` | 회원번호 | `large_string` | `M0016321` | 0 | 4,921 |
| `channel_cd` | 발매 채널 원천 코드 | `large_string` | `OTB01` | 0 | 13 |
| `sale_dtm` | 발매 일시 원문 | `large_string` | `20260529103300` | 0 | 0 |
| `biz_date` | 영업일 원문 | `large_string` | `20260529` | 0 | 0 |
| `ticket_cnt` | 전표 마권 장수 원문 | `large_string` | `9` | 0 | 0 |
| `total_amt` | 전표 합계 금액 원문 | `large_string` | `-61000` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `bet_order.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## bet_ticket

원천: `../data/00_origin/order/bet_ticket.csv`<br>
Bronze: `data/01_bronze/order/bet_ticket.parquet`<br>
행 수: **523,416**, 원천 컬럼 **13개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `order_no` | 전표번호 | `large_string` | `BC00489449` | 0 | 0 |
| `ticket_seq` | 전표 내 마권 순번 | `large_string` | `1` | 0 | 0 |
| `rc_date` | 경주일 원문 | `large_string` | `20260529` | 0 | 0 |
| `rc_no` | 경주번호 | `large_string` | `9` | 0 | 0 |
| `bet_type_cd` | 승식 원천 코드 | `large_string` | `복승` | 0 | 0 |
| `chul_no` | 첫 번째 출전마 번호 | `large_string` | `1` | 0 | 0 |
| `hr_name` | 첫 번째 말 이름 | `large_string` | `일사만리` | 0 | 1,563 |
| `chul_no2` | 두 번째 출전마 번호 | `large_string` | `8` | 0 | 416,107 |
| `hr_name2` | 두 번째 말 이름 | `large_string` | `한백제왕` | 0 | 416,107 |
| `ticket_cnt` | 마권 구좌 수 원문 | `large_string` | `-108` | 0 | 0 |
| `unit_amt` | 원천 단위 금액 | `large_string` | `100` | 0 | 0 |
| `bet_amt` | 베팅 금액 원문 | `large_string` | `-10800` | 0 | 0 |
| `ticket_status` | 마권 상태 원천 코드 | `large_string` | `CANCEL` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `bet_ticket.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:35` | 0 | 0 |

## RC_ENTRY

원천: `../data/00_origin/race/RC_ENTRY.csv`<br>
Bronze: `data/01_bronze/race/RC_ENTRY.parquet`<br>
행 수: **3,666**, 원천 컬럼 **13개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `RC_DATE` | 경주일 원문 | `large_string` | `20260522` | 0 | 0 |
| `RC_NO` | 경주번호 | `large_string` | `1` | 0 | 0 |
| `ORD_RAW` | 착순 또는 출전 상태 원문 | `large_string` | `1` | 0 | 0 |
| `CHUL_NO` | 출전마 번호 | `large_string` | `6` | 0 | 0 |
| `HR_NAME` | 말 이름 | `large_string` | `센돌이` | 0 | 0 |
| `HR_BREED` | 말 품종 원문 | `large_string` | `제` | 0 | 0 |
| `HR_SEX` | 말 성별 원문 | `large_string` | `거` | 0 | 0 |
| `HR_AGE` | 말 나이 원문 | `large_string` | `3` | 0 | 0 |
| `WG_BUDAM_RAW` | 부담중량 원문 | `large_string` | `55.0` | 0 | 0 |
| `JK_NAME` | 기수 이름 | `large_string` | `박성광` | 0 | 0 |
| `TR_NAME` | 조교사 이름 또는 외부마 표시 | `large_string` | `이태용` | 0 | 0 |
| `OW_NAME` | 마주 이름 | `large_string` | `오치영` | 0 | 0 |
| `RATING_RAW` | 레이팅 원문 | `large_string` | `9` | 0 | 716 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `RC_ENTRY.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:37` | 0 | 0 |

## RC_ODDS

원천: `../data/00_origin/race/RC_ODDS.csv`<br>
Bronze: `data/01_bronze/race/RC_ODDS.parquet`<br>
행 수: **3,666**, 원천 컬럼 **7개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `RC_DATE` | 경주일 원문 | `large_string` | `20260522` | 0 | 0 |
| `RC_NO` | 경주번호 | `large_string` | `1` | 0 | 0 |
| `ORD_RAW` | 착순 또는 출전 상태 원문 | `large_string` | `1` | 0 | 0 |
| `CHUL_NO` | 출전마 번호 | `large_string` | `6` | 0 | 0 |
| `SECTION_TIMES_RAW` | 구간 기록 복합 원문 | `large_string` | `0:48.8 0:16.7               0:24.4 0:40.4 0:16.8` | 0 | 22 |
| `WIN_ODDS_RAW` | 단승 배당률 원문 | `large_string` | `1.9` | 0 | 0 |
| `PLACE_ODDS_RAW` | 연승 배당률 원문 | `large_string` | `1.1` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `RC_ODDS.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:37` | 0 | 0 |

## RC_RACE

원천: `../data/00_origin/race/RC_RACE.csv`<br>
Bronze: `data/01_bronze/race/RC_RACE.parquet`<br>
행 수: **386**, 원천 컬럼 **13개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `RC_DATE` | 경주일 원문 | `large_string` | `20260522` | 0 | 0 |
| `RC_NO` | 경주번호 | `large_string` | `1` | 0 | 0 |
| `TITLE_RAW` | 원천 제목 | `large_string` | `제목 :   2026년05월22일(금)  제 01경주` | 0 | 0 |
| `RC_DOW` | 경주 요일 원문 | `large_string` | `금` | 0 | 0 |
| `MEET_NM` | 경마장 명칭 | `large_string` | `제주` | 0 | 0 |
| `RC_DAY_RAW` | 경주 일차 원문 | `large_string` | `제 40일` | 0 | 0 |
| `RC_DIST_RAW` | 경주 거리 원문 | `large_string` | `0900M` | 0 | 0 |
| `RANK_RAW` | 경주 등급·부담 방식 원문 | `large_string` | `제6등급별정A` | 0 | 0 |
| `RC_COND_RAW` | 경주 조건·대회 명칭 원문 | `large_string` | `제주마일반` | 0 | 0 |
| `WEATHER_TRACK_RAW` | 날씨·주로 상태·함수율 복합 원문 | `large_string` | `날씨: 흐림            주로: 다습        (14%)` | 0 | 0 |
| `PRIZE_RAW` | 순위별 상금 복합 원문 | `large_string` | `순위상금:        700만원       322만원       210만원        98만원        70만원` | 0 | 0 |
| `DIVIDEND_RAW` | 원천 배당 설명 | `large_string` | `배당률 단: ⑥1.9        연: ⑥1.1 ⑩1.4 ⑧2.3          복: ⑥⑩3.9       4F:1:03.7 &#124; 3F:0:48.8 &#124; 쌍: ⑥⑩5.8                                      주로:② &#124; 복연: ⑥⑩2.0...` | 0 | 0 |
| `START_TM_RAW` | 출발 시각 원문 | `large_string` | `10:45` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `RC_RACE.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:37` | 0 | 0 |

## RC_RESULT

원천: `../data/00_origin/race/RC_RESULT.csv`<br>
Bronze: `data/01_bronze/race/RC_RESULT.parquet`<br>
행 수: **3,666**, 원천 컬럼 **9개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `RC_DATE` | 경주일 원문 | `large_string` | `20260522` | 0 | 0 |
| `RC_NO` | 경주번호 | `large_string` | `1` | 0 | 0 |
| `ORD_RAW` | 착순 또는 출전 상태 원문 | `large_string` | `1` | 0 | 0 |
| `CHUL_NO` | 출전마 번호 | `large_string` | `6` | 0 | 0 |
| `HR_NAME` | 말 이름 | `large_string` | `센돌이` | 0 | 0 |
| `WG_HR_RAW` | 마체중·증감 복합 원문 | `large_string` | `279+14` | 0 | 0 |
| `RC_TIME_RAW` | 경주 기록 또는 출전 상태 원문 | `large_string` | `1:13.2` | 0 | 0 |
| `MARGIN_RAW` | 착차 원문 | `large_string` | `목` | 0 | 386 |
| `PASS_ORD_RAW` | 구간 통과 순위 복합 원문 | `large_string` | `1-  -  - 1- 1- 1` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `RC_RESULT.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:37` | 0 | 0 |

## RC_SALES

원천: `../data/00_origin/race/RC_SALES.csv`<br>
Bronze: `data/01_bronze/race/RC_SALES.parquet`<br>
행 수: **3,088**, 원천 컬럼 **4개** + 출처 컬럼 **2개**.

| 컬럼명 | 의미 | 현재 Arrow 타입 | 원천 예시 / 추가 값 | NULL 수 | 빈 문자열 수 |
| --- | --- | --- | --- | --- | --- |
| `RC_DATE` | 경주일 원문 | `large_string` | `20260522` | 0 | 0 |
| `RC_NO` | 경주번호 | `large_string` | `1` | 0 | 0 |
| `POOL_NM` | 매출 승식 명칭 또는 합계 | `large_string` | `단식` | 0 | 0 |
| `SALES_AMT_RAW` | 매출액 원문 | `large_string` | `12,548,000` | 0 | 0 |
| `source_file` | 원천 파일명과 확장자; 경로 제외 | `string` | `RC_SALES.csv` | 0 | 0 |
| `ingested_at` | 동일 경로·내용·시트의 최초 성공 수집 시각; KST | `string` | `2026-11-20 14:40:37` | 0 | 0 |

## 변경 이력

| 일자 (KST) | 변경 |
| --- | --- |
| 2026-11-20 | 실제 Bronze 12개 파일의 전체 원천 컬럼과 추가 출처 두 컬럼을 문서화 |
