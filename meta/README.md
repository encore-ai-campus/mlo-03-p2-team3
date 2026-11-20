# 공용 Bronze·Silver 메타데이터

공통 적재·표준화 코드는 팀 브랜치 `feat/fct-race-entry`의 커밋 `6f83e57`을 기준으로 사용한다. 진료 작업 브랜치에서도 같은 원천 12개와 표준 규칙을 적용한다.

| 파일 | 만드는 코드 | 내용 |
|:--|:--|:--|
| `mapping_rules.md` | (팀 공용 문서) | 원천 → 표준 매핑 규칙서. Silver 규칙의 근거 |
| `bronze_load_log.csv` | `src/01_bronze.py` | 원천 파일별 SHA-256, 행 수, 적재 시각(`_LOAD_DTM`), Bronze 파일 경로 |
| `data_dictionary.csv` | `src/02_normalize.py` | 저장소 기준 원천·Bronze·Silver 파일 경로, 표준 컬럼·타입, 원천 컬럼, 적용 규칙. 제외 컬럼은 `COL_NM=(제외)`와 사유 |
| `silver_value_map.csv` | `src/02_normalize.py` | 코드 컬럼의 원천값 → 표준코드 변환 건수 |
| `silver_issue_log.csv` | `src/02_normalize.py` | 원천값이 있었는데 Silver에서 NULL이 된 칸. 행 번호(`SRC_ROW_NO`), 원천값, 사유 |
| `silver_column_profile.csv` | `src/02_normalize.py` | Silver 컬럼별 행 수, NULL 수, TRIM 수, 변환 실패·코드표 밖·규칙상 NULL 건수 |

## 이슈 코드 (`silver_issue_log.csv`)

| ISSUE_CD | 뜻 |
|:--|:--|
| `PARSE_FAIL` | 정해진 형식으로 변환되지 않음 |
| `OUT_OF_CODE` | 코드표에 없는 값 |
| `RULE_NULL` | 규칙에 따라 NULL로 둠 (예: `외부마`, `-----`, `경주제외`). 실패가 아님 |

## 추적 방법

모든 Bronze·Silver 테이블에는 `_SRC_ROW_NO`(원천 데이터 행 번호, 1부터)가 있습니다. Silver 값이 의심되면 같은 `_SRC_ROW_NO`의 Bronze 행에서 원천값을 확인합니다.

## 검증 규칙과 결정 ID

| 결정 ID | 검증 규칙 | 근거 |
|---|---|---|
| `BR-01` | 원천과 Bronze의 행 수와 원천 컬럼의 값을 대조하고 원천 파일 SHA-256을 확인 | 저장소 단계별 대사 규칙 및 팀 매핑 규칙서 1장 |
| `SL-01` | Silver의 행 보존, 매출 합계 분리, 진료명 브리지, 표준 테이블별 기대 행 수를 대조 | 팀 매핑 규칙서 3장, 7장, 11장 |
| `SL-02` | `PARSE_FAIL`과 `OUT_OF_CODE`는 0건이어야 하며, 규칙상 NULL이 된 원천값은 `RULE_NULL`로 기록 | 팀 매핑 규칙서 1장, 4~7장, 11장 |
| `SL-03` | 매핑과 제외 규칙을 데이터 사전에 기록하고 검증 대상 원천 컬럼에 누락이 없는지 확인 | 팀 매핑 규칙서 9장, 10장 및 저장소 변경 내역 규칙 |
