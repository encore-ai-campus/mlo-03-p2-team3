# Bronze 단계 기록

- **코드:** `src/01_bronze.py` (적재), `src/01_bronze_check.py` (검증)
- **입력:** `data/00_origin/` 12개 파일 (읽기만 함)
- **출력:** `data/01_bronze/*.parquet` 12개, `meta/bronze_load_log.csv`
- **컬럼별 뜻과 실제 값:** `docs/BRONZE_COLUMNS.md`

## 무엇을 했나

원천 파일을 **아무것도 바꾸지 않고** Parquet로 옮겼습니다.

- 모든 값은 문자열로 그대로 둡니다. 숫자·날짜 변환, 공백 제거, 빈칸 처리는 하지 않습니다.
  - 예: `'  M0012346 '`, `'3,000천원(개별)'`, `'-----'`도 그대로 들어 있습니다.
- CSV는 UTF-8 BOM(`utf-8-sig`)으로 읽습니다.
- JSONL은 펼치지 않고 한 줄을 `RAW_JSON` 컬럼에 원문 그대로 넣습니다. 펼치는 작업은 Silver에서 합니다.

## 붙인 메타 컬럼

| 컬럼 | 값 | 용도 |
|:--|:--|:--|
| `_SRC_SYSTEM` | bet / mbr / hms / rms / vms / mongodb | 어느 원천 시스템에서 왔나 (매핑 규칙서 3장 기준) |
| `_LOAD_FILE` | 예: `order/bet_ticket.csv` | 어느 파일에서 왔나 |
| `_LOAD_DTM` | 예: `2026-11-20 14:26:05` (KST) | 언제 가져왔나 |
| `_SRC_ROW_NO` | 1, 2, 3 … | 원천 파일 몇 번째 데이터 행인지. 규칙서에는 없지만 행 추적용으로 추가 |

## 적재 기록: `meta/bronze_load_log.csv`

"어느 파일을 언제 가져와서 저장했는지"를 남기는 파일입니다. 원천 파일 1개당 1줄입니다.

| 컬럼 | 내용 |
|:--|:--|
| `LOAD_FILE` | 원천 파일 경로 |
| `SRC_SYSTEM` | 원천 시스템 |
| `SHA256` | 원천 파일 지문(해시). 파일이 1바이트라도 바뀌면 값이 달라짐 |
| `ROW_CNT` | 적재한 행 수 |
| `LOAD_DTM` | 적재 시각 |
| `BRONZE_FILE` | 저장한 Bronze 파일 경로 |

### 다시 돌려도 같은 파일이 나오는 이유

`_LOAD_DTM`에 매번 현재 시각을 넣으면 돌릴 때마다 결과가 달라집니다. 그래서 이렇게 처리합니다.

1. 원천 파일의 SHA-256을 계산합니다.
2. 같은 파일·같은 해시가 로그에 이미 있으면, 그때 기록한 `LOAD_DTM`을 그대로 씁니다. 결과는 바이트 단위로 같습니다.
3. 원천 파일 내용이 바뀌었으면 새 시각으로 적재하고, 로그에 한 줄을 추가합니다. 이전 기록은 지우지 않습니다.

## 검증 결과 (`src/01_bronze_check.py`)

| 원천 파일 | 원천 행 | Bronze 행 | 행 수 | 값 동일 | 원천 무변경 |
|:--|--:|--:|:-:|:-:|:-:|
| order/bet_order.csv | 27,907 | 27,907 | O | O | O |
| order/bet_ticket.csv | 523,416 | 523,416 | O | O | O |
| member/MBR_MASTER.csv | 4,383 | 4,383 | O | O | O |
| horse/HR_WEEKLY_SNAPSHOT.csv | 52,642 | 52,642 | O | O | O |
| horse/TR_WEEKLY_SNAPSHOT.csv | 954 | 954 | O | O | O |
| race/RC_RACE.csv | 386 | 386 | O | O | O |
| race/RC_ENTRY.csv | 3,666 | 3,666 | O | O | O |
| race/RC_ODDS.csv | 3,666 | 3,666 | O | O | O |
| race/RC_RESULT.csv | 3,666 | 3,666 | O | O | O |
| race/RC_SALES.csv | 3,088 | 3,088 | O | O | O |
| horse/HR_VET_HIST.csv | 1,488 | 1,488 | O | O | O |
| event/race_change_events.jsonl | 149 | 149 | O | O | O |

| 점검 항목 | 확인 방법 |
|:--|:--|
| 행 수 | 원천 행을 pandas가 아닌 `csv` 모듈로 따로 세서 Bronze와 비교 |
| 값 동일 | 원천을 다시 읽어 메타 컬럼을 뺀 Bronze와 칸 단위로 비교 |
| 원천 무변경 | 로그의 SHA-256 = 지금 원천 파일의 SHA-256 |
| 메타 컬럼 | `_SRC_SYSTEM`·`_LOAD_FILE`이 맞는지, `_LOAD_DTM`이 파일당 하나인지, `_SRC_ROW_NO`가 1부터 빠짐없이 이어지는지 |
| 재실행 | 두 번 돌려 Bronze 파일과 로그의 해시가 같은지 확인 (동일) |
