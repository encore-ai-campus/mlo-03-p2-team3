# 데이터 변경 로그

## 기록 위치와 시점

Bronze 또는 Silver Parquet 파일을 성공적으로 저장하고 행 수 확인까지 마치면 단계별 CSV에 기록을 추가합니다. Bronze 실행은 `meta/bronze_change_log.csv`에 원천 파일별 한 행을, Silver 실행은 `meta/silver_change_log.csv`에 생성 테이블별 한 행을 기록합니다. 재실행 기록은 각 파일의 기존 이력 뒤에 누적됩니다.

기존 통합 `meta/data_change_log.csv`의 이력은 단계별 CSV로 분리했습니다. 통합 파일은 이전 기록 보존용으로 남아 있으며 이후 실행에서는 갱신하지 않습니다.

CSV 기록 코드는 별도 공통 모듈 없이 `src/load_bronze.py`와 `src/load_silver.py` 안에 각각 포함되어 있습니다.

CSV는 Excel에서 바로 열 수 있도록 UTF-8-SIG로 저장합니다. 기록 파일은 임시 파일에 전체 내용을 쓴 뒤 교체합니다.

## 컬럼

| 컬럼 | 내용 |
|---|---|
| `RUN_DTM_KST` | 로그 기록 시각과 시간대 오프셋 |
| `STAGE` | `BRONZE` 또는 `SILVER` |
| `SRC_FILE` | 원천 파일 경로 목록(JSON 배열) |
| `INPUT_FILE` / `OUTPUT_FILE` | 입력·출력 파일 경로 |
| `INPUT_ROWS` / `OUTPUT_ROWS` | 입력·출력 행 수 |
| `INPUT_COLUMNS` / `OUTPUT_COLUMNS` | 입력·출력 컬럼 목록(JSON 배열) |
| `ADDED_COLUMNS` / `REMOVED_COLUMNS` | 입력 대비 추가·제외된 컬럼(JSON 배열) |
| `CHANGE_DETAIL` | 적용한 적재·표준화 규칙 또는 분리 작업 설명 |

이 로그는 행 단위 데이터를 복제하지 않고, 파일·테이블별 변환과 스키마 변경 및 행 수를 기록합니다. 실제 데이터 값은 Bronze/Silver Parquet에서 확인합니다.
