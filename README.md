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

## 진료 이력 데이터

원천은 `data/00_origin/horse/HR_VET_HIST.csv`이며, 진료 이력 1,488행과 6개 컬럼으로 구성됩니다.

### 원천 데이터 프로파일링

| 확인 항목 | 결과 |
|---|---|
| 날짜 형식 | 진료일은 `YYYY.MM.DD`, 보고일은 `YYYYMMDD` |
| 조 번호 | 앞자리에 `0`이 있는 값이 667행에 있어 문자열로 보존 |
| 복수 진료명 | 176행에 쉼표로 구분된 진료명이 포함됨 |
| 결측·완전 중복·날짜 파싱 실패 | 각각 0건 |

### Bronze·Silver 검증 결과

| 단계 | 산출물 | 검증 결과 |
|---|---|---|
| Bronze | `HR_VET_HIST_RAW.parquet`, `HR_VET_HIST_LOAD.json` | 원천과 동일한 1,488행 × 6열. 컬럼명·순서·셀 값이 일치하며 적재 기록에 원천 경로와 KST 적재 시각을 저장 |
| Silver 진료 이력 | `HR_VET_HIST.parquet` | 1,488행 × 7열. 컬럼명·날짜·타입·결측값을 표준화하고 레코드별 `VET_SEQ`를 부여 |
| Silver 진료 유형 브리지 | `HR_VET_TYPE_BRIDGE.parquet` | 1,664행 × 2열. 진료명 항목을 개별 행으로 나눠 `VET_SEQ`로 연결 |

[AS-IS 상세 프로파일링](docs/HR_VET_HIST_AS_IS.md) · [파일별 입출력과 컬럼 매핑](meta/HR_VET_HIST_DATA_DICTIONARY.md)
