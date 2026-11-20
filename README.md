# mlo-03-p2-team3

원천 데이터 → Bronze → Silver → 품질 관리 → Gold → AI Ready Data

## 디렉토리 구조

```
.
├── data/
│   ├── 00_origin/   # 원천 데이터 (읽기 전용, 수정·이동·덮어쓰기 금지)
│   ├── 01_bronze/   # 원천 → Parquet (어느 파일을 언제 가져왔는지 기록)
│   ├── 02_silver/   # 컬럼명·날짜·데이터 타입·논리값 표준화 (보존)
│   │   ├── clean/      # 품질 관리 후 유지 행 + 표시 컬럼 → Gold의 입력
│   │   └── _excluded/  # 품질 관리에서 제외한 행 (완전 중복)
│   └── 03_gold/     # 스타 스키마 (fact / dim)
├── src/             # 파이썬 코드 (단계별 처리 + 검증)
├── docs/            # AS-IS 문제 정리, 품질 관리 보고서
├── meta/            # 메타데이터 (데이터 사전, 데이터 설명서, 변경 내역)
└── AGENTS.md        # AI 에이전트·팀원 작업 규칙
```

- `main`의 `data/`에는 팀 공용 원천 파일과 폴더 구조를 공유합니다. Bronze·Silver·Gold 처리는 각자의 작업 브랜치에서 진행합니다.

## 실행

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/01_bronze.py         # 원천 → Bronze
.venv/bin/python src/01_bronze_check.py   # Bronze 검증
.venv/bin/python src/02_normalize.py      # Bronze → Silver
.venv/bin/python src/02_normalize_check.py  # Silver 검증
.venv/bin/python src/03_quality.py        # Silver 표준화 → 품질 관리 (clean/, _excluded/, 보고서)
.venv/bin/python src/03_quality_check.py  # 품질 관리 검증
.venv/bin/python src/04_modeling.py       # clean/ → Gold 스타 스키마
.venv/bin/python src/04_modeling_check.py # Gold 검증
.venv/bin/python src/make_column_docs.py  # 컬럼 사전 문서 다시 만들기
```

- 데이터 안내 (테이블별 내용·관계): `docs/DATA_GUIDE.md`
- 원천 문제 정리: `docs/AS-IS.md`
- 단계별 기록: `docs/BRONZE.md`, `docs/SILVER.md`, `docs/품질관리.md`, `docs/GOLD.md`
- 결정 로그 (품질 규칙의 근거 ID): `meta/decision_log.md`
- 컬럼 사전 (컬럼별 뜻·값·NULL): `docs/BRONZE_COLUMNS.md`, `docs/SILVER_COLUMNS.md` (`src/make_column_docs.py`로 생성)
- 메타데이터 설명: `meta/README.md`
