# 데이터 파이프라인 안내

[데이터 안내](DATA_GUIDE.md) · [원천 현황](AS-IS.md) · [Bronze](BRONZE.md) · [Bronze 컬럼](BRONZE_COLUMNS.md) · [Silver](SILVER.md) · [Silver 컬럼](SILVER_COLUMNS.md)

> 기록 기준: 2026-11-20 (KST). 완료·미수행·계획을 구분합니다.

## 현재 진행 상태

| 단계 | 상태 | 입력 → 출력 | 현재 기록 |
| --- | --- | --- | --- |
| 원천 / AS-IS | 현황 확인 완료 | `../data/00_origin` 읽기 전용 | 12개 파일, 625,411행; 일부 품질 징후 실측 |
| Bronze | 구현·생성·검증 완료 | `../data/00_origin` → `data/01_bronze/` | 원천 보존 + source_file / ingested_at 추가 |
| Silver 표준화 | 구현·생성·검증 완료 | `../data/01_bronze` → `data/02_silver/` | 평면 Parquet 14개; 입력 행 보존·표준화 변환 건수 기록 |
| Silver 품질 관리 | 구현·생성·읽기 전용 재검증 완료 | 표준화 14개 → clean 14개 + 중복 제외 1개 | D-001~D-012; 중복 1,052행 제외, 진료 유형 의미 병합 감소 2행 별도 대사; QUALITY_REVIEW.md 참조 |
| Gold | 구현·생성·읽기 전용 재검증 완료 | clean → `../data/03_gold` | fact 41,141행·차원5개; 적격39,284행·확인취소894묶음; 공통 차원 계약은 이 브랜치 제안 |

현재 문서 작성 브랜치는 `FCT_BET_CANCEL`입니다. 앞선 Bronze 작업은 사용자 요청으로 만든 `KEB`에서 진행했습니다.

## 문서 읽는 순서

| 문서 | 확인할 내용 |
| --- | --- |
| [AS-IS.md](AS-IS.md) | 원천 목록, 실제 관측한 문제와 아직 검증하지 않은 항목 |
| [bronze_usage.md](bronze_usage.md) | 처음 환경 준비부터 config.py 설정·실행·결과 확인까지 따라 하는 사용법 |
| [BRONZE.md](BRONZE.md) | 설정·실행 방법, 출처 기록, 저장 구조, 검증 결과 |
| [BRONZE_COLUMNS.md](BRONZE_COLUMNS.md) | 현재 존재하는 모든 Bronze 컬럼의 의미·타입·예시·NULL/빈값 |
| [SILVER.md](SILVER.md) | 실제 표준화·테이블 분리·행 보존 대사·검증 결과 |
| [SILVER_CHANGES.md](SILVER_CHANGES.md) | 테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 변경 건수 |
| [silver_usage.md](silver_usage.md) | 다른 프로젝트 실행·경로 인자·규칙 JSON 사용법 |
| [SILVER_COLUMNS.md](SILVER_COLUMNS.md) | 실제 Silver 컬럼·타입·원천 매핑·NULL 수·NULL 이유 |
| [QUALITY.md](QUALITY.md) | 품질 규칙별 실측·테이블별 대사·검증 결과 |
| [QUALITY_REVIEW.md](QUALITY_REVIEW.md) | 사용자 규칙·팩트 관점 대조와 최신 재검증, 재사용 범위 |
| [QUALITY_CHANGES.md](QUALITY_CHANGES.md) / [QUALITY_COLUMNS.md](QUALITY_COLUMNS.md) | 품질 처리 건수와 추가 컬럼 사전 |
| [quality_usage.md](quality_usage.md) | 읽기 전용 확인·처리 실행·다른 프로젝트 적용 |
| [GOLD_INPUT_CONTRACT.md](GOLD_INPUT_CONTRACT.md) | 공통 clean 입력 버전·팩트 그레인·후속 Gold 검증 |
| [GOLD.md](GOLD.md) / [GOLD_COLUMNS.md](GOLD_COLUMNS.md) | Gold 실제 테이블·행 수·PK/FK·금액 대사·컬럼 사전 |
| [gold_usage.md](gold_usage.md) / [GOLD_VERIFICATION.md](GOLD_VERIFICATION.md) | 생성·확인·다른 프로젝트 적용, 최종 검증 기록 |

## 원천 및 Bronze 현황

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

## 데이터 파일과 관계를 이해하는 기준

| 파일 | 원천 행 단위 | 연결 후보 / 주의점 |
| --- | --- | --- |
| race_change_events | JSON 객체 1개 = 이벤트 1행 | 이름·기준일 등의 연결 기준은 Silver/Gold 설계에서 확정; 이름의 유일성을 가정하지 않음 |
| HR_VET_HIST | 원천 진료 기록 1행. 여러 진료명이 한 칸에 있을 수 있음 | 이름·기준일 등의 연결 기준은 Silver/Gold 설계에서 확정; 이름의 유일성을 가정하지 않음 |
| HR_WEEKLY_SNAPSHOT | 기준일별 말 정보 1행 | 이름·기준일 등의 연결 기준은 Silver/Gold 설계에서 확정; 이름의 유일성을 가정하지 않음 |
| TR_WEEKLY_SNAPSHOT | 기준일별 조교사 정보 1행 | 이름·기준일 등의 연결 기준은 Silver/Gold 설계에서 확정; 이름의 유일성을 가정하지 않음 |
| MBR_MASTER | 원천 회원 정보 1행 | 이름·기준일 등의 연결 기준은 Silver/Gold 설계에서 확정; 이름의 유일성을 가정하지 않음 |
| bet_order | 원천 전표 1행. 전표번호 유일성은 Bronze에서 강제하지 않음 | 전표번호: order_no; 회원: member_no / MBR_NO |
| bet_ticket | 원천 마권 상세 1행. 중복 포함 | order_no로 전표 연결; rc_date·rc_no·chul_no로 경주/출전마 연결 후보 |
| RC_ENTRY | 경주별 출전마 정보 1행 | RC_DATE·RC_NO·CHUL_NO 등 원천 식별값 확인 필요; PK/FK 검증은 아직 미수행 |
| RC_ODDS | 경주별 말의 배당·구간 원문 1행 | RC_DATE·RC_NO·CHUL_NO 등 원천 식별값 확인 필요; PK/FK 검증은 아직 미수행 |
| RC_RACE | 경주 기본 정보 1행 | RC_DATE·RC_NO·CHUL_NO 등 원천 식별값 확인 필요; PK/FK 검증은 아직 미수행 |
| RC_RESULT | 경주별 말의 결과 원문 1행 | RC_DATE·RC_NO·CHUL_NO 등 원천 식별값 확인 필요; PK/FK 검증은 아직 미수행 |
| RC_SALES | 경주별 매출 구분 1행. 합계 행도 포함 | RC_DATE·RC_NO·CHUL_NO 등 원천 식별값 확인 필요; PK/FK 검증은 아직 미수행 |

## 저장소 탐색

| 경로 | 역할 |
| --- | --- |
| [`../data/00_origin`](../data/00_origin/) | 팀 공용 원천; 수정·이동·삭제하지 않음 |
| [`../data/01_bronze`](../data/01_bronze/) | 원천 보존 Parquet 12개 |
| [`../src/config.py`](../src/config.py) | 파일 경로·패턴·시트·컬럼·인코딩 설정 |
| [`../src/01_bronze.py`](../src/01_bronze.py) | 변환과 출처 추가, 검증, 수집 이력 기록 |
| [`../src/01_bronze_preview.ipynb`](../src/01_bronze_preview.ipynb) | 원천/결과 경로와 head(3), 최근 실행 대사 |
| [`../tests/test_bronze.py`](../tests/test_bronze.py) | Bronze 자동 테스트 9개 |
| [`../meta/bronze_ingestion.jsonl`](../meta/bronze_ingestion.jsonl) | 실행별 수집 이력과 최초 수집 시각 재사용 근거 |
| [`../meta/mapping_rules.md`](../meta/mapping_rules.md) | 팀 공용 매핑 규칙서; Bronze에는 일시 표기 규칙만 적용 |
| `docs/` | 사람이 읽는 단계별 작업 기록; 앞으로 계속 갱신 |
| `../meta` | 기계 판독 이력·규칙·향후 데이터 사전 및 품질관리 근거 |

## 문서 갱신 기준

| 작업 | 함께 갱신할 문서 |
| --- | --- |
| 원천 추가·새 문제 확인 | AS-IS.md, DATA_GUIDE.md |
| Bronze 코드·설정·출처·검증 변경 | bronze_usage.md, BRONZE.md, BRONZE_COLUMNS.md, DATA_GUIDE.md |
| Silver 구현·변환 규칙·검증 | SILVER.md, SILVER_COLUMNS.md, SILVER_CHANGES.md, silver_usage.md, DATA_GUIDE.md 및 meta 데이터 사전 |
| 품질 관리 | 제외·유지 행 수, 사유, 근거 결정 ID와 검증 결과를 해당 단계 문서에 추가 |
| Gold 시작 | GOLD.md, GOLD_COLUMNS.md를 추가하고 DATA_GUIDE.md에서 연결 |

단계 문서에는 입력·출력, 적용 규칙, 실제 변경, 검증 결과, 해결되지 않은 문제, 변경 이력을 남깁니다.
수치에는 측정 조건을 적고, 계획·규칙서 기대값과 실측값을 구분합니다. 첨부 예시의 완료 결과는 이 프로젝트의 결과로 복사하지 않습니다.

## 문서 경로 변경 이력

| 일자 (KST) | 변경 |
| --- | --- |
| 2026-11-20 | 사용자 확인에 따라 문서 폴더를 docs로 통일. 기존 문서는 사용자가 이동했으며, 관련 안내·링크·작업 규칙을 갱신함 |

## Silver 표준화 진행 이력

| 일자 (KST) | 작업 | 범위 |
| --- | --- | --- |
| 2026-11-20 | Bronze 기반 02_normalize.py 표준화와 변경 건수·데이터 사전·검증 구현 | 사용자 확인에 따라 합계·진료명 브리지를 분리해 Silver 바로 아래 14개 파일 생성. 품질 정제·중복 제거·행 제외는 미수행 |
