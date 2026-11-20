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

Bronze만 읽어 표준화하며, 합계·진료명 분리를 포함한 Parquet 14개를 `data/02_silver/` 바로 아래에 저장합니다. 품질 정제는 다음 단계입니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --check-reference
.\.venv\Scripts\python.exe src/02_normalize_check.py --check-reference
```
