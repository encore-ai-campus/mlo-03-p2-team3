# mlo-03-p2-team3

원천 데이터 → Bronze → Silver → 품질 관리 → Gold → AI Ready Data

## 디렉토리 구조

```
.
├── data/
│   ├── 00_origin/   # 원천 데이터 (읽기 전용, 수정·이동·덮어쓰기 금지)
│   ├── 01_bronze/   # 원천 → Parquet (어느 파일을 언제 가져왔는지 기록)
│   ├── 02_silver/   # 컬럼명·날짜·데이터 타입·논리값 표준화
│   └── 03_gold/     # 스타 스키마 (fact / dim)
├── src/             # 파이썬 코드 (단계별 처리 + 검증)
├── docs/             # 단계별 작업 기록·컬럼 사전·데이터 안내
├── meta/            # 메타데이터 (데이터 사전, 데이터 설명서, 변경 내역)
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

Gold 작업 시 `docs/GOLD.md`, `docs/GOLD_COLUMNS.md`를 추가합니다.

## Silver 표준화

Bronze만 읽어 표준화하며, 합계·진료명 분리를 포함한 Parquet 14개를 `data/02_silver/` 바로 아래에 저장합니다. 후속 품질 관리는 별도 코드로 수행하며 표준화 결과를 보존합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --check-reference
.\.venv\Scripts\python.exe src/02_normalize_check.py --check-reference
```

## Silver 품질 관리

D-001~D-012에 따른 `clean/` 14개와 `_excluded/BET_TICKET.parquet`이 생성되어 있습니다. 기존 결과를 확인할 때는 아래 읽기 전용 검증만 실행합니다.

```powershell
.\.venv\Scripts\python.exe src/02_quality_check.py
```

[품질 확인 기록](docs/QUALITY_REVIEW.md) · [규칙·실측·대사](docs/QUALITY.md) · [다른 프로젝트 적용 사용법](docs/quality_usage.md) · [Gold 입력 계약](docs/GOLD_INPUT_CONTRACT.md)

처리 코드는 `src/02_quality.py`, 읽기 전용 검증 코드는 `src/02_quality_check.py`입니다.

## Gold 스타 스키마

`data/03_gold/`에 50대 단승 구매 선택 묶음 팩트 41,141행과 회원·말·경주·날짜·채널 차원5개를 생성했습니다. 분석 적격39,284행, 확인취소894묶음이며 **주 분석은 `analysis_eligible=1`만 사용**합니다. 분석 제외1,857행은 팩트와 감사 테이블에 보존합니다.

```powershell
.\.venv\Scripts\python.exe src/03_gold_check.py
```

[Gold 결과](docs/GOLD.md) · [컬럼 사전](docs/GOLD_COLUMNS.md) · [실행·재사용](docs/gold_usage.md) · [검증 기록](docs/GOLD_VERIFICATION.md)

공통 차원 키 계약은 현재 브랜치의 제안이며 팀 합의 완료를 의미하지 않습니다. SQL 예제는 `meta/gold_schema.sql`에 제공하며 DB 적재는 수행하지 않았습니다.

Gold 데이터 파일명은 `DIM_MEMBER.parquet`, `FCT_BET_SELECTION_CANCEL_50S.parquet` 등 대문자로 통일합니다. 분석 보조 요약은 `meta/WIN_RATE_CANCEL_SUMMARY.csv`에 별도로 두며 스타 스키마 테이블에 포함하지 않습니다. `meta/audit/`는 입력 처분·취소 연결·분석 부적격 근거를 보존하는 감사 기록입니다. `data/03_gold/`에는 팩트1개·차원5개만 저장합니다.
