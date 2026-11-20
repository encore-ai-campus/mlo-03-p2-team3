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
```

- 데이터 안내 (테이블별 내용·관계): `docs/DATA_GUIDE.md`
- 원천 문제 정리: `docs/AS-IS.md`
- 단계별 기록: `docs/BRONZE.md`, `docs/SILVER.md`
- 컬럼 사전 (컬럼별 뜻·값·NULL): `docs/BRONZE_COLUMNS.md`, `docs/SILVER_COLUMNS.md` (`src/make_column_docs.py`로 생성)
- 메타데이터 설명: `meta/README.md`
