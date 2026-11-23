# Gold 말 진료 스타 스키마

입력은 `develop`의 `data/02_silver/clean/`입니다(D-012). 진료 팩트, 브리지, 차원은 `data/03_gold/horse_medical/`에 생성합니다. 날짜·말·조교사 차원은 네 스키마가 모인 뒤 [공통 차원 통합 안건](COMMON_DIMENSIONS.md)에 따라 비교합니다(D-010).

## 설계

| 출력 테이블 | 행 단위 및 키 | clean 입력 |
|---|---|---|
| `FCT_HORSE_MEDICAL` | 진료 기록 1건. PK는 `VET_SEQ`, 측정값 `VET_CNT`는 행마다 1 | `HR_VET_HIST` |
| `BRIDGE_HR_VET_TYPE` | 진료 기록과 진료 유형 연결 1건. 복합 PK는 `VET_SEQ`와 `VET_TYPE_KEY` | `HR_VET_TYPE_BRIDGE` |
| `DIM_DATE` | 진료일과 보고일 전체 범위의 날짜 1일. PK는 `DATE_KEY`(YYYYMMDD) | `HR_VET_HIST`, `RC_RACE` |
| `DIM_HORSE` | 마명별 SCD2 버전 1건. PK는 `HORSE_KEY` | `HR_WEEKLY_SNAPSHOT` |
| `DIM_TRAINER` | 조교사별 최신 스냅샷 1건. PK는 `TRAINER_KEY` | `TR_WEEKLY_SNAPSHOT` |
| `DIM_AGE_GROUP` | 2~3세, 4~5세, 6~7세, 8세 이상, 미확인. PK는 `AGE_GROUP_KEY` | 코드에 정의한 구간 |
| `DIM_VET_TYPE` | 표준 진료 유형 1개. PK는 `VET_TYPE_KEY` | `HR_VET_TYPE_BRIDGE` |

```mermaid
erDiagram
    DIM_DATE ||--o{ FCT_HORSE_MEDICAL : VET_DT_KEY
    DIM_DATE ||--o{ FCT_HORSE_MEDICAL : REPORT_DT_KEY
    DIM_HORSE ||--o{ FCT_HORSE_MEDICAL : HORSE_KEY
    DIM_TRAINER ||--o{ FCT_HORSE_MEDICAL : TRAINER_KEY
    DIM_AGE_GROUP ||--o{ FCT_HORSE_MEDICAL : AGE_GROUP_KEY
    FCT_HORSE_MEDICAL ||--|{ BRIDGE_HR_VET_TYPE : VET_SEQ
    DIM_VET_TYPE ||--o{ BRIDGE_HR_VET_TYPE : VET_TYPE_KEY
```

- 말은 마명과 진료일로 연결합니다. 스냅샷 다음 날부터 해당 버전이 유효하며, 진료일보다 앞선 스냅샷이 없으면 미확인 말 키 `0`으로 연결합니다(D-007). 나이대는 같은 말 버전의 `HR_AGE`를 사용하며 미확인 키는 `0`입니다.
- 조교사는 진료 기록의 `TR_GRP_NO`로 연결합니다.
- 전체 진료 건수는 팩트의 `SUM(VET_CNT)`로 계산합니다. 한 진료가 여러 유형에 속할 수 있으므로 유형을 넘나드는 건수는 `VET_SEQ`를 중복 제거해 집계합니다.

## 생성 및 검증

저장소 루트에서 실행합니다.

```powershell
python -X utf8 src/horse_medical/04_gold_horse_medical.py
python -X utf8 src/horse_medical/04_gold_horse_medical.py --check
```

`--check`는 clean으로부터 계산한 결과와 저장된 Gold 테이블 및 매니페스트를 대조합니다. [Gold 매니페스트](../../data/03_gold/horse_medical/_manifest.json)에 입력 `CLEAN_VERSION`, 테이블별 행 수, 제외 건수와 키 검증 결과를 기록합니다.

| 대사·검증 항목 | 결과 |
|---|---:|
| clean 진료 행 수 = Gold 팩트 행 수 = `SUM(VET_CNT)` | 1,488 |
| clean 유형 연결 수 = Gold 브리지 행 수 | 1,662 |
| 이전 말 스냅샷 없는 clean 기록 = Gold 미확인 말 기록 | 71 |
| Gold 입력 제외 행 | 0 |
| PK 중복 및 미해결 FK | 각각 0 |
| 2회 생성한 Parquet 7개와 매니페스트의 SHA-256 | 8개 모두 일치 |
