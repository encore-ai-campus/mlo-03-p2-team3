# mlo-03-p2-team3

원천 데이터 → Bronze → Silver 표준화 → 품질 관리 → **Gold 스타 스키마 완료** → AI Ready Data

`FCT_BET_CANCEL` 브랜치에서는 **원구매 당시 만 50~59세 회원이 선택한 말의 구매 전 최근 1년 승률과 단승 고객 취소율의 관계**를 분석할 수 있도록 팩트 1개와 차원 5개를 구현했습니다.

> 기록 기준: 2026-11-20 (KST). 스타 스키마 파일 생성·검증까지 완료했으며, DB 적재·팀 전체 공통 차원 통합·후속 AI 활용은 아직 수행하지 않았습니다.

## 단계별 완료 현황

| 단계 | 상태 | 주요 결과 |
| --- | --- | --- |
| 원천 / AS-IS | 조사·기록 완료 | 원천 12개 파일, 625,411행; 범위·품질 징후·출처 기록 |
| Bronze | 변환·검증 완료 | 원천 보존 Parquet 12개, 출처·수집 시각·수집 이력 기록 |
| Silver 표준화 | 변환·검증 완료 | 합계·진료명 브리지를 포함한 표준 테이블 14개; 기본 입력 행 보존 |
| 품질 관리 | 처리·검증 완료 | clean 14개, 완전 중복 1,052행 별도 보관, 진료명 의미 병합 감소 2행 별도 대사 |
| Gold | 스타 스키마 생성·검증 완료 | 팩트 41,141행 + 차원 5개; PK/FK·집계 대사 43개 검사 통과 |

이전 단계 데이터는 수정하지 않고, 제외 행·사유·원천 계보를 보존합니다. 처리 순서·정렬·키 생성을 고정하여 같은 입력으로 재실행하면 같은 결과를 얻도록 구현했습니다.

## 디렉토리 구조

```
.
├── data/
│   ├── 00_origin/   # 원천 데이터 (읽기 전용, 수정·이동·덮어쓰기 금지)
│   ├── 01_bronze/   # 원천 → Parquet (어느 파일을 언제 가져왔는지 기록)
│   ├── 02_silver/   # 표준화 Parquet 14개
│   │   ├── clean/      # 품질 처리 후 유지 데이터 14개; Gold 입력
│   │   └── _excluded/  # 완전 중복 마권 1,052행
│   └── 03_gold/     # 대문자 파일명의 팩트 1개·차원 5개만 저장
├── src/             # 파이썬 코드 (단계별 처리 + 검증)
├── docs/             # 단계별 작업 기록·컬럼 사전·데이터 안내
├── meta/            # 사전·결정·변경 로그·manifest·검증 JSON·SQL
│   ├── audit/       # Gold 입력 처분·취소 연결·분석 부적격 감사 기록
│   └── WIN_RATE_CANCEL_SUMMARY.csv  # 승률구간별 분석 보조 요약
└── AGENTS.md        # AI 에이전트·팀원 작업 규칙
```

- `main`의 `data/`에는 팀 공용 원천 파일과 폴더 구조를 공유합니다. Bronze·Silver·Gold 처리는 각자의 작업 브랜치에서 진행합니다.

## Bronze 파이프라인

설정은 `src/config.py`, 실행 코드는 `src/01_bronze.py`, 미리보기는 `src/01_bronze_preview.ipynb`입니다.
처음 설정하고 실행하려면 [Bronze 사용법](docs/bronze_usage.md)을 따라 하세요. 실제 처리·검증 결과는 [Bronze 작업 기록](docs/BRONZE.md)에 정리합니다.

## 작업 문서

| 문서 | 내용 |
| --- | --- |
| [데이터 안내](docs/DATA_GUIDE.md) | 진행 상태·파일 목록·문서 탐색 |
| [AS-IS](docs/AS-IS.md) | 원천 구조·실측 문제와 후속 검증 |
| [Bronze 사용법](docs/bronze_usage.md) | 환경 준비·config.py 설정·변환 실행·결과 확인 |
| [Bronze](docs/BRONZE.md) | 구현·실행·출처·검증·변경 이력 |
| [Bronze 컬럼](docs/BRONZE_COLUMNS.md) | 실제 컬럼 의미·타입·예시·빈값 |
| [Silver](docs/SILVER.md) | 실제 표준화·14개 테이블·보존 대사·검증 |
| [Silver 컬럼](docs/SILVER_COLUMNS.md) | 실제 컬럼·타입·NULL 이유 |
| [Silver 변경 건수](docs/SILVER_CHANGES.md) | 테이블·원천컬럼·표준컬럼·변경값과 건수 |
| [Silver 사용법](docs/silver_usage.md) | 실행·다른 프로젝트 적용·JSON 규칙 설정 |
| [품질 관리](docs/QUALITY.md) / [완료 확인](docs/QUALITY_REVIEW.md) | 규칙·실측·행 수 대사·최종 검증 |
| [품질 컬럼](docs/QUALITY_COLUMNS.md) / [변경 건수](docs/QUALITY_CHANGES.md) | 플래그·보정·제외·의미 병합 기록 |
| [품질 사용법](docs/quality_usage.md) | 실행·읽기 전용 확인·다른 프로젝트 적용 |
| [Gold 입력 계약](docs/GOLD_INPUT_CONTRACT.md) / [설계](docs/GOLD_DESIGN.md) | 공용 clean 입력·팩트 그레인·키·집계 규칙 |
| [Gold 결과](docs/GOLD.md) / [컬럼](docs/GOLD_COLUMNS.md) | 실제 테이블·행 수·PK/FK·집계 대사 |
| [Gold 사용법](docs/gold_usage.md) / [검증 기록](docs/GOLD_VERIFICATION.md) | 생성·확인·재사용·최종 검증 |

## Silver 표준화

Bronze만 읽어 표준화하며, 합계·진료명 분리를 포함한 Parquet 14개를 `data/02_silver/` 바로 아래에 저장합니다. 후속 품질 관리는 별도 코드로 수행하며 표준화 결과를 보존합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --check-reference
.\.venv\Scripts\python.exe src/02_normalize_check.py --check-reference
```

위 명령은 표준화 최초 실행 단계용입니다. 품질 폴더가 생성된 현재 결과를 확인할 때는 아래 품질·Gold 전용 검증기를 사용합니다. 표준화 검증기에는 하위 폴더 금지 조건이 있습니다.

## Silver 품질 관리

D-001~D-012에 따른 `clean/` 14개와 `_excluded/BET_TICKET.parquet`이 생성되어 있습니다. 기존 결과를 확인할 때는 아래 읽기 전용 검증만 실행합니다.

| 규칙 | 실제 처리 |
| --- | --- |
| D-002 완전 중복 | 최소 원천 행 번호를 유지하고 1,052행 별도 제외 |
| D-003 0원 마권 | 3,632행 유지·표시; 업무 집계 분자·분모 모두 제외, 오류 집계 포함 |
| D-004 늦은 취소 | 1,000장 / 고유 546전표 표시·유지; 취소 분석 포함 |
| D-005 빈 마명 | 출전표 유일 연결로 1,560행 보정, 원래 값·근거 보존 |
| D-006 전표 불일치 / 원전표 없는 취소 | 93 / 644전표 표시만 하고 원래 수치·연결값 보존 |
| D-007 진료 조 불일치 / 이전 스냅샷 미확인 | 11 / 71건 유지, 관련 분석에 확인 필요 표시 |
| D-011 진료명 의미 병합 | 2진료의 일·열사병을 각각 한 번 집계; 브리지 1,664 → 1,662행 |

품질 건수는 완전 중복 제거 후 기준입니다. 일반 테이블은 입력 = 유지 + 제외로, 진료명 브리지의 의미 병합 감소는 별도로 대사합니다.

```powershell
.\.venv\Scripts\python.exe src/02_quality_check.py
```

[품질 확인 기록](docs/QUALITY_REVIEW.md) · [규칙·실측·대사](docs/QUALITY.md) · [다른 프로젝트 적용 사용법](docs/quality_usage.md) · [Gold 입력 계약](docs/GOLD_INPUT_CONTRACT.md)

처리 코드는 `src/02_quality.py`, 읽기 전용 검증 코드는 `src/02_quality_check.py`입니다.

## Gold 스타 스키마

**팩트 한 행 = 원구매 전표 × 경주일 × 경주번호 × 단승(WIN) × 선택 출주번호의 구매 선택 묶음**입니다. 같은 선택의 여러 상세를 합치며 취소 전표를 별도 분모 행으로 추가하지 않습니다.

| 파일 (`data/03_gold/`) | 행 수 | PK | 역할 |
| --- | --- | --- | --- |
| `FCT_BET_SELECTION_CANCEL_50S.parquet` | 41,141 | fact_id | 구매금액·구좌·상세 수, 구매 전 승률, 확인취소·분석 적격 여부 |
| `DIM_MEMBER.parquet` | 4,384 | member_key | 회원번호·생일·가입일 |
| `DIM_HORSE.parquet` | 833 | horse_key | 내부 말 식별·마명·생일·부마·모마 |
| `DIM_RACE.parquet` | 387 | race_id | 경마장·경주일·경주번호·출발시각·거리·등급 |
| `DIM_DATE.parquet` | 180 | date_key | 구매일·취소일·경주일·스냅샷일의 역할별 날짜 차원 |
| `DIM_CHANNEL.parquet` | 32 | channel_key | 발매 채널·장외지점 |

각 차원의 행 수에는 미상 행 1개가 포함됩니다. 날짜 미상 키는 0, 나머지 미상 키는 `UNKNOWN`입니다. 팩트는 각 차원의 PK를 FK로 참조하며, 모든 테이블의 PK 중복과 팩트 FK 누락은 0건입니다.

| 분석 지표 | 실제 결과 |
| --- | --- |
| 전체 / 분석 적격 / 분석 부적격 팩트 | 41,141 / 39,284 / 1,857행 |
| 적격 중 확인취소 구매 묶음 | 894개 |
| 적격 원구매금액 / 확인취소금액 | 230,209,200원 / 3,765,000원 |
| 적격 집계에 포함된 늦은 취소 | 상세 20행; 고유 전표 수나 구매 묶음 수와 다른 단위 |

**주 분석은 반드시 `analysis_eligible=1`을 적용합니다.** 나이는 원구매일 기준 만 나이이며, 승률은 구매 KST 날짜보다 엄격히 이전인 최신 스냅샷에서 계산합니다. 출전 0회는 0%와 구분합니다. 늦은 취소는 포함하되, 불명확한 연결·초과 취소는 취소 없음으로 바꾸지 않고 NULL 라벨과 분석 제외 사유를 유지합니다.

| 보조 산출물 | 위치·용도 |
| --- | --- |
| 입력 마권 전수 처분 | `meta/audit/TICKET_DISPOSITION.parquet`; 522,364행의 포함·범위 제외 사유와 계보 |
| 단승 취소 연결 감사 | `meta/audit/CANCEL_LINK_AUDIT.parquet`; 5,121행의 연결·시각·금액 검증 |
| 분석 부적격 근거 | `meta/audit/FACT_ANALYSIS_EXCLUSIONS.parquet`; 1,857행의 분석 제외 사유 |
| 승률구간 요약 | `meta/WIN_RATE_CANCEL_SUMMARY.csv`; 기본·최근출전 10회 이상, 각 5구간으로 총 10행 |

보조 요약과 감사 파일은 스타 스키마 테이블에 포함하지 않습니다. 처리 엔진은 `src/gold.py`·`src/gold_pipeline.py`, 생성 명령은 `src/03_gold.py`, 읽기 전용 확인은 `src/03_gold_check.py`입니다.

```powershell
.\.venv\Scripts\python.exe src/03_gold_check.py
```

[Gold 결과](docs/GOLD.md) · [컬럼 사전](docs/GOLD_COLUMNS.md) · [실행·재사용](docs/gold_usage.md) · [검증 기록](docs/GOLD_VERIFICATION.md)

공통 차원 키 계약은 현재 브랜치의 제안이며 팀 합의 완료를 의미하지 않습니다. SQL 예제는 `meta/gold_schema.sql`에 제공하며 DB 적재는 수행하지 않았습니다.

Gold 데이터 파일명은 `DIM_MEMBER.parquet`, `FCT_BET_SELECTION_CANCEL_50S.parquet` 등 대문자로 통일합니다. 분석 보조 요약은 `meta/WIN_RATE_CANCEL_SUMMARY.csv`에 별도로 두며 스타 스키마 테이블에 포함하지 않습니다. `meta/audit/`는 입력 처분·취소 연결·분석 부적격 근거를 보존하는 감사 기록입니다. `data/03_gold/`에는 팩트1개·차원5개만 저장합니다.

## 실행 환경·검증

Python 3.11 이상과 `requirements.txt`의 패키지를 사용합니다. 환경 준비·최초 생성·다른 프로젝트 경로 지정 방법은 단계별 사용법을 참고하세요. 산출물이 이미 있으면 위의 읽기 전용 확인 명령을 사용합니다. 새 입력·규칙에는 별도 버전 경로를 지정하며 기존 결과와 다른 데이터는 덮어쓰지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

최종 검증 기록 기준 자동 테스트 39개와 Gold 검사 43개가 통과했습니다. Gold 검사에는 PK/FK, 입력 마권 전수 처분, 구매 상세·금액·구좌 집계, 취소 연결 및 승률구간 요약 대사가 포함됩니다. 읽기 전용 검증은 저장 파일의 값·스키마·해시와 재계산 결과를 비교합니다.

## 자료 범위와 해석

경주 전체 매출은 `RC_SALES`, 발매 거래의 일부 범위에 대한 상세 분석은 `BET_ORDER`·`BET_TICKET`을 사용합니다. 두 자료의 금액 합계를 동일한 모집단의 매출로 간주하지 않습니다. 발매·취소 자료는 공개 거래 데이터를 마권 발매 시나리오에 맞춰 재구성했습니다. 출처: Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository, CC BY 4.0.

회원 생일 생성값·소매 재매핑 거래를 포함한 시뮬레이션 분석이므로 실제 마사회 고객 행동이나 인과효과로 일반화하지 않습니다. 같은 회원·말·경주의 반복 구매를 독립표본으로 가정하지 않습니다. 말 키는 공식 마번이 아닌 내부 식별자입니다. 팀 공통 차원 통합 시 자연키로 매핑하고 팩트 FK를 재연결한 뒤 행 수·금액·참조 무결성을 다시 확인해야 합니다.
