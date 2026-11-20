# 품질 관리 실행 사용법

[작업 기록](QUALITY.md) · [변경 건수](QUALITY_CHANGES.md) · [Gold 입력 계약](GOLD_INPUT_CONTRACT.md)

## 실행

프로젝트 루트에서 실행합니다. 기존 Bronze/Silver 코드와 입력 파일을 다시 생성하지 않습니다.

**현재처럼 결과가 이미 있으면 읽기 전용 확인만 실행합니다.** 이 검증은 규칙을 메모리에서 다시 측정하고 기존 파일과 비교하며, 결과 파일을 저장하지 않습니다.

```powershell
.\.venv\Scripts\python.exe src/02_quality_check.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_quality.py -v
```

아래 처리 명령은 최초 생성 또는 별도 버전 생성에 사용합니다.

```powershell
.\.venv\Scripts\python.exe src/02_quality.py --check-reference
.\.venv\Scripts\python.exe src/02_quality_check.py
```

| 옵션 | 기본값 / 의미 |
| --- | --- |
| --input-root | data/02_silver; 바로 아래 표준화 Parquet 14개만 읽음 |
| --clean-root | data/02_silver/clean; 새 결과 14개 |
| --excluded-root | data/02_silver/_excluded; 완전 중복 제외만 저장 |
| --meta-root | meta; dq_* 로그·검증·manifest와 병합 로그 |
| --docs-root | docs; 품질 관리 결과·컬럼·변경·Gold 계약 |
| --check-reference | 현재 팀 데이터셋의 확정 건수와 비교; 일반 입력에서는 생략 가능 |

기존 clean/_excluded 파일과 결과가 다르면 덮어쓰지 않고 중단합니다. 새 규칙/새 입력은 명시적으로 별도 버전 출력 폴더와 meta/docs 경로를 지정해 검토합니다.
같은 결과는 바이트와 수정 시각을 유지합니다. 실행 시각을 데이터에 넣지 않습니다.
검증을 모두 통과한 결과를 임시 폴더에 저장하고 Parquet 왕복 비교 및 입력 해시·수정 시각을 확인한 뒤 게시합니다.

## 진료명 브리지

| 항목 | 보관·대사 |
| --- | --- |
| 표준화 1,664개 항목 | 기존 HR_VET_TYPE_BRIDGE.parquet에 그대로 보존 |
| 품질 처리 후 1,662개 항목 | clean/HR_VET_TYPE_BRIDGE.parquet |
| 2개 진료별 의미 병합 | meta/vet_type_merge_log.csv; 두 원래 항목 ID·값과 결과 ID 기록 |
| 대사 | 1,664 = 1,662 + 의미 병합 감소 2; _excluded에는 넣지 않음 |

## 검증 범위

새 02_quality_check.py는 표준화 파일 해시와 품질 결과를 함께 읽기만 하여 검사합니다.
기존 표준화 검증기의 하위 폴더 금지 조건은 바꾸지 않았으므로 품질 단계 후에는 이 전용 검증기를 사용합니다.
원래 Silver의 이슈 38,305건 기준이나 새 Bronze 추적 컬럼을 이번 작업에서 소급 적용하지 않습니다.

## 오류

| 상황 | 처리 |
| --- | --- |
| 입력이 14개 공용 테이블과 다름 | 중단; 표준화 입력 버전 확인 |
| 전표/경주 키가 중복되거나 시각 참조 누락 | 늦은 취소를 추정하지 않고 중단 |
| 마명 보정의 출전표 연결이 0개/복수 | 원래 빈값 유지, 근거 없는 보정 금지; 로그 기록 |
| 같은 마명·날짜 스냅샷이 여러 개 | 의료 매칭 미확인으로 보존; 임의 한 행 선택 금지 |
| 기존 품질 결과와 다름 | 덮어쓰지 않음; 별도 버전 경로 사용 |
| 결과 파일 잠김 | 해당 미리보기 핸들을 닫고 재실행 |

## 다른 마 경주 프로젝트에 적용

Python 3.11 이상과 저장소 `requirements.txt`의 패키지를 사용합니다. `src/02_quality.py`와 같은 폴더의 `src/02_quality_check.py`를 함께 복사하거나, 이 저장소의 스크립트에 다른 프로젝트 경로를 전달할 수 있습니다. 실행 폴더에 의존하지 않도록 기본 경로는 스크립트의 저장소 루트 기준이며, 아래처럼 입력·출력·meta·docs를 모두 지정하면 다른 프로젝트에 분리 저장합니다.

```powershell
.\.venv\Scripts\python.exe src/02_quality.py `
  --input-root 'D:\other_racing_project\data\02_silver' `
  --clean-root 'D:\other_racing_project\data\02_silver\clean_v1' `
  --excluded-root 'D:\other_racing_project\data\02_silver\excluded_v1' `
  --meta-root 'D:\other_racing_project\meta\quality_v1' `
  --docs-root 'D:\other_racing_project\docs\quality_v1'
.\.venv\Scripts\python.exe src/02_quality_check.py `
  --meta-root 'D:\other_racing_project\meta\quality_v1'
```

| 적용 조건 | 확인 사항 |
| --- | --- |
| 입력 계약 | 공용 표준 테이블 14개와 동일한 컬럼명·자료형·코드 의미가 필요. 원천 CSV나 임의 스키마를 바로 받는 범용 정제기는 아님 |
| 출처 | 모든 표준화 입력에 `_SRC_BRONZE_FILE`, `_SRC_ROW_NO`가 있어야 함 |
| 시간·코드 | 표준화 단계에서 KST 시각과 SALE/CANCEL, SOLD/CANCEL 등의 공통 코드를 맞춤 |
| 기대 건수 | 다른 데이터에는 `--check-reference`를 생략. 1,052·3,632 등의 고정 건수는 현재 팀 데이터 전용 |
| D-011 범위 | 원천 행 번호 595·664이면서 원문이 `일,열사병`이고 브리지가 `일`·`열사병`인 승인 기록에만 적용. 다른 행 번호·진료명은 별도 근거 결정과 코드 검토 필요 |
| 문서 검토 | 생성 문서의 현재 팀 경로·고정 예시(1,664→1,662 등)는 다른 데이터의 실측으로 사용하지 않음. 실제 결과는 그 실행의 `dq_validation.json`, `dq_manifest.json`, 대사 표로 확인하고 프로젝트 문서를 갱신 |
| 결과 보존 | 입력과 출력은 서로 다른 경로. 기존 결과와 달라지면 새 버전의 clean/excluded/meta/docs 경로를 함께 지정 |
| 배포·이동 | manifest는 절대 경로와 입력 수정 시각을 기록함. 원본 프로젝트에서 검증하며 폴더를 옮긴 뒤 경로 문자열만 바꿔 검증 완료로 간주하지 않음 |
| Gold 경계 | 이 코드는 50대 필터·단승 필터·승률·취소 연결·팩트/차원 생성을 하지 않음. 공용 품질 데이터를 유지하여 담당자가 팩트별 조건을 적용 |

`02_quality.py`는 품질 문서 5개를 생성합니다. 이 사용법의 보충 안내와 [QUALITY_REVIEW.md](QUALITY_REVIEW.md)는 사람이 확인한 기록이며, 처리 재실행 시 생성 문서가 갱신될 수 있습니다. 완료 결과 확인에는 검증 전용 명령을 사용합니다.

| 변경 일자 (KST) | 내용 |
| --- | --- |
| 2026-11-20 | 기존 결과의 읽기 전용 확인을 우선하도록 구분. 다른 프로젝트 경로 예시·표준 스키마 조건·D-011 승인 범위·manifest 이동 제한 명시 |
