# AS-IS 원천 데이터 현황

[데이터 안내](DATA_GUIDE.md) · [원천 현황](AS-IS.md) · [Bronze](BRONZE.md) · [Bronze 컬럼](BRONZE_COLUMNS.md) · [Silver](SILVER.md) · [Silver 컬럼](SILVER_COLUMNS.md)

> 기록 기준: 2026-11-20 (KST). 완료·미수행·계획을 구분합니다.

## 조사 범위

원천 12개 파일을 읽기만 하여 목록·행 수·컬럼과 아래 항목을 확인했습니다.
이 AS-IS 조사는 원천을 읽기만 했습니다. 이후 Silver 표준화를 수행했으며 실제 변경은 [Silver 기록](SILVER.md)에 분리해 정리했습니다. 품질 정제는 미수행입니다. 컬럼 의미는 원천 이름과 [매핑 규칙서](../meta/mapping_rules.md)를 참고한 설명이며 원천값은 변경하지 않았습니다.

| 원천 상대 경로 (`../data/00_origin` 기준) | 내용 | 원천 행 수 | 원천 열 수 | Bronze 열 수 |
| --- | --- | --- | --- | --- |
| `event/race_change_events.jsonl` | 경주 변경 이벤트 | 149 | 7 | 9 |
| `horse/HR_VET_HIST.csv` | 말 진료 이력 | 1,488 | 6 | 8 |
| `horse/HR_WEEKLY_SNAPSHOT.csv` | 말 주간 스냅샷 | 52,642 | 23 | 25 |
| `horse/TR_WEEKLY_SNAPSHOT.csv` | 조교사 주간 스냅샷 | 954 | 14 | 16 |
| `member/MBR_MASTER.csv` | 회원 기본 정보 | 4,383 | 6 | 8 |
| `order/bet_order.csv` | 발매·취소 전표 | 27,907 | 9 | 11 |
| `order/bet_ticket.csv` | 전표에 포함된 마권 | 523,416 | 13 | 15 |
| `race/RC_ENTRY.csv` | 경주 출전 정보 | 3,666 | 13 | 15 |
| `race/RC_ODDS.csv` | 경주 배당·구간 기록 | 3,666 | 7 | 9 |
| `race/RC_RACE.csv` | 경주 기본 정보 | 386 | 13 | 15 |
| `race/RC_RESULT.csv` | 경주 결과 | 3,666 | 9 | 11 |
| `race/RC_SALES.csv` | 승식별 매출 | 3,088 | 4 | 6 |
| **합계** | **12개 파일** | **625,411** | — | — |

## 경주 매출 및 마권 발매 내역 현황

RC_SALES는 제주 경주의 전체 마권 매출을 경주·승식별로 집계한 자료다. BET_TICKET에는 전표별 마권 거래금액과 발매·취소·무효 상태가 기록되어 있다.

동일 경주의 단승 금액을 대조한 결과, 두 자료의 합계에 차이가 있었다. 본 프로젝트에서는 BET_TICKET을 발매 거래의 일부 범위를 담은 상세 자료로 간주하며, 경주 전체 매출은 RC_SALES를 기준으로 집계한다.

**자료 출처** · 발매 전표와 상세 내역(BET_ORDER, BET_TICKET)은 공개 거래 데이터를 마권 발매 시나리오에 맞춰 재구성했다. Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository, CC BY 4.0.

## 확인한 구조·품질 징후

| ID | 대상 | 실제 확인 내용 | 이번 단계 처리 | 후속 작업 |
| --- | --- | --- | --- | --- |
| ASIS-001 | 원천 컬럼명 | 소문자 snake_case, 대문자, camelCase 공존 | 그대로 보존 | Silver에서 공용 네이밍 규칙 적용 예정 |
| ASIS-002 | MBR_MASTER.BIRTH_DT | 세 가지 날짜 표현 존재; 아래 형식별 집계 참조 | 그대로 보존 | Silver에서 DATE 변환·실패 기록 |
| ASIS-003 | bet_order.sale_dtm | 두 가지 일시 표현 존재; 아래 집계 참조 | 그대로 보존 | Silver에서 KST 일시로 해석 예정 |
| ASIS-004 | bet_ticket.csv | 완전히 같은 원천 행의 첫 행 이후 중복 1,052행 | 중복 유지 | 정제 단계에서 근거 결정 ID 확정 후 처리 |
| ASIS-005 | RC_SALES.POOL_NM | 합계 386행 포함; 총 3,088행 | 분리하지 않음 | Silver에서 본문/합계 분리 후 행 수 대사 |
| ASIS-006 | HR_VET_HIST.VET_NM_RAW | 쉼표가 포함된 진료명 176행 | 쪼개지 않음 | Silver에서 브리지 생성 기준과 항목 수 검증 |
| ASIS-007 | JSONL | 이벤트별 선택 필드와 중첩 객체 존재 | 중첩 struct 유지, 없는 필드만 null 표현 | Silver에서 표준 컬럼으로 펼칠 예정 |
| ASIS-008 | 여러 문자열 컬럼 | 빈 문자열·앞뒤 공백·정확히 -----인 값 관측 | 원문 유지 | Silver에서 규칙별 변환과 원천값 추적 |

ASIS ID는 관찰 항목 식별자입니다. 정제 규칙의 근거 결정 ID나 처리 승인을 대신하지 않습니다.
중복 건수는 모든 원천 컬럼으로 `duplicated(keep="first")`를 계산한 값입니다. 중복 그룹 수나 정제 후 행 수가 아닙니다.
진료명 집계는 쉼표 포함 여부만 검사한 값이며, 브리지 출력 행 수를 검증한 결과가 아닙니다.

## 날짜·일시 표현 실측

| 컬럼 | 원천 표현 패턴 | 행 수 |
| --- | --- | --- |
| MBR_MASTER.BIRTH_DT | YYYYMMDD | 4,108 |
| MBR_MASTER.BIRTH_DT | YYYY-MM-DD | 164 |
| MBR_MASTER.BIRTH_DT | YYYY.MM.DD | 84 |
| MBR_MASTER.BIRTH_DT | 빈 문자열 | 27 |
| bet_order.sale_dtm | YYYY-MM-DD HH:MI:SS | 26,364 |
| bet_order.sale_dtm | YYYYMMDDHHMISS | 1,543 |

정규식 모양 기준의 집계입니다. 실제 달력 유효성이나 일시 변환 성공 여부를 검증한 수치가 아닙니다.

## 빈 문자열·공백·표시값 실측

| 원천 상대 경로 | 컬럼 | 빈 문자열 수 | 앞뒤 공백 포함 수 | 정확히 ----- 수 |
| --- | --- | --- | --- | --- |
| horse/HR_WEEKLY_SNAPSHOT.csv | RATING_RAW | 18,298 | 0 | 0 |
| horse/HR_WEEKLY_SNAPSHOT.csv | DAM_NAME | 397 | 0 | 0 |
| member/MBR_MASTER.csv | BIRTH_DT | 27 | 0 | 0 |
| order/bet_order.csv | orig_order_no | 24,446 | 0 | 0 |
| order/bet_order.csv | member_no | 4,921 | 46 | 0 |
| order/bet_order.csv | channel_cd | 13 | 0 | 0 |
| order/bet_ticket.csv | hr_name | 1,563 | 5,164 | 0 |
| order/bet_ticket.csv | chul_no2 | 416,107 | 0 | 0 |
| order/bet_ticket.csv | hr_name2 | 416,107 | 0 | 0 |
| race/RC_ENTRY.csv | RATING_RAW | 716 | 0 | 0 |
| race/RC_ODDS.csv | SECTION_TIMES_RAW | 22 | 0 | 0 |
| race/RC_ODDS.csv | WIN_ODDS_RAW | 0 | 0 | 22 |
| race/RC_ODDS.csv | PLACE_ODDS_RAW | 0 | 0 | 22 |
| race/RC_RACE.csv | DIVIDEND_RAW | 0 | 386 | 0 |
| race/RC_RESULT.csv | MARGIN_RAW | 386 | 0 | 0 |

빈 문자열은 길이 0인 문자열, 공백 포함 수는 `값 != 값.strip()`인 문자열 수입니다.
범주는 중복될 수 있습니다. 위 표에는 한 항목이라도 0이 아닌 문자열 컬럼만 표시했습니다.
JSON 객체 내부의 하위 필드는 이 문자열 집계에 포함하지 않았습니다. Parquet의 NULL과 CSV 빈 문자열은 구분합니다.

## 아직 검증하지 않은 사항

| 항목 | 현재 상태 |
| --- | --- |
| 전표·마권의 장수/금액 대사 및 취소 연결 | 미수행; 예시 문서의 93건·644건을 현재 실측으로 사용하지 않음 |
| 표준화 형식·코드 검증 | Silver 변환 실패·코드표 밖 값 0건 확인. 상세는 [Silver 검증](SILVER.md) 참조. 도메인 품질·논리적 이상값 정제는 미수행 |
| 테이블 PK/FK, Gold 사실·차원 키 | 미수행; 단순 후보 키를 유일키로 확정하지 않음 |
| 실제 외부 다운로드 일시 | 확인 불가; ingested_at으로 추정하지 않음 |

## 변경 이력

| 일자 (KST) | 작업 | 결과 |
| --- | --- | --- |
| 2026-11-20 | 원천 현황·일부 품질 징후 조사 | 원천 수정 없이 파일 목록·컬럼·행 수 및 관찰 수치 기록 |
| 2026-11-20 | 사용자 제공 경주 매출·마권 발매 내역 설명 반영 | 두 자료의 집계 범위 차이, 경주 전체 매출 기준 및 재구성 거래 데이터 출처 명시 |
