# Silver 단계 기록 (표준화)

[변경 내역·건수](SILVER_CHANGES.md) · [컬럼 사전](SILVER_COLUMNS.md) · [사용법](silver_usage.md) · [데이터 안내](DATA_GUIDE.md)

## 처리 결과

| 항목 | 결과 |
| --- | --- |
| 상태 | 표준화·검증 완료 |
| 코드 | [02_normalize.py](../src/02_normalize.py), [02_normalize_check.py](../src/02_normalize_check.py) |
| 입력 | `D:\IT\mlo3_p2_team3_EB\data\01_bronze`; Bronze만 읽으며 origin은 읽지 않음 |
| 출력 | `D:\IT\mlo3_p2_team3_EB\data\02_silver` 바로 아래 표준화 Parquet 14개; 품질 단계의 clean/·_excluded/는 별도 산출물 |
| 근거 | [mapping_rules.md](../meta/mapping_rules.md)의 이름·타입·코드·복합값·분리 규칙 |
| 파일 개수 | 12개 원천에서 14개 표준 테이블 생성; 기본 공용 규칙은 사용자 확인에 따라 14개 파일 |
| 행 삭제 | 없음. 중복·전표/마권 불일치는 후속 품질 관리 대상으로 보존 |
| 추적 | SOURCE_FILE, INGESTED_AT(KST), _SRC_ROW_NO(1부터), _SRC_BRONZE_FILE(Bronze 상대 경로) |
| 검증 | 117개 중 117개 통과; PARSE_FAIL 0건, OUT_OF_CODE 0건 |
| 규칙서 고정 기대값 비교 | 수행 |

2026-11-20 (KST) 후속 품질 단계의 코드·산출물이 추가되었습니다. 이 문서의 행 수와 검증 수는 **표준화 당시 결과**입니다. 표준화 파일은 보존하며, 품질 처리 이후 상태는 [QUALITY.md](QUALITY.md), 최신 확인은 [QUALITY_REVIEW.md](QUALITY_REVIEW.md)를 참조합니다. 품질 결과 생성 후 읽기 전용 확인은 `src/02_quality_check.py`를 사용합니다.

## 출력 테이블

| 테이블 / 파일명 (.parquet) | 행 수 | 컬럼 수 |
| --- | --- | --- |
| BET_ORDER | 27,907 | 14 |
| BET_TICKET | 523,416 | 16 |
| MBR_MASTER | 4,383 | 10 |
| HR_WEEKLY_SNAPSHOT | 52,642 | 28 |
| TR_WEEKLY_SNAPSHOT | 954 | 18 |
| RC_RACE | 386 | 23 |
| RC_ENTRY | 3,666 | 15 |
| RC_ODDS | 3,666 | 16 |
| RC_RESULT | 3,666 | 21 |
| RC_SALES | 2,702 | 8 |
| RC_SALES_TOTAL | 386 | 7 |
| HR_VET_HIST | 1,488 | 11 |
| HR_VET_TYPE_BRIDGE | 1,664 | 7 |
| RC_CHANGE_EVENT | 149 | 17 |

## 입력 행 보존 대사

| Bronze 대응 테이블 | Bronze 행 수 | Silver 대응 행 수 | 대사 방식 | 결과 |
| --- | --- | --- | --- | --- |
| BET_ORDER | 27,907 | 27,907 | 1:1 | 일치 |
| BET_TICKET | 523,416 | 523,416 | 1:1 | 일치 |
| MBR_MASTER | 4,383 | 4,383 | 1:1 | 일치 |
| HR_WEEKLY_SNAPSHOT | 52,642 | 52,642 | 1:1 | 일치 |
| TR_WEEKLY_SNAPSHOT | 954 | 954 | 1:1 | 일치 |
| RC_RACE | 386 | 386 | 1:1 | 일치 |
| RC_ENTRY | 3,666 | 3,666 | 1:1 | 일치 |
| RC_ODDS | 3,666 | 3,666 | 1:1 | 일치 |
| RC_RESULT | 3,666 | 3,666 | 1:1 | 일치 |
| RC_SALES | 3,088 | 3,088 | 본문+합계 | 일치 |
| HR_VET_HIST | 1,488 | 1,488 | 1:1 | 일치 |
| RC_CHANGE_EVENT | 149 | 149 | 1:1 | 일치 |

HR_VET_TYPE_BRIDGE는 원천 진료명에서 분리한 항목 수와 대사하며 부모 VET_SEQ와 항목 순서를 검증합니다.
원천 테이블의 보존 대사와 별개로 브리지 행이 추가되므로, 14개 파일의 전체 행 합을 원천 행 수와 직접 비교하지 않습니다.

## 기본 공용 규칙의 표준화 내용

다른 --spec을 지정하면 아래 기본 도메인 규칙을 자동 적용하지 않습니다. 실제 적용 내용은 해당 실행의 컬럼 사전·변경 내역을 확인합니다.

| 구분 | 적용 내용 |
| --- | --- |
| 이름 | 공용 UPPER_SNAKE 매핑. 전표 ticket_cnt → TICKET_CNT, 마권 ticket_cnt → UNIT_CNT |
| 날짜/일시 | 혼합 날짜를 date32, 일시를 timestamp[ms, Asia/Seoul], 시각을 time32[ms]로 변환 |
| 숫자 | 건수 int32, 지정 금액 int64, 소수 decimal128. 정밀도 초과 시 반올림하지 않고 실패 |
| 문자열/빈값 | TRIM, 빈 문자열·공백·----- → NULL. 착차 빈칸 FIRST, 채널 빈칸 UNKNOWN은 규칙 예외 |
| 코드 | 승식·상태·채널·지역·성별·등급·날씨·주로 등을 코드화; 코드표 밖 값은 로그와 실패 검증 |
| 복합값 | 체중/증감, 분:초, 분수 착차, 구간 위치, 순위상금, 경주 조건, 도입가격 분리 |
| 매출 | POOL_NM=합계 행을 RC_SALES_TOTAL로 분리; 실제 분리 행 수는 출력·대사 표 참조 |
| 진료명 | VET_NM 원문 유지, VET_SEQ로 개별 진료명 브리지 연결 |
| JSON | 이벤트 중첩 필드를 평탄화; 이벤트별 없는 필드는 NULL 유지 |
| 제외 컬럼 | 규칙서 9장 컬럼은 Silver에서 제외. Bronze와 데이터 사전에 원천·사유 보존 |

상세 내용과 **테이블 / 원천컬럼 / 표준컬럼 / 바꾼내용 / 건수**는 [SILVER_CHANGES.md](SILVER_CHANGES.md)에 기록했습니다.
이 문서는 실행 코드가 실제 집계에서 생성합니다. 다른 데이터를 실행하면 건수도 해당 입력 기준으로 다시 계산됩니다.

## 기록 파일

| 파일 | 내용 |
| --- | --- |
| [data_dictionary.csv](../meta/data_dictionary.csv) | 원천·표준 컬럼/타입·적용 규칙·건수·제외 사유 |
| [silver_value_changes.csv](../meta/silver_value_changes.csv) | 원천값 → 표준값별 전체 변경 건수 |
| [silver_issue_log.csv](../meta/silver_issue_log.csv) | 원천 행 번호·Bronze 파일·NULL/실패 원천값·사유·규칙 ID |
| [silver_column_profile.csv](../meta/silver_column_profile.csv) | 컬럼별 NULL·TRIM·타입·값 변경·실패 집계 |
| [silver_validation.json](../meta/silver_validation.json) | 입력/출력 해시·규칙·검증 결과 |
| [normalization_decisions.csv](../meta/normalization_decisions.csv) | 규칙서 밖 원문 표현의 해석 근거 |

이슈 로그는 컬럼 단위 기록이므로 한 입력 행에 여러 로그가 있을 수 있습니다. 이슈 코드별 기록 수: `{"RULE_NULL": 79806}`.
원천값이 있던 규칙상 NULL은 실패와 구분해 RULE_NULL로 보존합니다. 원천 자체의 빈 문자열과 선택 필드 누락은 컬럼 프로파일에 집계합니다.

## 추가 해석과 확인할 점

| 결정 ID | 관측 원문·조건 | 적용 해석·보존 |
| --- | --- | --- |
| D-NORM-001 | 미출전(ORD_RAW=94/95)이고 PASS_ORD_RAW의 구분자 사이에 숫자가 전혀 없는 '-  -  -  -' | 6개 통과 위치 모두 기록 없음(NULL); 원천과 NULL 사유 보존. 팀 공용 규칙서에 이 표현을 명시할지 검토 필요 |
| TYPE-01 | 규칙서의 DECIMAL 컬럼에 정밀도 미지정 | 기록/구간/함수율 (5,1), 착차 (5,2), JSON 부담중량 (4,1)로 명시. 값이 정확히 표현되지 않으면 실패 |

품질 정제·중복 제거·Gold는 수행하지 않았습니다. 다음 단계에서 행을 제외하면 근거 결정 ID와 별도 제외 데이터를 남겨야 합니다.

## 검증 결과

| 검증 항목 | 기대 | 실제 | 결과 |
| --- | --- | --- | --- |
| BET_ORDER input/output rows | 27907 | 27907 | 통과 |
| BET_ORDER each input row once | True | True | 통과 |
| BET_ORDER source file trace | True | True | 통과 |
| BET_ORDER original file trace | True | True | 통과 |
| BET_ORDER Bronze unchanged | a88e25f740ba9dddcda1f61aa9e500228c56ed5584e1416b92a74725d3e69a56 | a88e25f740ba9dddcda1f61aa9e500228c56ed5584e1416b92a74725d3e69a56 | 통과 |
| BET_TICKET input/output rows | 523416 | 523416 | 통과 |
| BET_TICKET each input row once | True | True | 통과 |
| BET_TICKET source file trace | True | True | 통과 |
| BET_TICKET original file trace | True | True | 통과 |
| BET_TICKET Bronze unchanged | ae968ce27c19da939ad90db34a98107e0546402fc333d684ab07a255094a8178 | ae968ce27c19da939ad90db34a98107e0546402fc333d684ab07a255094a8178 | 통과 |
| MBR_MASTER input/output rows | 4383 | 4383 | 통과 |
| MBR_MASTER each input row once | True | True | 통과 |
| MBR_MASTER source file trace | True | True | 통과 |
| MBR_MASTER original file trace | True | True | 통과 |
| MBR_MASTER Bronze unchanged | 7d55c383f55373d4568cac360e1ec8211a3af8afbdd2dc38fdd48bffcda3264b | 7d55c383f55373d4568cac360e1ec8211a3af8afbdd2dc38fdd48bffcda3264b | 통과 |
| HR_WEEKLY_SNAPSHOT input/output rows | 52642 | 52642 | 통과 |
| HR_WEEKLY_SNAPSHOT each input row once | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT source file trace | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT original file trace | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT Bronze unchanged | c8f74177e5b0138a0fba04ed46deadd824183a1248937cc515a258ce88343bda | c8f74177e5b0138a0fba04ed46deadd824183a1248937cc515a258ce88343bda | 통과 |
| TR_WEEKLY_SNAPSHOT input/output rows | 954 | 954 | 통과 |
| TR_WEEKLY_SNAPSHOT each input row once | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT source file trace | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT original file trace | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT Bronze unchanged | 3e98a7474cce0d928a334bbf499a7cb904bdd3305b054ae3ed1cc54158c60a4f | 3e98a7474cce0d928a334bbf499a7cb904bdd3305b054ae3ed1cc54158c60a4f | 통과 |
| RC_RACE input/output rows | 386 | 386 | 통과 |
| RC_RACE each input row once | True | True | 통과 |
| RC_RACE source file trace | True | True | 통과 |
| RC_RACE original file trace | True | True | 통과 |
| RC_RACE Bronze unchanged | 739f78a02e4882961aabb3f004e36d23724d38a6264058def615baf10323461c | 739f78a02e4882961aabb3f004e36d23724d38a6264058def615baf10323461c | 통과 |
| RC_ENTRY input/output rows | 3666 | 3666 | 통과 |
| RC_ENTRY each input row once | True | True | 통과 |
| RC_ENTRY source file trace | True | True | 통과 |
| RC_ENTRY original file trace | True | True | 통과 |
| RC_ENTRY Bronze unchanged | 587926ff826db487cb84e1ce844e00d6b5fa74524b6ecca14d24cf135a67d778 | 587926ff826db487cb84e1ce844e00d6b5fa74524b6ecca14d24cf135a67d778 | 통과 |
| RC_ODDS input/output rows | 3666 | 3666 | 통과 |
| RC_ODDS each input row once | True | True | 통과 |
| RC_ODDS source file trace | True | True | 통과 |
| RC_ODDS original file trace | True | True | 통과 |
| RC_ODDS Bronze unchanged | c2b89e5db2beb6a87416fa0adc20da0861923b15d8192ab6c3a8eda6d7802361 | c2b89e5db2beb6a87416fa0adc20da0861923b15d8192ab6c3a8eda6d7802361 | 통과 |
| RC_RESULT input/output rows | 3666 | 3666 | 통과 |
| RC_RESULT each input row once | True | True | 통과 |
| RC_RESULT source file trace | True | True | 통과 |
| RC_RESULT original file trace | True | True | 통과 |
| RC_RESULT Bronze unchanged | 400a6eac808ad5081b055bddbb99a1f0569c402a910dca89b605887749c02f7c | 400a6eac808ad5081b055bddbb99a1f0569c402a910dca89b605887749c02f7c | 통과 |
| RC_SALES input/output rows | 3088 | 3088 | 통과 |
| RC_SALES each input row once | True | True | 통과 |
| RC_SALES source file trace | True | True | 통과 |
| RC_SALES original file trace | True | True | 통과 |
| RC_SALES source file trace | True | True | 통과 |
| RC_SALES original file trace | True | True | 통과 |
| RC_SALES Bronze unchanged | dec48efd7ed2f3b92d4f29fd6603cc1c01017b8f5678f71ea45276b51a901c8e | dec48efd7ed2f3b92d4f29fd6603cc1c01017b8f5678f71ea45276b51a901c8e | 통과 |
| HR_VET_HIST input/output rows | 1488 | 1488 | 통과 |
| HR_VET_HIST each input row once | True | True | 통과 |
| HR_VET_HIST source file trace | True | True | 통과 |
| HR_VET_HIST original file trace | True | True | 통과 |
| bridge item count | 1664 | 1664 | 통과 |
| bridge item/order/parent equality | True | True | 통과 |
| bridge parents exist | True | True | 통과 |
| HR_VET_HIST Bronze unchanged | 8d904f4b216cffdc3286098b356333a20806bb3672c3464bf406b19ea7bcf98d | 8d904f4b216cffdc3286098b356333a20806bb3672c3464bf406b19ea7bcf98d | 통과 |
| RC_CHANGE_EVENT input/output rows | 149 | 149 | 통과 |
| RC_CHANGE_EVENT each input row once | True | True | 통과 |
| RC_CHANGE_EVENT source file trace | True | True | 통과 |
| RC_CHANGE_EVENT original file trace | True | True | 통과 |
| RC_CHANGE_EVENT Bronze unchanged | 9c0409884c1820241e3abe5b9d9e00a4449ebaadbfa5da33cf763a2ff7b26c17 | 9c0409884c1820241e3abe5b9d9e00a4449ebaadbfa5da33cf763a2ff7b26c17 | 통과 |
| BET_ORDER column naming | True | True | 통과 |
| BET_ORDER timezones | True | True | 통과 |
| BET_TICKET column naming | True | True | 통과 |
| BET_TICKET timezones | True | True | 통과 |
| MBR_MASTER column naming | True | True | 통과 |
| MBR_MASTER timezones | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT column naming | True | True | 통과 |
| HR_WEEKLY_SNAPSHOT timezones | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT column naming | True | True | 통과 |
| TR_WEEKLY_SNAPSHOT timezones | True | True | 통과 |
| RC_RACE column naming | True | True | 통과 |
| RC_RACE timezones | True | True | 통과 |
| RC_ENTRY column naming | True | True | 통과 |
| RC_ENTRY timezones | True | True | 통과 |
| RC_ODDS column naming | True | True | 통과 |
| RC_ODDS timezones | True | True | 통과 |
| RC_RESULT column naming | True | True | 통과 |
| RC_RESULT timezones | True | True | 통과 |
| RC_SALES column naming | True | True | 통과 |
| RC_SALES timezones | True | True | 통과 |
| RC_SALES_TOTAL column naming | True | True | 통과 |
| RC_SALES_TOTAL timezones | True | True | 통과 |
| HR_VET_HIST column naming | True | True | 통과 |
| HR_VET_HIST timezones | True | True | 통과 |
| HR_VET_TYPE_BRIDGE column naming | True | True | 통과 |
| HR_VET_TYPE_BRIDGE timezones | True | True | 통과 |
| RC_CHANGE_EVENT column naming | True | True | 통과 |
| RC_CHANGE_EVENT timezones | True | True | 통과 |
| PARSE_FAIL | 0 | 0 | 통과 |
| OUT_OF_CODE | 0 | 0 | 통과 |
| BET_ORDER reference rows | 27907 | 27907 | 통과 |
| BET_TICKET reference rows | 523416 | 523416 | 통과 |
| MBR_MASTER reference rows | 4383 | 4383 | 통과 |
| HR_WEEKLY_SNAPSHOT reference rows | 52642 | 52642 | 통과 |
| TR_WEEKLY_SNAPSHOT reference rows | 954 | 954 | 통과 |
| RC_RACE reference rows | 386 | 386 | 통과 |
| RC_ENTRY reference rows | 3666 | 3666 | 통과 |
| RC_ODDS reference rows | 3666 | 3666 | 통과 |
| RC_RESULT reference rows | 3666 | 3666 | 통과 |
| RC_SALES reference rows | 2702 | 2702 | 통과 |
| RC_SALES_TOTAL reference rows | 386 | 386 | 통과 |
| HR_VET_HIST reference rows | 1488 | 1488 | 통과 |
| HR_VET_TYPE_BRIDGE reference rows | 1664 | 1664 | 통과 |
| RC_CHANGE_EVENT reference rows | 149 | 149 | 통과 |
| MBR_MASTER.BIRTH_DT reference NULL | 27 | 27 | 통과 |
| RC_ODDS.WIN_ODDS reference NULL | 22 | 22 | 통과 |
| RC_ODDS.PLC_ODDS reference NULL | 22 | 22 | 통과 |
| RC_RACE.TRACK_MOIST_RT reference NULL | 21 | 21 | 통과 |
| RC_RESULT.FINISH_ORD reference NULL | 22 | 22 | 통과 |
| external horse Y | 25428 | 25428 | 통과 |
| sales totals unique race | 386 | 386 | 통과 |
| multiple diagnoses source rows | 176 | 176 | 통과 |

## 변경 이력

| 일자 (KST) | 작업 | 결과 |
| --- | --- | --- |
| 2026-11-20 | Bronze 입력 기반 표준화·분리·추적·변환 건수 집계 구현 | Silver 평면 저장, docs·meta 실제 수치 기록 |
