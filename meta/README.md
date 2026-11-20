# meta/ 데이터 설명서

| 파일 | 만드는 코드 | 내용 |
|:--|:--|:--|
| `mapping_rules.md` | (팀 공용 문서) | 원천 → 표준 매핑 규칙서. Silver 규칙의 근거 |
| `bronze_load_log.csv` | `src/01_bronze.py` | 원천 파일별 SHA-256, 행 수, 적재 시각(`_LOAD_DTM`), Bronze 파일 경로 |
| `data_dictionary.csv` | `src/02_normalize.py` | Silver 테이블·컬럼, 타입, 원천 컬럼, 적용 규칙. 제외한 원천 컬럼은 `COL_NM=(제외)`와 사유 |
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
