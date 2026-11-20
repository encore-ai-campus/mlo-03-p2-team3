# Silver 표준화 사용법

[작업 기록](SILVER.md) · [변경 내역·건수](SILVER_CHANGES.md) · [컬럼 사전](SILVER_COLUMNS.md)

## 1. 준비와 입력

| 항목 | 설정 |
| --- | --- |
| 실행 파일 | [02_normalize.py](../src/02_normalize.py) |
| 입력 | Bronze Parquet만 사용. origin CSV/JSONL을 다시 읽지 않음 |
| 기본 입력 경로 | 프로젝트 루트/data/01_bronze; 하위 폴더까지 검색 |
| 기본 출력 경로 | 프로젝트 루트/data/02_silver; 모든 파일을 바로 아래 저장 |
| 기본 규칙 | mapping_rules.md의 공용 규칙을 코드로 정의한 default_specs() |
| config.py 관계 | Bronze용 설정과 별개. Silver 경로는 아래 실행 인자로 지정 |
| 의존 패키지 | Python 3.12 이상, pandas, pyarrow |

프로젝트 루트에서 전용 가상환경을 사용합니다. 패키지가 없다면 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install pandas pyarrow
```

## 2. 현재 프로젝트 실행

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --check-reference
```

`--check-reference`는 공용 규칙서 11장의 이 데이터셋 고정 행 수·NULL 수를 추가 검증합니다.
다른 시기·다른 크기의 입력에서는 이 옵션을 생략하고 입력 대비 보존·변환·추적 검증을 사용합니다.

| 처리 | 내용 |
| --- | --- |
| 입력 확인 | 규칙별 입력 파일명(stem)이 하나씩 있는지 확인. 경로 중첩·미매핑 컬럼·파일 충돌 차단 |
| 표준화 | 이름·타입·값·단위·날짜 형식 변환. 행 정렬/삭제/중복 제거 없음 |
| 출처 | SOURCE_FILE·INGESTED_AT을 유지/타입 변환, 원천 행 번호와 Bronze 상대 경로 추가 |
| 테이블 분리 | RC_SALES 합계 분리, 진료명 브리지 생성: 기본 규칙은 14개 파일 |
| 대사 | 각 입력 행이 대응 테이블에 정확히 한 번 존재하는지 확인. 브리지는 항목 수·순서·부모 연결 확인 |
| 임시 저장 검증 | Parquet 왕복 값·스키마 비교 후 저장. 검증 실패 시 Silver를 저장하지 않고 진단 기록 남김 |
| 보고서 | meta의 데이터 사전·전체 변경값별 건수·NULL 사유와 docs의 실제 결과 표 생성 |

## 3. 다른 프로젝트에서 같은 규칙 사용

02_normalize.py는 config.py 등 다른 프로젝트 소스 파일을 import하지 않습니다.
이 파일을 다른 프로젝트로 복사하고 pandas/pyarrow를 설치한 뒤, 입력·출력·메타·문서 경로를 지정할 수 있습니다.
기본 규칙을 그대로 쓰려면 같은 원천 컬럼과 파일명이 필요합니다. 경마와 무관한 데이터까지 동일한 코드표로 추정 변환하지 않습니다.

```powershell
python 02_normalize.py --input-root "D:/other/data/01_bronze" --output-root "D:/other/data/02_silver" --meta-root "D:/other/meta" --docs-root "D:/other/docs"
```

| 인자 | 의미 |
| --- | --- |
| --input-root | Bronze 루트; .parquet 재귀 검색 |
| --output-root | 평면 Silver 저장 폴더 |
| --meta-root | 데이터 사전·변환 건수·이슈·검증 이력 경로 |
| --docs-root | 자동 생성되는 단계·컬럼·변경·사용법 문서 경로 |
| --spec | 다른 원천 구조에 사용할 JSON 규칙 파일 |
| --check-reference | 현재 공용 데이터셋의 고정 기대값 검증 |
| --dump-default-spec | 기본 규칙을 JSON으로 내보내고 종료 |

4개 경로는 서로 겹치지 않게 지정합니다. 입력 파일명은 하위 폴더가 달라도 규칙별로 유일해야 합니다.
규칙에 없는 입력 파일이나 출력 폴더에 남은 다른 테이블이 있으면 자동 삭제하지 않고 중단하므로 별도 경로를 사용합니다.

## 4. 다른 컬럼·코드표는 JSON으로 지정

기본 규칙을 파일로 꺼내 수정하려면 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize.py --dump-default-spec meta/normalize_rules.json
```

새 구조라면 아래처럼 별도 규칙을 작성합니다. 이 예시는 person.parquet의 gender 컬럼이 실제로 `2`/`1`을 뜻한다고 정의한 경우에만 사용합니다.

```json
{
  "tables": {
    "PERSON": {
      "input": "person",
      "columns": [
        {"source": "gender", "target": "SEX_CD", "type": "string", "op": "map", "mapping": {"2": "F", "1": "M"}}
      ],
      "drop": []
    }
  }
}
```

| 규칙 필드 | 의미 |
| --- | --- |
| tables의 키 | 출력 테이블명·파일명. UPPER_SNAKE |
| input | 입력 Parquet 파일명에서 확장자를 제외한 이름 |
| columns[].source | 원천 컬럼명. JSON struct 하위는 race.rcDate처럼 점으로 표현 |
| columns[].target | 표준 컬럼명. UPPER_SNAKE |
| columns[].type | string, int32, int64, date32, timestamp, time, decimal(p,s) |
| columns[].op | text(TRIM·빈값), upper, map 등 변환. 날짜/숫자 타입은 text에서도 type에 맞게 변환 |
| mapping | map 연산의 명시적 원천값 → 표준값 사전 |
| allowed | NULL을 제외한 허용 출력 코드 목록; 필요 시 지정 |
| drop | Silver에서 의도적으로 제외할 원천 컬럼명. 제외 사유가 데이터 사전에 기록됨 |

원천 컬럼을 columns 또는 drop에 모두 명시해야 합니다. Bronze의 source_file과 ingested_at은 있으면 자동 추적 매핑하므로 생략할 수 있습니다.

```powershell
python 02_normalize.py --input-root "D:/other/data/01_bronze" --output-root "D:/other/data/02_silver" --meta-root "D:/other/meta" --docs-root "D:/other/docs" --spec "D:/other/meta/person_rules.json"
```

기본 경마 코드표에는 숫자 `2` → F 규칙이 없습니다. 위 JSON처럼 명시한 규칙에서만 변환하며, `2`가 5행이면 보고서에 `2 → F (5)`로 집계합니다.

## 5. 보고서 확인과 재실행

| 확인 대상 | 볼 내용 |
| --- | --- |
| SILVER.md | 테이블별 행 수·보존 대사·검증 결과 |
| SILVER_CHANGES.md | 테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 대상·이름·타입·값 변경 건수 |
| SILVER_COLUMNS.md | 실제 컬럼·Arrow 타입·NULL 이유·처음 3행 예시 |
| meta/silver_value_changes.csv | 전체 원천값 → 표준값별 변경 건수. 값이 많은 항목도 생략 없이 기록 |
| meta/silver_issue_log.csv | 값이 있던 원천이 NULL로 바뀐 사유, 실패·코드표 밖 값, 원천 행 번호 |
| meta/silver_validation.json | 입력/출력 SHA-256과 검증 결과 |

같은 입력·규칙·코드·옵션으로 재실행하면 Parquet과 집계 결과가 같습니다. 동일 파일은 덮어쓰지 않습니다.
실행 시각은 Silver 본문에 추가하지 않으며 Bronze에서 받은 최초 수집 시각을 사용합니다.

검증 도구가 함께 있다면 저장된 결과를 읽기만 하여 다시 검사합니다.

```powershell
.\.venv\Scripts\python.exe src/02_normalize_check.py --check-reference
```

독립 실행에 필요한 파일은 02_normalize.py 하나이며, 02_normalize_check.py는 선택적인 재검증 도구입니다.
코드·규칙·입력이 바뀌면 표준화를 먼저 재실행해야 현재 결과의 해시와 맞습니다.

## 범위와 오류 처리

| 사항 | 동작 |
| --- | --- |
| 중복·전표/마권 불일치·이상값 | 이번에는 정제하지 않음. 입력 행 유지 |
| 빈값·규칙상 NULL | 공용 표준화 규칙에 따른 변환. 원천은 Bronze에 남기고 NULL 이유 기록 |
| 날짜·숫자 변환 실패 / 코드표 밖 | PARSE_FAIL / OUT_OF_CODE 진단 기록, 검증 실패로 Silver 저장 중단. 행을 골라 제외하지 않음 |
| 규칙서에 없는 원문 해석 | 별도 결정 ID와 적용 조건 기록. 통과기록 없음 해석은 SILVER.md 참조 |
| PermissionError | 결과 파일의 읽기 핸들을 닫고 재실행 |
| 메모리 | 파일 전체와 변환 로그를 메모리에서 처리하므로 대용량은 메모리 필요 |

현재 단계는 **표준화**입니다. 품질 관리와 행 제외는 별도 단계에서 근거 결정 ID·유지/제외 데이터·건수 대사와 함께 수행합니다.
