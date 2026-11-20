# Silver 품질 관리 작업 기록

[처리 변경·건수](QUALITY_CHANGES.md) · [추가 컬럼](QUALITY_COLUMNS.md) · [사용법](quality_usage.md) · [Gold 입력 계약](GOLD_INPUT_CONTRACT.md) · [결정서](../meta/decision_log.md)

## 적용 범위와 보존

| 항목 | 결과 |
| --- | --- |
| 입력 | data/02_silver/*.parquet 14개; 파일 내용·수정 시각 보존 |
| 유지 결과 | data/02_silver/clean/ 바로 아래 14개 Parquet |
| 완전 중복 제외 | data/02_silver/_excluded/BET_TICKET.parquet, 1,052행 |
| 진료명 의미 병합 | 제외 폴더에 넣지 않음; 별도 병합 로그 2건과 원래 4개 토큰의 계보 보존 |
| 버전 | `DQ-2a7f4bd98578ec01a8d5`; 4명은 같은 dq_manifest.json과 clean 해시를 사용 |
| 이전 작업 | 원천·Bronze·기존 Silver 및 기존 적재/표준화 코드·기록을 수정하지 않음 |
| 새 팀 규칙 중 소급하지 않은 것 | Bronze 전체 문자열/새 추적 컬럼/bronze_load_log.csv와 Silver 이슈 38,305건 기준을 기존 파일에 강제하지 않음 |
| 실행 순서 | D-001: 중복 제외 → 나머지 검사·표시/보정 → 집계별 제외 조건 |
| Gold | 아직 생성하지 않음. 입력 계약만 문서화 |

## 결정별 실제 처리

| 결정 | 문제 | 실측 건수 | 처리 |
| --- | --- | --- | --- |
| D-002 | 마권 완전 중복 | 1,052 | 업무값 비교; 최소 원천 행 번호·동률 Bronze 경로 순; 나머지 _excluded 보관 |
| D-003 | 0원 마권 | 3,632 | clean에 유지; INVALID_YN=Y, BUSINESS_AGG_ELIGIBLE_YN=N |
| D-004 | 늦은 취소 | 1,000장 / 546전표 | 마권·전표 LATE_CANCEL_YN=Y; 삭제·일괄 제외하지 않음 |
| D-004 | 0원이며 늦은 취소 | 0장 / 0전표 | 전체 늦은 취소 검사에는 포함, ZERO_LATE_CANCEL_YN으로 교집합 표시 |
| D-005 | 빈 마명 보정 | 1,560 | 출전표의 경주일·경주번호·마번이 정확히 1행 연결될 때만; HR_NM_BEFORE와 근거 보존 |
| D-006 | 전표·마권 불일치 | 93전표 | HEADER_MISMATCH_YN=Y; 수치 보정 안 함 |
| D-006 | 원전표 없는 취소 | 644전표 | ORIG_MISSING_YN=Y; 원전표 추정 연결 안 함 |
| D-007 | 진료 조 불일치 / 이전 스냅샷 없음 | 11 / 71 | 전체 진료 유지; 해당 조·스냅샷 분석에서 확인 필요 |
| D-011 | 일,열사병 유형 의미 병합 | 2진료 | parent VET_NM 원문 보존; 브리지 일·열사병 단일 유형 |
| D-011 | 브리지 / 복수 유형 진료 | 1,664 → 1,662행 / 176 → 174건 | 중복 제외가 아닌 의미 병합; 별도 감소 대사 |

위 품질 건수는 모두 완전 중복을 먼저 제거한 뒤 측정했습니다. 전표 불일치 검사는 0원 마권을 포함한 전체 중복 제거 상세로 대사했습니다.
전표의 장수는 상세 행 수이며 UNIT_CNT(구좌 수)의 합이 아닙니다. 전표 늦은 취소 건수는 고유 ORDER_NO 수입니다.
늦은 취소 금액의 부호 있는 합은 **-4,162,700원**입니다. 이 금액을 절댓값으로 바꾸거나 원천 거래 금액을 수정하지 않았습니다.

## 테이블별 행 수 대사

| 테이블 | 표준화 입력 | clean 유지 | _excluded 완전 중복 | 의미 병합 감소 | 결과 |
| --- | --- | --- | --- | --- | --- |
| BET_ORDER | 27,907 | 27,907 | 0 | 0 | 일치 |
| BET_TICKET | 523,416 | 522,364 | 1,052 | 0 | 일치 |
| MBR_MASTER | 4,383 | 4,383 | 0 | 0 | 일치 |
| HR_WEEKLY_SNAPSHOT | 52,642 | 52,642 | 0 | 0 | 일치 |
| TR_WEEKLY_SNAPSHOT | 954 | 954 | 0 | 0 | 일치 |
| RC_RACE | 386 | 386 | 0 | 0 | 일치 |
| RC_ENTRY | 3,666 | 3,666 | 0 | 0 | 일치 |
| RC_ODDS | 3,666 | 3,666 | 0 | 0 | 일치 |
| RC_RESULT | 3,666 | 3,666 | 0 | 0 | 일치 |
| RC_SALES | 2,702 | 2,702 | 0 | 0 | 일치 |
| RC_SALES_TOTAL | 386 | 386 | 0 | 0 | 일치 |
| HR_VET_HIST | 1,488 | 1,488 | 0 | 0 | 일치 |
| HR_VET_TYPE_BRIDGE | 1,664 | 1,662 | 0 | 2 | 일치 |
| RC_CHANGE_EVENT | 149 | 149 | 0 | 0 | 일치 |

- 일반 테이블: 표준화 입력 = clean + _excluded. 입력 행은 정확히 한쪽에만 있습니다.
- 진료명 브리지: **1,664 = 1,662 + 의미 병합 감소 2**. 브리지 _excluded는 0입니다.
- 브리지는 clean 행 ID와 병합 흡수 행 ID가 서로 겹치지 않으면서 원래 1,664개 입력 항목을 모두 덮는지 검사했습니다.
- 2개 병합 기록 각각에 원래 두 토큰의 행 ID·값·순번과 결과 행 ID를 남겼습니다. 원래 표준화 파일도 보존됩니다.

## 처리 로그 집계

| 테이블 | 규칙 ID | 결정 ID | 처리 | 로그 수 |
| --- | --- | --- | --- | --- |
| BET_ORDER | DQ-R03 | D-006 | MARK | 644 |
| BET_ORDER | DQ-S01 | D-006 | MARK | 93 |
| BET_ORDER | DQ-T02 | D-004 | MARK | 546 |
| BET_TICKET | DQ-C01 | D-005 | CORRECT | 1,560 |
| BET_TICKET | DQ-R03 | D-006 | MARK | 1,361 |
| BET_TICKET | DQ-S01 | D-006 | MARK | 2,681 |
| BET_TICKET | DQ-T01 | D-004 | MARK | 1,000 |
| BET_TICKET | DQ-U01 | D-002 | EXCLUDE | 1,052 |
| BET_TICKET | DQ-V01 | D-003 | MARK | 3,632 |
| HR_VET_HIST | DQ-R05 | D-007 | MARK | 71 |
| HR_VET_HIST | DQ-S04 | D-007 | MARK | 11 |
| HR_VET_TYPE_BRIDGE | DQ-S05 | D-011 | MERGE | 4 |

총 12,655줄입니다. 같은 입력 행에 여러 규칙이 적용되거나 전표 플래그를 마권에 전파하면 로그가 여러 줄 생깁니다. 로그 수를 고유 전표 수나 위반 건수 합계로 해석하지 않습니다.

## 보존·측정 기준

| 구분 | 기준 |
| --- | --- |
| 완전 중복 | _로 시작하는 추적 컬럼, SRC_ 컬럼, SOURCE_FILE, INGESTED_AT을 빼고 업무값 전체 비교. TICKET_SEQ는 포함 |
| 선택 순서 | _SRC_ROW_NO 최소 → _SRC_BRONZE_FILE 오름차순 → 표준화 파일 안의 입력 순서 |
| 늦은 취소 | 전표 CANCEL + 마권 CANCEL, 취소 SALE_DTM >= 해당 마권 RC_RACE.START_DTM |
| 빈 마명 | NULL만 대상. 유일한 출전표 연결이 아니면 추측 보정하지 않고 원래 값을 유지 |
| 원전표 없음 | 취소 ORIG_ORDER_NO가 유효한 SALE 전표에 연결되지 않음; NULL 포함 |
| 진료 비교 | 동일 마명의 진료일보다 엄격히 이전인 최신 스냅샷. 동일 날짜도 제외 |
| 말 개체 | 이름 기반 과거 스냅샷 후보 매칭이며 공식 말 ID 확정이 아님. Gold에서 개체 검증 별도 필요 |
| 예전 이슈 로그 | 기존 silver_issue_log.csv는 보존. QC 건수는 dq_log.csv로 분리 |
| 재실행 | 같은 내용은 수정하지 않음. 기존 clean/_excluded와 다른 결과는 덮어쓰지 않고 별도 버전 경로 요구 |

## 검증 결과

| 검증 | 기대 | 실제 | 결과 |
| --- | --- | --- | --- |
| cancel order vs ticket status | True | True | 통과 |
| BET_ORDER row conservation | 27907 | 27907 | 통과 |
| BET_ORDER exclusive disposition | True | True | 통과 |
| BET_ORDER exact row coverage | True | True | 통과 |
| BET_ORDER kept row ids unique | 27907 | 27907 | 통과 |
| BET_ORDER unmodified original fields | True | True | 통과 |
| BET_ORDER lineage present | True | True | 통과 |
| BET_TICKET row conservation | 523416 | 523416 | 통과 |
| BET_TICKET exclusive disposition | True | True | 통과 |
| BET_TICKET exact row coverage | True | True | 통과 |
| BET_TICKET kept row ids unique | 522364 | 522364 | 통과 |
| BET_TICKET unmodified original fields | True | True | 통과 |
| BET_TICKET lineage present | True | True | 통과 |
| BET_TICKET unmodified original fields | True | True | 통과 |
| BET_TICKET lineage present | True | True | 통과 |
| MBR_MASTER row conservation | 4383 | 4383 | 통과 |
| MBR_MASTER exclusive disposition | True | True | 통과 |
| MBR_MASTER exact row coverage | True | True | 통과 |
| MBR_MASTER kept row ids unique | 4383 | 4383 | 통과 |
| MBR_MASTER unmodified original fields | True | True | 통과 |
| MBR_MASTER lineage present | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT row conservation | 52642 | 52642 | 통과 |
| HR_WEEKLY_SNAPSHOT exclusive disposition | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT exact row coverage | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT kept row ids unique | 52642 | 52642 | 통과 |
| HR_WEEKLY_SNAPSHOT unmodified original fields | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT lineage present | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT row conservation | 954 | 954 | 통과 |
| TR_WEEKLY_SNAPSHOT exclusive disposition | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT exact row coverage | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT kept row ids unique | 954 | 954 | 통과 |
| TR_WEEKLY_SNAPSHOT unmodified original fields | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT lineage present | True | True | 통과 |
| RC_RACE row conservation | 386 | 386 | 통과 |
| RC_RACE exclusive disposition | True | True | 통과 |
| RC_RACE exact row coverage | True | True | 통과 |
| RC_RACE kept row ids unique | 386 | 386 | 통과 |
| RC_RACE unmodified original fields | True | True | 통과 |
| RC_RACE lineage present | True | True | 통과 |
| RC_ENTRY row conservation | 3666 | 3666 | 통과 |
| RC_ENTRY exclusive disposition | True | True | 통과 |
| RC_ENTRY exact row coverage | True | True | 통과 |
| RC_ENTRY kept row ids unique | 3666 | 3666 | 통과 |
| RC_ENTRY unmodified original fields | True | True | 통과 |
| RC_ENTRY lineage present | True | True | 통과 |
| RC_ODDS row conservation | 3666 | 3666 | 통과 |
| RC_ODDS exclusive disposition | True | True | 통과 |
| RC_ODDS exact row coverage | True | True | 통과 |
| RC_ODDS kept row ids unique | 3666 | 3666 | 통과 |
| RC_ODDS unmodified original fields | True | True | 통과 |
| RC_ODDS lineage present | True | True | 통과 |
| RC_RESULT row conservation | 3666 | 3666 | 통과 |
| RC_RESULT exclusive disposition | True | True | 통과 |
| RC_RESULT exact row coverage | True | True | 통과 |
| RC_RESULT kept row ids unique | 3666 | 3666 | 통과 |
| RC_RESULT unmodified original fields | True | True | 통과 |
| RC_RESULT lineage present | True | True | 통과 |
| RC_SALES row conservation | 2702 | 2702 | 통과 |
| RC_SALES exclusive disposition | True | True | 통과 |
| RC_SALES exact row coverage | True | True | 통과 |
| RC_SALES kept row ids unique | 2702 | 2702 | 통과 |
| RC_SALES unmodified original fields | True | True | 통과 |
| RC_SALES lineage present | True | True | 통과 |
| RC_SALES_TOTAL row conservation | 386 | 386 | 통과 |
| RC_SALES_TOTAL exclusive disposition | True | True | 통과 |
| RC_SALES_TOTAL exact row coverage | True | True | 통과 |
| RC_SALES_TOTAL kept row ids unique | 386 | 386 | 통과 |
| RC_SALES_TOTAL unmodified original fields | True | True | 통과 |
| RC_SALES_TOTAL lineage present | True | True | 통과 |
| HR_VET_HIST row conservation | 1488 | 1488 | 통과 |
| HR_VET_HIST exclusive disposition | True | True | 통과 |
| HR_VET_HIST exact row coverage | True | True | 통과 |
| HR_VET_HIST kept row ids unique | 1488 | 1488 | 통과 |
| HR_VET_HIST unmodified original fields | True | True | 통과 |
| HR_VET_HIST lineage present | True | True | 통과 |
| HR_VET_TYPE_BRIDGE row conservation | 1664 | 1664 | 통과 |
| HR_VET_TYPE_BRIDGE exclusive disposition | True | True | 통과 |
| HR_VET_TYPE_BRIDGE exact row coverage | True | True | 통과 |
| HR_VET_TYPE_BRIDGE kept row ids unique | 1662 | 1662 | 통과 |
| HR_VET_TYPE_BRIDGE unmodified original fields | True | True | 통과 |
| HR_VET_TYPE_BRIDGE lineage present | True | True | 통과 |
| RC_CHANGE_EVENT row conservation | 149 | 149 | 통과 |
| RC_CHANGE_EVENT exclusive disposition | True | True | 통과 |
| RC_CHANGE_EVENT exact row coverage | True | True | 통과 |
| RC_CHANGE_EVENT kept row ids unique | 149 | 149 | 통과 |
| RC_CHANGE_EVENT unmodified original fields | True | True | 통과 |
| RC_CHANGE_EVENT lineage present | True | True | 통과 |
| only approved unique-entry name repairs | True | True | 통과 |
| name repair counts match actual changed values | 1560 | 1560 | 통과 |
| only approved bridge type corrections | True | True | 통과 |
| bridge correction count equals merged records | 2 | 2 | 통과 |
| ticket business PK after dedup | 0 | 0 | 통과 |
| zero tickets retained | 3632 | 3632 | 통과 |
| business eligibility excludes exactly zero | True | True | 통과 |
| late cancellations retained | 1000 | 1000 | 통과 |
| unique late orders | 546 | 546 | 통과 |
| bridge input to output plus semantic reduction | 1664 | 1664 | 통과 |
| only full duplicates in excluded | ['BET_TICKET'] | ['BET_TICKET'] | 통과 |
| bridge parent exists | True | True | 통과 |
| bridge parent/type unique | 0 | 0 | 통과 |
| D-011 one canonical type per record | True | True | 통과 |
| medical rows retained | 1488 | 1488 | 통과 |
| reference duplicate_excluded | 1052 | 1052 | 통과 |
| reference zero_tickets | 3632 | 3632 | 통과 |
| reference late_tickets | 1000 | 1000 | 통과 |
| reference late_orders | 546 | 546 | 통과 |
| reference zero_late_tickets | 0 | 0 | 통과 |
| reference filled_names | 1560 | 1560 | 통과 |
| reference header_mismatch_orders | 93 | 93 | 통과 |
| reference orig_missing_orders | 644 | 644 | 통과 |
| reference vet_group_mismatch | 11 | 11 | 통과 |
| reference vet_no_prior | 71 | 71 | 통과 |
| reference vet_merge_records | 2 | 2 | 통과 |
| reference bridge_rows | 1662 | 1662 | 통과 |
| reference multiple_vet_records | 174 | 174 | 통과 |
| BET_ORDER source hash preserved | 310b4810c7442ce08f6a4a4548e2763e27d8b2c857b9d49b5d65cc6e700e5852 | 310b4810c7442ce08f6a4a4548e2763e27d8b2c857b9d49b5d65cc6e700e5852 | 통과 |
| BET_ORDER source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| BET_TICKET source hash preserved | 529283ac76609297734f221c89181f22d6e74e3f3f415b737881ec789fa90a4c | 529283ac76609297734f221c89181f22d6e74e3f3f415b737881ec789fa90a4c | 통과 |
| BET_TICKET source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| MBR_MASTER source hash preserved | 98a49f09368569bf2327a918bc48f324a7483e7d014ed09326d114a3be30fd57 | 98a49f09368569bf2327a918bc48f324a7483e7d014ed09326d114a3be30fd57 | 통과 |
| MBR_MASTER source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| HR_WEEKLY_SNAPSHOT source hash preserved | 933e730598557cac8eaf2b0d4aebc7a1fede90b8f8d7055386ccf13f63e64e57 | 933e730598557cac8eaf2b0d4aebc7a1fede90b8f8d7055386ccf13f63e64e57 | 통과 |
| HR_WEEKLY_SNAPSHOT source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| TR_WEEKLY_SNAPSHOT source hash preserved | 3c5517a6da89974133d921772daf423948b18fe12ae2bdedae2f2aa1b521d90d | 3c5517a6da89974133d921772daf423948b18fe12ae2bdedae2f2aa1b521d90d | 통과 |
| TR_WEEKLY_SNAPSHOT source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_RACE source hash preserved | 1ec0724ed0812ca1abe3ea2f825cd606eff7fb3b0d12562f58b5f6d218c3f30c | 1ec0724ed0812ca1abe3ea2f825cd606eff7fb3b0d12562f58b5f6d218c3f30c | 통과 |
| RC_RACE source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_ENTRY source hash preserved | a163429e0c83a20affcb6cd213c285317c988d3825023351dc2dfc3f6d5ae7e2 | a163429e0c83a20affcb6cd213c285317c988d3825023351dc2dfc3f6d5ae7e2 | 통과 |
| RC_ENTRY source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_ODDS source hash preserved | 86faa9f7bf489653be8b146b76828bcd82784d5062e8cd4fa7febe0b926018f7 | 86faa9f7bf489653be8b146b76828bcd82784d5062e8cd4fa7febe0b926018f7 | 통과 |
| RC_ODDS source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_RESULT source hash preserved | 63ae201fce390773d3730d60e49cb876b0b846cfa404368f2761f8352f79682d | 63ae201fce390773d3730d60e49cb876b0b846cfa404368f2761f8352f79682d | 통과 |
| RC_RESULT source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_SALES source hash preserved | 2219713fe57baecad48f133c44d4bab4cb30beccd811abbe894ae3b36dc222b2 | 2219713fe57baecad48f133c44d4bab4cb30beccd811abbe894ae3b36dc222b2 | 통과 |
| RC_SALES source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_SALES_TOTAL source hash preserved | 84dbc5086f108d1fa04c612e4174be24d38354959ce047aac9d1b0ece90aeb58 | 84dbc5086f108d1fa04c612e4174be24d38354959ce047aac9d1b0ece90aeb58 | 통과 |
| RC_SALES_TOTAL source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| HR_VET_HIST source hash preserved | 33e67904421c456e327a582667466d4f6707273cdafe52540601cd9af7e73c97 | 33e67904421c456e327a582667466d4f6707273cdafe52540601cd9af7e73c97 | 통과 |
| HR_VET_HIST source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| HR_VET_TYPE_BRIDGE source hash preserved | fc4b33acd78a4d0647d5709ea46fd27b3dc68f084d0e9b2f6ae5aeddb32786ce | fc4b33acd78a4d0647d5709ea46fd27b3dc68f084d0e9b2f6ae5aeddb32786ce | 통과 |
| HR_VET_TYPE_BRIDGE source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |
| RC_CHANGE_EVENT source hash preserved | 9bc6a02cf50585976ea0517238b48eea0d58b288c40694761b1d9e9a7b2798bb | 9bc6a02cf50585976ea0517238b48eea0d58b288c40694761b1d9e9a7b2798bb | 통과 |
| RC_CHANGE_EVENT source mtime preserved | 1795157074000000000 | 1795157074000000000 | 통과 |

## 변경 이력

| 일자 (KST) | 작업 |
| --- | --- |
| 2026-11-20 | D-001~D-012 적용. 기존 Bronze/Silver 보존, 품질 clean·중복 제외·진료명 의미 병합 계보와 대사 구현 |
