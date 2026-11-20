# 품질 관리 변경 내역과 건수

[작업 기록](QUALITY.md) · [추가 컬럼](QUALITY_COLUMNS.md) · [결정서](../meta/decision_log.md)

행 제외·표시·보정·의미 병합을 구분한 실제 집계입니다. 같은 행은 여러 규칙에 포함될 수 있습니다.
마명별 보정 등 값이 많은 항목은 대표 5개와 전체 건수를 표시하며 [dq_value_changes.csv](../meta/dq_value_changes.csv)에 모든 값별 건수를 기록합니다.
OLD/NEW가 null인 EXCLUDE는 값 삭제가 아니라 원래 행 전체의 별도 보관입니다. MERGE는 완전 중복 제외가 아닌 D-011 의미 병합입니다.

| 테이블 | 원천컬럼 | 처리 후 컬럼/위치 | 바꾼내용·값별 건수 | 총 처리 건수 | 규칙 ID | 결정 ID |
| --- | --- | --- | --- | --- | --- | --- |
| BET_ORDER | HEADER_MISMATCH_YN | HEADER_MISMATCH_YN | MARK<br>`"N"` → `"Y"` (93) | 93 | DQ-S01 | D-006 |
| BET_ORDER | LATE_CANCEL_YN | LATE_CANCEL_YN | MARK<br>`"N"` → `"Y"` (546) | 546 | DQ-T02 | D-004 |
| BET_ORDER | ORIG_MISSING_YN | ORIG_MISSING_YN | MARK<br>`"N"` → `"Y"` (644) | 644 | DQ-R03 | D-006 |
| BET_TICKET | (업무값 전체) | _excluded | EXCLUDE<br>`null` → `null` (1,052) | 1,052 | DQ-U01 | D-002 |
| BET_TICKET | HEADER_MISMATCH_YN | HEADER_MISMATCH_YN | MARK<br>`"N"` → `"Y"` (2,681) | 2,681 | DQ-S01 | D-006 |
| BET_TICKET | HR_NM | HR_NM | CORRECT<br>`null` → `"슈퍼스타"` (12)<br>`null` → `"와흘호"` (12)<br>`null` → `"걸싸게"` (11)<br>`null` → `"전승맨"` (11)<br>`null` → `"청룡바람"` (11)<br>그 외 537개 값은 dq_value_changes.csv에 전체 기록 | 1,560 | DQ-C01 | D-005 |
| BET_TICKET | INVALID_YN | INVALID_YN | MARK<br>`"N"` → `"Y"` (3,632) | 3,632 | DQ-V01 | D-003 |
| BET_TICKET | LATE_CANCEL_YN | LATE_CANCEL_YN | MARK<br>`"N"` → `"Y"` (1,000) | 1,000 | DQ-T01 | D-004 |
| BET_TICKET | ORIG_MISSING_YN | ORIG_MISSING_YN | MARK<br>`"N"` → `"Y"` (1,361) | 1,361 | DQ-R03 | D-006 |
| HR_VET_HIST | GRP_MISMATCH_YN | GRP_MISMATCH_YN | MARK<br>`"N"` → `"Y"` (11) | 11 | DQ-S04 | D-007 |
| HR_VET_HIST | HORSE_MATCH_STATUS_CD | HORSE_MATCH_STATUS_CD | MARK<br>`null` → `"UNVERIFIED"` (71) | 71 | DQ-R05 | D-007 |
| HR_VET_TYPE_BRIDGE | VET_TYPE_NM | VET_TYPE_NM | MERGE<br>`"열사병"` → `"일·열사병"` (2)<br>`"일"` → `"일·열사병"` (2) | 4 | DQ-S05 | D-011 |
