# Bronze 단계 작업 기록

[데이터 안내](DATA_GUIDE.md) · [원천 현황](AS-IS.md) · [Bronze](BRONZE.md) · [Bronze 컬럼](BRONZE_COLUMNS.md) · [Silver](SILVER.md) · [Silver 컬럼](SILVER_COLUMNS.md)

> 기록 기준: 2026-11-20 (KST). 완료·미수행·계획을 구분합니다.

처음 설정하고 실행하는 순서는 [Bronze 사용법](bronze_usage.md)을 참고하세요. 이 문서는 실제 수행한 작업과 검증 결과를 기록합니다.

## 처리 개요

| 항목 | 현재 결과 |
| --- | --- |
| 상태 | 구현·산출물 생성·검증 완료 |
| 코드 | [01_bronze.py](../src/01_bronze.py), [config.py](../src/config.py) |
| 입력 | data/00_origin/의 CSV 11개와 JSONL 1개; 읽기 전용 |
| 출력 | data/01_bronze/ 아래 동일 상대 경로의 Parquet 12개, 총 625,411행 |
| 보존 | 기존 컬럼명·순서·값·공백·빈 문자열·날짜 표현·중복·행 순서 |
| 추가 컬럼 | source_file(파일명.확장자), ingested_at(최초 성공 수집 시각, KST) |
| 표준화 | 미적용; 매핑 규칙서의 일시 표기만 수집 시각에 참고 |
| 상세 컬럼 | [BRONZE_COLUMNS.md](BRONZE_COLUMNS.md) |

## 파일별 결과

| 원천 상대 경로 | 출력 경로 | 입력 = 출력 행 수 | 본문 ingested_at (KST) | 원천 값 보존 |
| --- | --- | --- | --- | --- |
| `event/race_change_events.jsonl` | `../data/01_bronze/event/race_change_events.parquet` | 149 | 2026-11-20 14:40:35 | 일치 |
| `horse/HR_VET_HIST.csv` | `../data/01_bronze/horse/HR_VET_HIST.parquet` | 1,488 | 2026-11-20 14:40:35 | 일치 |
| `horse/HR_WEEKLY_SNAPSHOT.csv` | `../data/01_bronze/horse/HR_WEEKLY_SNAPSHOT.parquet` | 52,642 | 2026-11-20 14:40:35 | 일치 |
| `horse/TR_WEEKLY_SNAPSHOT.csv` | `../data/01_bronze/horse/TR_WEEKLY_SNAPSHOT.parquet` | 954 | 2026-11-20 14:40:35 | 일치 |
| `member/MBR_MASTER.csv` | `../data/01_bronze/member/MBR_MASTER.parquet` | 4,383 | 2026-11-20 14:40:35 | 일치 |
| `order/bet_order.csv` | `../data/01_bronze/order/bet_order.parquet` | 27,907 | 2026-11-20 14:40:35 | 일치 |
| `order/bet_ticket.csv` | `../data/01_bronze/order/bet_ticket.parquet` | 523,416 | 2026-11-20 14:40:35 | 일치 |
| `race/RC_ENTRY.csv` | `../data/01_bronze/race/RC_ENTRY.parquet` | 3,666 | 2026-11-20 14:40:37 | 일치 |
| `race/RC_ODDS.csv` | `../data/01_bronze/race/RC_ODDS.parquet` | 3,666 | 2026-11-20 14:40:37 | 일치 |
| `race/RC_RACE.csv` | `../data/01_bronze/race/RC_RACE.parquet` | 386 | 2026-11-20 14:40:37 | 일치 |
| `race/RC_RESULT.csv` | `../data/01_bronze/race/RC_RESULT.parquet` | 3,666 | 2026-11-20 14:40:37 | 일치 |
| `race/RC_SALES.csv` | `../data/01_bronze/race/RC_SALES.parquet` | 3,088 | 2026-11-20 14:40:37 | 일치 |

## 검증 결과

| 검증 | 방법 | 결과 |
| --- | --- | --- |
| 파일별 행 수 대사 | 원천 리더 결과와 Parquet 행 수 비교 | 12/12 일치, 총 625,411행 |
| 기존 컬럼·값 보존 | Parquet에서 원천 컬럼만 선택하여 원천 Arrow 테이블과 전체 비교 | 12/12 일치 |
| 출처 컬럼 값 | 모든 행의 파일명·최초 수집 시각 검사 | 12/12 일치 |
| 기록과 실물 일치 | 원천/Parquet SHA-256을 최근 성공 이력과 비교 | 12/12 일치 |
| 별도 원문 대조 | CSV의 모든 필드와 JSON의 원래 존재한 값을 별도 검증 스크립트로 비교 | 전체 일치 (앞선 구현 검증) |
| 재실행 | 동일 입력/설정의 출력 해시 및 수정 시각 비교 | 12/12 unchanged 확인 (앞선 구현 검증) |
| 자동 테스트 | unittest, 보존·시트/컬럼 선택·경로 충돌·실패 보존·출처 충돌·원천 변경 등 | 9/9 통과 (직전 코드 검증) |
| 노트북 | 전체 코드 셀 5개 실행 | 정상 완료 (직전 코드 검증) |

현재 문서 작성 시에는 실제 파일을 읽기만 하여 행·컬럼·값·출처·SHA-256을 다시 확인했습니다. 새 적재는 수행하지 않았습니다.

## 실행

프로젝트 루트에서 Python 3.12 이상으로 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/01_bronze.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

[`../src/config.py`](../src/config.py)에서 입력 폴더, 출력 폴더, 수집 이력 경로와 `FileRule`을 변경한다.
현재 기본값은 `../data/00_origin`의 CSV/JSONL을 모든 컬럼 그대로 읽는 설정이다.
CSV, TSV, JSONL, XLSX/XLSM, Parquet을 지원한다. 구형 XLS는 지원하지 않는다.
`pattern`은 입력 폴더 기준 파일 경로 또는 glob이고, `sheet_names=None`은 모든 Excel 시트,
`usecols=None`은 모든 컬럼이다. 명시적으로 컬럼을 선택하면 그 컬럼과 순서만 저장하며 이력에 선택 목록을 남긴다.
CSV 인코딩·구분자, Excel 헤더 위치도 파일 규칙마다 설정한다.
여러 규칙이 같은 파일에 일치하거나 서로 다른 입력이 같은 출력 경로에 대응하면 변환 전에 중단한다.

다른 폴더에 대해서도 같은 코드로 실행한다. 상대 경로는 실행 위치와 관계없이 프로젝트 루트 기준이다.

```powershell
.\.venv\Scripts\python.exe src/01_bronze.py --source-root D:/other/input --output-root D:/other/01_bronze --manifest-path D:/other/meta/bronze_ingestion.jsonl
```

## 저장 구조와 보존

- `00_origin/order/bet_order.csv` → `01_bronze/order/bet_order.parquet`
- `input/sub/book.xlsx` → `01_bronze/sub/book/<시트이름>.parquet` (시트 이름의 경로 특수문자는 URL 인코딩)
- 확장자만 Parquet으로 바꾸고 상대 폴더 경로와 파일 이름의 대소문자를 유지한다.
- CSV는 타입 정보가 없으므로 모든 값을 문자열로 읽어 `01`, 빈 문자열, `NA`, 공백, 날짜 원문을 보존한다. 자동 숫자/날짜 추론을 하지 않는다.
- CSV 빈/중복 헤더나 열 수가 다른 행은 자동 수정하지 않고 실패 이력에 남긴다.
- Excel은 저장된 셀 값을 읽는다. 서식·수식 자체·병합·화면 표시 형식은 Parquet 테이블의 보존 대상이 아니다. 서로 다른 타입이 섞여 Arrow로 표현할 수 없는 열은 자동 치환하지 않고 실패한다.
- JSONL은 날짜를 파싱하거나 중첩 필드를 펼치지 않는다. JSON 필드의 합집합을 컬럼/struct 스키마로 만들므로 없는 필드는 Parquet에서 null로 표현된다. 실제 빈 문자열은 그대로 보존한다.
- 행 필터링, 중복 제거, 정렬, 원천 컬럼명 변경을 하지 않는다. 원천 컬럼 뒤에 `source_file`, `ingested_at` 두 출처 컬럼을 추가한다.
- Parquet 임시 파일을 다시 읽어 전체 값과 스키마, 행 수를 비교한 다음 원자적으로 교체한다. 같은 결과이면 기존 파일을 수정하지 않는다.
- 원천 파일 SHA-256을 읽기 전후 비교한다. 읽는 중 바뀌면 해당 파일은 실패 처리한다.
- 동일 설정/입력으로 재실행하면 데이터 파일은 동일하며 실행 이력만 추가된다. 원천이 바뀌면 해당 Bronze는 갱신되므로 과거 데이터 스냅샷은 Git 등으로 별도 관리한다.

## Bronze 출처 컬럼

각 행에 `source_file`(경로를 제외한 원천 파일명과 확장자, 예: `bet_order.csv`)과 `ingested_at`(KST `YYYY-MM-DD HH:MI:SS`)을 추가한다.
기존 원천 컬럼은 그대로 두고 마지막에 두 컬럼만 붙인다. 컬럼명은 `config.py`에서 변경 가능하다.
원천 컬럼과 이름이 겹치면 덮어쓰지 않고 실패한다.
같은 경로·SHA-256·시트는 성공 이력의 최초 수집 시각을 재사용하여 재실행 결과를 유지한다.
원천 내용이 바뀌면 새 수집 시각을 기록한다. 기존 이력은 삭제하지 않고 함께 보관한다.
이전 버전으로 적재한 파일도 기존 성공 이력의 최초 수집 시각을 사용해 두 컬럼을 추가한다.
사용자의 출처 컬럼 추가 요청에 따라 실행 시각은 이력의 최초 수집 시각으로 고정하여 본문에 기록한다.

## 수집 이력

`../meta/bronze_ingestion.jsonl`에 파일/시트/실행별로 한 줄씩 추가한다.
`ingested_at`은 이번 실행에서 파일을 읽기 시작한 실제 시각, `saved_at`은 저장 또는 기존 결과 검증 완료 시각이다.
원천이 처음 외부에서 다운로드된 시각은 확인할 수 없으므로 이를 수집 시각으로 추정하지 않는다.
매핑 규칙서에 따라 일시는 `YYYY-MM-DD HH:MI:SS`, 시간대는 `timezone=KST`, `utc_offset=+09:00`으로 명시한다.
`data_ingested_at`은 본문에 기록한 최초 수집 시각이다. 파일 경로·상대 경로·시트·선택 컬럼·입출력 컬럼·입출력 행 수·행 수 일치·값 일치·SHA-256·실행 ID와 상태를 기록한다.
`written`: 새로 저장/갱신, `unchanged`: 기존 결과와 동일, `failed`: 실패와 예외 사유.
일부 파일 실패 시 다른 파일 이력도 남기고 실행 종료 코드는 실패로 반환한다. 설정/출력 충돌은 실행 전에 예외로 중단한다.

## 노트북

[`../src/01_bronze_preview.ipynb`](../src/01_bronze_preview.ipynb)에서 프로젝트 루트와 `CONFIG`를 불러온다.
설정에 해당하는 원천/Parquet 경로 목록과 각 파일의 `head(3)`, 수집 이력의 최근 실행 대사를 확인한다.
원천 미리보기는 변환 코드의 동일 리더를 사용한다. 노트북은 변환을 자동 실행하지 않으므로 먼저 위 명령으로 Bronze를 생성한다.


## 설정 항목

| 설정 | 기본값 | 의미 |
| --- | --- | --- |
| source_root | data/00_origin | 입력 루트 폴더 |
| output_root | data/01_bronze | 결과 루트 폴더 |
| manifest_path | meta/bronze_ingestion.jsonl | 누적 이력; 삭제 시 최초 시각 재사용에 영향 |
| rules / pattern | FileRule() / **/* | 지원 파일 검색; 다중 규칙 중복 매칭은 오류 |
| sheet_names | None | Excel 모든 시트; 이름 또는 0부터 시작하는 인덱스 지정 가능 |
| usecols | None | 모든 컬럼; 명시 시 해당 컬럼을 지정 순서로 선택 |
| encoding / delimiter | utf-8-sig / , | 텍스트 인코딩 / CSV 구분자 |
| header | 0 | Excel 헤더의 0 기반 행 위치 |
| compression | snappy | Parquet 압축 |
| source_file_column / ingested_at_column | source_file / ingested_at | 추가 출처 컬럼명; 원천명과 충돌 시 실패 |

## 이력 필드 읽는 법

| 이력 필드 | 의미 |
| --- | --- |
| run_id | 실행 식별자 |
| source_path / source_relative_path | 전체 원천 경로 / 입력 루트 기준 상대 경로 |
| sheet_name / output_path | 원천 Excel 시트 / Parquet 저장 경로 |
| ingested_at | 이번 실행에서 읽기 시작한 시각; 본문 최초 시각과 다를 수 있음 |
| data_ingested_at | 본문 ingested_at에 실제로 넣은 최초 성공 수집 시각 |
| saved_at | 이번 실행의 저장 또는 동일 결과 검증 완료 시각 |
| timezone / utc_offset | KST / +09:00 |
| source_rows / bronze_rows | 원천 / 출력 행 수 |
| row_count_match / values_match | 행 수 / Parquet 왕복 값 검증 통과 여부 |
| source_columns / output_columns | 원천 / 출력 컬럼명 목록 |
| selected_columns / provenance_columns | 설정에 따른 선택 컬럼 / 추가 출처 컬럼 |
| source_sha256 / output_sha256 | 원천 / 결과 내용 해시 |
| status / error / failed_at | 처리 상태 / 실패 사유 / 실패 시각 |

## 진행 중 확인한 사항과 처리

| 사항 | 처리·현재 상태 |
| --- | --- |
| 출처를 이력에만 기록했던 초기 구현 | 사용자 요청에 따라 Bronze 본문에도 두 출처 컬럼 추가 완료 |
| source_file의 경로 포함 | 사용자 요청에 따라 파일명.확장자만 저장하도록 변경 완료 |
| 노트북이 마지막 Parquet 읽기 핸들을 유지해 파일 교체가 거부됨 | 읽기 핸들을 닫고 재적재 완료; 노트북에도 close 처리 반영 |
| 과거 실패 이력 | 삭제하지 않음; 최신 완료 실행을 기준으로 결과 판단 |

## 변경 이력

| 일자 (KST) | 작업 | 결과 |
| --- | --- | --- |
| 2026-11-20 | 설정 기반 CSV/JSONL/Excel/TSV/Parquet 리더 및 변환 구현 | 다른 입력 폴더에도 동일 코드 적용 |
| 2026-11-20 | 출처 컬럼 추가 및 파일명 정책 반영 | 원천 컬럼 뒤에 source_file, ingested_at 추가 |
| 2026-11-20 | 최초 수집 시각 재사용·누적 이력·검증 구현 | 원천 값 보존, 재실행 결과 동일 |
| 2026-11-20 | 원천/결과 미리보기 노트북 및 테스트 작성 | head(3), 경로·이력·대사 확인 |
| 2026-11-20 | docs 문서 체계 정리 | 실제 처리 결과와 향후 계획을 분리하여 기록 |
| 2026-11-20 | 사용법 문서 개편 | bronze_usage.md에 환경 준비·설정 예시·실행·결과 확인 안내를 작성하고 문서 탐색에 연결 |
