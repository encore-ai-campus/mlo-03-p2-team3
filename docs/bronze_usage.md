# Bronze 사용법 — 첫 설정부터 Parquet 확인까지

[데이터 안내](DATA_GUIDE.md) · [Bronze 작업 기록](BRONZE.md) · [Bronze 컬럼 사전](BRONZE_COLUMNS.md)

이 문서는 처음 실행하는 사람이 `src/config.py`를 설정하고 `src/01_bronze.py`로 파일을 Parquet으로 변환하는 순서대로 설명합니다.
현재 실행 파일명은 **`01_bronze.py`**입니다. 아래 명령은 모두 **프로젝트 루트**에서 실행합니다.

## 1. 실행 위치와 Python 환경 준비

PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd D:\IT\mlo3_p2_team3_EB
```

프로젝트에 `.venv`가 이미 있으면 생성 단계는 건너뜁니다. 새 환경에서는 Python 3.12 이상을 먼저 설치한 뒤 가상환경을 만듭니다.

```powershell
python -m venv .venv
```

프로젝트 전용 Python으로 필요한 패키지를 설치합니다. 가상환경 활성화는 필요하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

| 준비 항목 | 용도 |
| --- | --- |
| Python 3.12 이상 | 코드 실행 |
| pandas, pyarrow | 원천 읽기, Parquet 생성·검증 |
| openpyxl | XLSX/XLSM 시트 읽기 |
| nbformat, nbclient, ipykernel | 노트북 형식·실행 지원 |

현재 프로젝트에는 전용 `.venv`가 생성되어 있습니다. 다른 컴퓨터에서 처음 실행할 때는 위 환경 준비를 진행합니다.

## 2. config.py에서 세 경로 설정

[`src/config.py`](../src/config.py)를 열고 **파일 아래쪽의 `CONFIG = BronzeConfig()` 부분을 교체**합니다.
`BronzeConfig`, `FileRule` 클래스와 기존 import는 그대로 둡니다. 실제로 사용할 `CONFIG` 대입문은 하나만 남깁니다.

현재 프로젝트의 모든 원천 파일과 모든 컬럼을 읽으려면 다음 설정을 사용합니다.

```python
CONFIG = BronzeConfig(
    source_root=PROJECT_ROOT / "data/00_origin",
    output_root=PROJECT_ROOT / "data/01_bronze",
    manifest_path=PROJECT_ROOT / "meta/bronze_ingestion.jsonl",
    rules=(
        FileRule(pattern="**/*", sheet_names=None, usecols=None),
    ),
)
```

| 설정 | 넣을 값 | 현재 예시 |
| --- | --- | --- |
| source_root | 읽어 올 파일들이 있는 루트 폴더 | data/00_origin |
| output_root | 변환 결과를 저장할 루트 폴더 | data/01_bronze |
| manifest_path | 수집·저장·검증 이력을 누적할 파일 | meta/bronze_ingestion.jsonl |

| 경로 작성 방법 | 예시 | 해석 |
| --- | --- | --- |
| 프로젝트 기준 | `PROJECT_ROOT / "data/00_origin"` | 프로젝트 루트 아래 폴더 |
| 상대 경로 | `Path("data/00_origin")` | 실행 위치와 관계없이 프로젝트 루트 기준 |
| 외부 절대 경로 | `Path("D:/other/input")` | 해당 폴더에서 입력을 검색 |

입력·출력 폴더는 서로 같거나 상하위로 겹칠 수 없습니다. 이력 파일도 원천 폴더 밖에 둡니다.
출력 폴더와 이력 파일의 부모 폴더는 코드가 생성합니다. 입력 폴더는 미리 존재해야 합니다.

## 3. 읽을 파일·시트·컬럼 지정

`rules` 안의 `FileRule`로 파일별 읽기 방법을 지정합니다.

| 설정 | 기본값 | 설정 방법 |
| --- | --- | --- |
| pattern | `"**/*"` | source_root 기준 파일 경로 또는 glob |
| sheet_names | `None` | Excel 모든 시트. 일부만 읽으려면 시트명 또는 0부터 시작하는 번호 튜플 |
| usecols | `None` | 모든 원천 컬럼. 일부만 읽으려면 정확한 원천 컬럼명 튜플 |
| encoding | `"utf-8-sig"` | CSV/TSV/JSONL의 실제 인코딩. 예: cp949 |
| delimiter | `","` | CSV 구분자. TSV 파일은 자동으로 탭 사용 |
| header | `0` | Excel 헤더 행의 위치. 첫 행 0, 두 번째 행 1 |

| pattern 예시 | 검색 범위 |
| --- | --- |
| `"**/*"` | 모든 하위 폴더의 지원 파일 |
| `"**/*.csv"` | 모든 하위 폴더의 .csv 파일 |
| `"order/*.csv"` | order 폴더 바로 아래의 .csv 파일 |
| `"order/bet_order.csv"` | 특정 파일 하나 |

지원 확장자는 `.csv`, `.tsv`, `.jsonl`, `.xlsx`, `.xlsm`, `.parquet`입니다. 구형 `.xls`는 지원하지 않습니다.
하나의 파일이 여러 규칙에 동시에 일치하면 중단합니다. 기본 `FileRule()`에 특정 파일 규칙을 덧붙이지 말고, 서로 겹치지 않는 규칙으로 교체합니다.
각 규칙에 일치하는 지원 파일이 하나도 없어도 중단합니다.

### 예시 A. 현재 프로젝트의 특정 CSV만 변환

```python
CONFIG = BronzeConfig(
    source_root=PROJECT_ROOT / "data/00_origin",
    output_root=PROJECT_ROOT / "data/01_bronze",
    manifest_path=PROJECT_ROOT / "meta/bronze_ingestion.jsonl",
    rules=(
        FileRule(pattern="order/bet_order.csv"),
    ),
)
```

결과는 `data/01_bronze/order/bet_order.parquet`에 저장됩니다. 지정하지 않은 파일은 처리하지 않습니다.

### 예시 B. 다른 폴더의 Excel에서 지정 시트·컬럼만 읽기

아래 경로·파일명·시트명·컬럼명은 **사용할 파일의 실제 값으로 바꿉니다**.

```python
CONFIG = BronzeConfig(
    source_root=Path("D:/other/input"),
    output_root=Path("D:/other/01_bronze"),
    manifest_path=Path("D:/other/meta/bronze_ingestion.jsonl"),
    rules=(
        FileRule(
            pattern="sales/book.xlsx",
            sheet_names=("매출",),
            usecols=("주문번호", "판매일시", "금액"),
            header=0,
        ),
    ),
)
```

| 바꾸고 싶은 동작 | 설정 |
| --- | --- |
| 모든 시트 읽기 | `sheet_names=None` |
| 두 시트 읽기 | `sheet_names=("매출", "취소")` |
| 첫 번째 시트 읽기 | `sheet_names=(0,)` |
| 모든 컬럼 유지 | `usecols=None` |
| 특정 컬럼만 지정 순서로 읽기 | `usecols=("주문번호", "금액")` |

하나만 지정해도 `("매출",)`처럼 끝의 쉼표를 넣어 튜플로 작성합니다.
컬럼을 선택하면 결과에는 **선택한 컬럼과 출처 두 컬럼만** 들어갑니다. 현재 프로젝트처럼 원천 컬럼을 전부 보존하려면 `usecols=None`을 사용합니다.

### 예시 C. 파일마다 다른 읽기 설정

```python
CONFIG = BronzeConfig(
    source_root=Path("D:/other/input"),
    output_root=Path("D:/other/01_bronze"),
    manifest_path=Path("D:/other/meta/bronze_ingestion.jsonl"),
    rules=(
        FileRule(pattern="member.csv", encoding="cp949"),
        FileRule(pattern="sales.csv", delimiter=";"),
        FileRule(pattern="book.xlsx", sheet_names=("Sheet1",), header=1),
    ),
)
```

위 예시는 서로 다른 파일 3개가 모두 입력 폴더에 있을 때 사용합니다. 실제로 없는 파일의 규칙은 제거합니다.

## 4. 저장 후 Bronze 변환 실행

설정 파일을 저장한 다음 프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe src/01_bronze.py
```

| 처리 순서 | 수행 내용 |
| --- | --- |
| 1 | CONFIG에서 입력·출력·이력 경로와 파일 규칙 읽기 |
| 2 | 파일·시트 목록을 정렬하고 경로 겹침·중복 매칭·출력 충돌 검사 |
| 3 | 원천을 읽고 설정한 컬럼 선택 |
| 4 | source_file, ingested_at 두 출처 컬럼 추가 |
| 5 | 같은 결과 폴더에 임시 Parquet 생성 |
| 6 | Parquet을 다시 읽어 행 수·전체 값·스키마 검증, 원천 내용 변경 여부 확인 |
| 7 | 검증 성공 시 결과 저장. 기존 결과와 같으면 파일을 수정하지 않음 |
| 8 | 파일/시트별 결과를 수집 이력에 추가 |

콘솔 출력 예시는 다음과 같습니다. 아래 경로는 예시입니다.

```text
written: order/bet_order.csv -> D:\IT\mlo3_p2_team3_EB\data\01_bronze\order\bet_order.parquet
```

| 상태 | 의미 | 다음 확인 |
| --- | --- | --- |
| written | 새로 저장하거나 기존 결과 갱신 | 출력 Parquet 확인 |
| unchanged | 이번 결과가 기존 파일과 동일 | 정상 재실행 결과 |
| failed | 해당 파일 처리 실패 | 이력의 error 확인 |

일부 파일이 실패해도 나머지 파일을 처리한 뒤 최종 종료 코드는 실패로 반환합니다. 설정·출력 경로 충돌은 파일 처리 전에 중단합니다.

### 경로만 일회성으로 변경하기

config.py를 바꾸지 않고 이번 실행의 세 경로만 덮어쓸 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe src/01_bronze.py --source-root "D:/other/input" --output-root "D:/other/01_bronze" --manifest-path "D:/other/meta/bronze_ingestion.jsonl"
```

파일 패턴·시트·컬럼 등은 계속 config.py의 설정을 사용합니다. 현재 rules가 다른 폴더의 파일과 맞는지 먼저 확인합니다.

## 5. 결과 파일과 출처 확인

### 저장 위치

원천 루트 아래 상대 폴더 구조와 파일 이름을 유지하고 확장자를 `.parquet`으로 바꿉니다. Excel은 파일별 폴더 아래 시트마다 하나씩 저장합니다.

| source_root 아래 입력 | output_root 아래 결과 |
| --- | --- |
| order/bet_order.csv | order/bet_order.parquet |
| event/race_change_events.jsonl | event/race_change_events.parquet |
| sales/book.xlsx의 매출 시트 | sales/book/%EB%A7%A4%EC%B6%9C.parquet |
| sub/data.tsv | sub/data.parquet |

Excel 시트명은 URL 인코딩하므로 실제 파일명에서 한글·특수문자가 `%...`로 표시될 수 있습니다.
예를 들어 매출 시트는 `%EB%A7%A4%EC%B6%9C.parquet`으로 저장됩니다.

### 추가되는 두 컬럼

| 컬럼 | 예시 | 의미 |
| --- | --- | --- |
| source_file | bet_order.csv | 경로를 제외한 원천 파일명과 확장자 |
| ingested_at | 2026-11-20 14:40:35 | 최초 성공 수집 시각. KST, YYYY-MM-DD HH:MI:SS 문자열 |

기존 원천 컬럼과 값은 유지하고 마지막에 두 컬럼을 붙입니다.
동일 원천 경로·SHA-256·시트의 최초 성공 수집 시각은 이력에서 재사용합니다. 이력 파일을 삭제하면 재실행 시 수집 시각이 바뀔 수 있으므로 결과와 함께 보관합니다.
원천 내용이 바뀌면 새 수집 시각과 결과로 갱신합니다.

### 실행 이력 확인

현재 프로젝트의 이력 마지막 한 줄은 다음 명령으로 확인합니다. 다른 경로를 설정했다면 해당 경로로 바꿉니다.

```powershell
Get-Content -Encoding utf8 meta/bronze_ingestion.jsonl | Select-Object -Last 1 | ConvertFrom-Json | Format-List
```

| 확인할 필드 | 정상 기준 / 의미 |
| --- | --- |
| source_path / output_path | 의도한 원천·저장 경로인가 |
| sheet_name | 의도한 Excel 시트인가 |
| source_rows / bronze_rows | 두 행 수가 같은가 |
| row_count_match / values_match | 둘 다 true인가 |
| status | written 또는 unchanged인가 |
| data_ingested_at | Parquet 본문의 ingested_at과 같은 최초 수집 시각 |
| ingested_at / saved_at | 이번 실행에서 읽기 시작한 시각 / 저장·검증 완료 시각 |
| timezone / utc_offset | KST / +09:00 |

## 6. 노트북으로 head(3) 확인

| 순서 | 할 일 |
| --- | --- |
| 1 | 먼저 위 명령으로 Bronze 생성 |
| 2 | PyCharm 등 Jupyter를 지원하는 도구에서 [01_bronze_preview.ipynb](../src/01_bronze_preview.ipynb) 열기 |
| 3 | 프로젝트 .venv의 Python을 인터프리터/커널로 선택 |
| 4 | 노트북 작업 폴더를 프로젝트 루트 또는 src로 두고 위에서부터 모든 셀 실행 |
| 5 | 설정된 원천/결과 경로, 원천별 head(3), Bronze별 head(3), 최근 실행 대사 확인 |

다른 위치에서 노트북을 실행한다면 첫 코드 셀의 `PROJECT_ROOT`를 실제 프로젝트 루트로 지정합니다.
노트북은 변환을 자동 실행하지 않으며 원천 미리보기에서 파일 전체를 읽으므로 큰 파일은 메모리가 필요합니다.
requirements.txt는 커널·노트북 실행 라이브러리를 설치하며, 별도 JupyterLab 화면 프로그램까지 설치하는 구성은 아닙니다.

## 7. 자주 만나는 오류

| 증상 | 확인·해결 |
| --- | --- |
| python을 찾을 수 없음 | Python 3.12 이상 설치 여부 확인. 이미 만든 환경은 .venv/Scripts/python.exe로 실행 |
| ModuleNotFoundError | 같은 .venv Python으로 requirements.txt 설치 후 재실행 |
| 입력 폴더가 없음 | source_root의 실제 경로 확인 |
| 설정과 일치하는 지원 파일이 없음 | pattern이 source_root 기준인지, 파일명·확장자가 맞는지 확인 |
| 여러 규칙이 같은 파일과 일치 | rules에서 포괄 규칙과 개별 파일 규칙의 겹침 제거 |
| 시트 오류 / KeyError | 실제 시트명·0 기반 인덱스·헤더 위치·컬럼명 확인 |
| UnicodeDecodeError | encoding을 실제 원천 인코딩으로 설정 |
| 빈/중복 헤더 또는 CSV 열 수 오류 | 원천 문제를 AS-IS에 기록. 자동으로 고치지 않으며 올바른 입력·읽기 설정인지 확인 |
| 출처 컬럼 이름 충돌 | config.py의 source_file_column / ingested_at_column을 원천에 없는 이름으로 지정 |
| 출력 경로 충돌 | 같은 상대 경로에 같은 stem의 CSV/JSONL 등이 있거나 Excel 출력 폴더와 겹치는지 확인 |
| PermissionError / 액세스 거부 | 미리보기의 Parquet 읽기 핸들 등 파일을 열고 있는 대상을 닫은 뒤 재실행 |
| Excel 혼합 타입의 Arrow 변환 오류 | 셀 타입이 섞인 열을 확인. 현재 코드는 값을 임의 치환하지 않고 실패 이력에 남김 |

현재 구현은 전체 파일을 메모리에 읽습니다. Excel은 셀 값 기준이며 서식·수식 자체·병합 구조를 보존하지 않습니다.
JSON은 중첩을 유지하지만 선택 필드가 없는 행은 Parquet에서 null로 표현됩니다. 표준화·공백 제거·중복 제거는 수행하지 않습니다.

## 관련 문서와 변경 이력

| 문서 | 용도 |
| --- | --- |
| [BRONZE.md](BRONZE.md) | 실제 수행한 작업·검증 결과·변경 내역 |
| [BRONZE_COLUMNS.md](BRONZE_COLUMNS.md) | 현재 결과 파일의 컬럼 설명 |
| [DATA_GUIDE.md](DATA_GUIDE.md) | 전체 데이터·단계 안내 |

| 일자 (KST) | 변경 |
| --- | --- |
| 2026-11-20 | 기존 링크 안내를 환경 준비 → config.py 경로·파일·시트·컬럼 설정 → 01_bronze.py 실행 → 결과·이력·head(3) 확인 순서의 사용법으로 교체 |
