# 품질 관리 추가 컬럼

[작업 기록](QUALITY.md) · [변경 내역](QUALITY_CHANGES.md) · [Gold 입력](GOLD_INPUT_CONTRACT.md)

기존 컬럼 타입은 유지했습니다. 수정 허용한 원천 업무 컬럼은 마권 HR_NM과 브리지 VET_TYPE_NM뿐이며 원래 값은 별도 컬럼과 로그에 보존합니다.
표준화 결과 파일 자체는 수정하지 않았습니다.

## BET_ORDER

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| LATE_CANCEL_YN | string | 마권은 출발 이상 시각의 취소, 전표는 하나라도 해당하면 Y | 0 | [{"counts": 27361, "values": "N"}, {"counts": 546, "values": "Y"}] |
| ZERO_LATE_CANCEL_YN | string | 0원이며 늦은 취소인 교집합; 전표는 하나라도 해당하면 Y | 0 | [{"counts": 27907, "values": "N"}] |
| HEADER_MISMATCH_YN | string | 전표 장수/금액과 중복 제거 상세가 다름; 마권은 전표 플래그 상속 | 0 | [{"counts": 27814, "values": "N"}, {"counts": 93, "values": "Y"}] |
| ORIG_MISSING_YN | string | 취소가 유효 원구매 SALE 전표에 연결되지 않음; 마권은 전표 플래그 상속 | 0 | [{"counts": 644, "values": "Y"}, {"counts": 27263, "values": "N"}] |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## BET_TICKET

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| INVALID_YN | string | 0원 마권이면 Y; 오류 집계에는 포함 | 0 | [{"counts": 518732, "values": "N"}, {"counts": 3632, "values": "Y"}] |
| BUSINESS_AGG_ELIGIBLE_YN | string | 0원 기준 업무 집계 사용 가능 여부; Gold의 50대·단승 등 적격 조건과는 별개 | 0 | [{"counts": 518732, "values": "Y"}, {"counts": 3632, "values": "N"}] |
| LATE_CANCEL_YN | string | 마권은 출발 이상 시각의 취소, 전표는 하나라도 해당하면 Y | 0 | [{"counts": 521364, "values": "N"}, {"counts": 1000, "values": "Y"}] |
| ZERO_LATE_CANCEL_YN | string | 0원이며 늦은 취소인 교집합; 전표는 하나라도 해당하면 Y | 0 | [{"counts": 522364, "values": "N"}] |
| HR_NM_BEFORE | string | 보정 전 마명; 원래 NULL도 보존 | 1560 |  |
| HR_NM_FILLED_YN | string | 출전표 유일 연결로 보정한 경우 Y | 0 | [{"counts": 520804, "values": "N"}, {"counts": 1560, "values": "Y"}] |
| HR_NM_FILL_STATUS_CD | string | NOT_NEEDED / FILLED_UNIQUE_ENTRY / NO_MATCH / AMBIGUOUS / ENTRY_NAME_MISSING | 0 | [{"counts": 520804, "values": "NOT_NEEDED"}, {"counts": 1560, "values": "FILLED_UNIQUE_ENTRY"}] |
| HEADER_MISMATCH_YN | string | 전표 장수/금액과 중복 제거 상세가 다름; 마권은 전표 플래그 상속 | 0 | [{"counts": 519683, "values": "N"}, {"counts": 2681, "values": "Y"}] |
| ORIG_MISSING_YN | string | 취소가 유효 원구매 SALE 전표에 연결되지 않음; 마권은 전표 플래그 상속 | 0 | [{"counts": 1361, "values": "Y"}, {"counts": 521003, "values": "N"}] |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## MBR_MASTER

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## HR_WEEKLY_SNAPSHOT

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## TR_WEEKLY_SNAPSHOT

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_RACE

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_ENTRY

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_ODDS

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_RESULT

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_SALES

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_SALES_TOTAL

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## HR_VET_HIST

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| GRP_MISMATCH_YN | string | 진료 조와 직전 과거 스냅샷 조가 다름; 진료 조는 유지 | 0 | [{"counts": 1477, "values": "N"}, {"counts": 11, "values": "Y"}] |
| HORSE_MATCH_STATUS_CD | string | PRIOR_NAME_SNAPSHOT_FOUND / UNVERIFIED; 공식 말 ID 검증을 뜻하지 않음 | 0 | [{"counts": 71, "values": "UNVERIFIED"}, {"counts": 1417, "values": "PRIOR_NAME_SNAPSHOT_FOUND"}] |
| PRIOR_SNAPSHOT_DT | date32[day] | 진료일보다 엄격히 이전인 채택 스냅샷 날짜 | 71 |  |
| SNAPSHOT_TR_GRP_NO | string | 비교에 사용한 과거 스냅샷 조 번호 | 71 |  |
| MEDICAL_ANALYSIS_REVIEW_YN | string | 조/스냅샷별 분석 확인 필요. 전체 진료 집계에는 포함 | 0 | [{"counts": 82, "values": "Y"}, {"counts": 1406, "values": "N"}] |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## HR_VET_TYPE_BRIDGE

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| VET_TYPE_NM_BEFORE | string | 의미 병합 전 진료명 토큰 | 0 |  |
| VET_TYPE_CORRECTED_YN | string | 일·열사병 단일 유형으로 보정한 결과 행 Y | 0 | [{"counts": 1660, "values": "N"}, {"counts": 2, "values": "Y"}] |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |

## RC_CHANGE_EVENT

| 추가 컬럼 | 타입 | 의미 | NULL 수 | 상태별 건수 |
| --- | --- | --- | --- | --- |
| _DQ_INPUT_ROW_NO | int64 | 표준화 입력 파일 내부 1부터 시작하는 행 번호 | 0 |  |
| _DQ_ROW_ID | string | 테이블명+표준화 입력 행 번호; 병합 전 항목을 구분 | 0 |  |
| TABLE_NM | string | 해당 테이블명 | 0 |  |
| RULE_ID | string | 적용 규칙 ID 목록; 미위반 보존은 DQ-R00 | 0 |  |
| DECISION_ID | string | 근거 결정 ID 목록 | 0 |  |
| ACTION | string | KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능 | 0 |  |
| REASON | string | 처리 또는 보존 근거 | 0 |  |
| _DQ_DATASET_VERSION | string | 공통 clean 버전; 입력/결정/실제 결과 내용 기반 | 0 |  |
