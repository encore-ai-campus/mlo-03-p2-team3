# Bronze 원천 적재 작업 기록

## 작업 내용

- `src/load_bronze.py`를 추가해 `data/00_origin/` 아래 CSV와 JSONL을 재귀적으로 읽고 `data/01_bronze/`에 Parquet로 적재하도록 구성했습니다.
- 원천 파일은 읽기만 하며 수정하거나 이동하지 않습니다.
- 정렬된 상대 경로 순서로 처리하고, 원천 상대 경로를 출력 경로에 반영합니다. 예를 들어 `horse/HR_VET_HIST.csv`는 `horse/HR_VET_HIST.parquet`로 저장됩니다.
- CSV는 모든 컬럼을 문자열로 읽어 선행 0, 날짜 형식, 빈 문자열을 원형에 가깝게 유지합니다. JSONL도 필드 값을 문자열로 변환하며, 배열과 객체 값은 compact JSON 문자열로 보존합니다.
- `_SRC_FILE`에는 `00_origin/` 기준 상대 경로를, `_LOAD_DTM`에는 최초 적재 시각을 기록합니다. 같은 파일 내용으로 재실행하면 기존 시각을 유지하고, 파일 내용이 달라지면 새 적재 시각을 기록합니다.
- `_load_manifest.json`에는 원천 SHA-256, 출력 경로, 행 수, 적재 시각을 기록해 원천과 Bronze 결과를 추적합니다.
- Parquet 파일과 매니페스트는 임시 파일에 쓴 뒤 교체해 중간 실패 시 기존 결과가 부분 파일로 바뀌지 않도록 했습니다.
- 저장한 Parquet의 행 수가 원천 행 수와 같은지 확인합니다. Parquet 문자열 타입은 Arrow `string`과 `large_string`을 모두 허용합니다. 출력 경로가 겹치는 원천 파일이 있으면 적재 전에 중단합니다.
- 원천 파일의 Bronze 적재가 완료되면 `meta/bronze_change_log.csv`에 입출력 경로, 행 수, 컬럼 목록 및 추적 컬럼 추가 내역을 기록합니다.

## 실행 방법

프로젝트 루트에서 실행합니다.

```powershell
python -m pip install pandas pyarrow
python src/load_bronze.py
```

CSV 및 JSONL 파일이 모두 정상적으로 읽혀야 하며, `_SRC_FILE` 또는 `_LOAD_DTM`이라는 원천 컬럼이 있으면 충돌 방지를 위해 해당 파일 적재를 중단합니다. 입력 파일별 출력 행 수는 로그와 매니페스트에 기록됩니다.
