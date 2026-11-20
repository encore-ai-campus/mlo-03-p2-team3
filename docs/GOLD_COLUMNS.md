# Gold 컬럼 사전

2026-11-20 (KST). 실제 Parquet 스키마와 NULL 실측 기준. 데이터 파일명은 대문자이며 논리 테이블명·컬럼명은 기존 소문자를 유지합니다. 요약은 meta/WIN_RATE_CANCEL_SUMMARY.csv에 저장하며 해당 타입은 계산 시 논리형, NULL은 CSV 빈칸입니다. [작업 기록](GOLD.md).

## dim_member

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| member_key | string | True | 0 | 회원번호 기반 내부 대리키; UNKNOWN 미상 |
| member_no | string | False | 1 | 표준 회원 업무키 |
| birth_date | date32[day] | False | 28 | 달력 날짜; 원천 또는 해당 사건 기준 |
| join_date | date32[day] | False | 1 | 달력 날짜; 원천 또는 해당 사건 기준 |
| source_row_id | string | False | 1 | clean의 _DQ_ROW_ID; 해당 입력 처분/감사 테이블 PK |

## dim_horse

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| horse_key | string | True | 0 | 내부 마명·생일 키. 공식 마번 아님; 불명은 UNKNOWN |
| horse_name | string | False | 1 | 표준 마명 |
| birth_date | date32[day] | False | 1 | 달력 날짜; 원천 또는 해당 사건 기준 |
| sire_name | string | False | 1 | 부마명 |
| dam_name | string | False | 6 | 모마명 |
| identity_status | string | False | 0 | INTERNAL_NAME_BIRTH_CONSISTENT는 내부 식별 일관성 확인; 공식 개체 검증 아님 |

## dim_race

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| race_id | string | True | 0 | MEET_CD·RC_DT·RC_NO 기반 내부 대리키; UNKNOWN 미상 |
| race_date | date32[day] | False | 1 | 달력 날짜; 원천 또는 해당 사건 기준 |
| race_no | int32 | False | 1 | 경주번호 |
| meet_cd | string | False | 1 | 공용 경마장 코드 |
| race_start_at | timestamp[ms, tz=Asia/Seoul] | False | 1 | Asia/Seoul KST 사건 시각 |
| distance_m | int32 | False | 1 | 경주 거리(m) |
| race_grade | string | False | 1 | 공용 등급 코드 |
| source_row_id | string | False | 1 | clean의 _DQ_ROW_ID; 해당 입력 처분/감사 테이블 PK |

## dim_date

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| date_key | int32 | True | 0 | YYYYMMDD 달력 키, 미상은 0 |
| calendar_date | date32[day] | False | 1 | 달력 날짜; 원천 또는 해당 사건 기준 |
| year | int32 | False | 1 | 연도 |
| quarter | int32 | False | 1 | 분기1~4 |
| month | int32 | False | 1 | 월1~12 |
| day_of_month | int32 | False | 1 | 일1~31 |
| weekday | int32 | False | 1 | ISO 요일: 월1~일7 |
| year_month | string | False | 1 | YYYY-MM |

## dim_channel

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| channel_key | string | True | 0 | CHNL_CD·OTB_BRANCH_NO 기반 내부 대리키; UNKNOWN 미상 |
| channel_cd | string | False | 0 | 표준 채널+장외지점 코드; OTB01 등 |
| channel_group | string | False | 0 | 공용 CHNL_CD |
| branch_no | string | False | 3 | 장외지점 번호 |
| channel_name | string | False | 0 | 현장/앱/장외/미상 표시명 |

## fct_bet_selection_cancel_50s

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| fact_id | string | True | 0 | 原구매 전표·경주일·경주번호·WIN·출주번호의 내부 해시 |
| original_order_no | string | False | 0 | 원구매 전표 식별자; 퇴화 차원 |
| member_key | string | False | 0 | 회원번호 기반 내부 대리키; UNKNOWN 미상 |
| horse_key | string | False | 0 | 내부 마명·생일 키. 공식 마번 아님; 불명은 UNKNOWN |
| race_id | string | False | 0 | MEET_CD·RC_DT·RC_NO 기반 내부 대리키; UNKNOWN 미상 |
| channel_key | string | False | 0 | CHNL_CD·OTB_BRANCH_NO 기반 내부 대리키; UNKNOWN 미상 |
| purchase_date_key | int32 | False | 0 | dim_date 역할별 FK; 미상/취소 없음은 0 |
| cancel_date_key | int32 | False | 0 | dim_date 역할별 FK; 미상/취소 없음은 0 |
| race_date_key | int32 | False | 0 | dim_date 역할별 FK; 미상/취소 없음은 0 |
| snapshot_date_key | int32 | False | 0 | dim_date 역할별 FK; 미상/취소 없음은 0 |
| bet_type_cd | string | False | 0 | 승식 WIN 고정 |
| chul_no | int32 | False | 0 | 해당 경주의 출주번호; 말 영구 속성 아님 |
| age_at_purchase | int32 | False | 0 | 원구매일 기준 생일을 반영한 만 나이 |
| purchase_at | timestamp[ms, tz=Asia/Seoul] | False | 0 | Asia/Seoul KST 사건 시각 |
| horse_age_at_race | int32 | False | 0 | 출전표의 경주 당시 말 나이 |
| horse_sex_at_race | string | False | 0 | 출전표의 경주 당시 성별 코드 |
| purchase_detail_count | int64 | False | 0 | 묶음에 포함된 원구매 상세 행 수 |
| purchase_stake_units | int64 | False | 0 | 원구매 상세 UNIT_CNT 합; 마권 장수와 다름 |
| purchase_amount_krw | int64 | False | 0 | 0원 상세를 제외한 원구매 상세 금액 합(원); 헤더 금액 아님 |
| horse_snapshot_date | date32[day] | False | 0 | 구매일보다 엄격히 이전인 최신 채택 관측일 |
| snapshot_age_days | int32 | False | 0 | 구매일과 채택 스냅샷일의 날짜 차 |
| recent1y_starts | int64 | False | 0 | 채택 과거 스냅샷의 출전 수 |
| recent1y_wins | int64 | False | 0 | 채택 과거 스냅샷의 1착 수 |
| recent1y_win_rate | double | False | 1493 | 채택 스냅샷 최근1년 1착수/출전수; 출전0 또는 불량 전적은 NULL |
| recent1y_win_rate_band | string | False | 0 | 0%, (0,5%], (5,10%], (10,20%], >20%; 계산 불가 UNKNOWN |
| career_starts | int64 | False | 0 | 채택 과거 스냅샷의 출전 수 |
| career_wins | int64 | False | 0 | 채택 과거 스냅샷의 1착 수 |
| career_win_rate | double | False | 1402 | 채택 스냅샷 통산 1착수/출전수; 출전0은 NULL |
| has_verified_customer_cancel | int32 | False | 102 | 1 확인 취소, 0 관측 확인취소 없음, NULL 불명확 |
| cancel_label_status | string | False | 0 | AMBIGUOUS / VERIFIED_CANCEL / NO_CANCEL_OBSERVED |
| cancel_transaction_count | int64 | False | 0 | 확정 연결 후보의 고유 비영 취소 전표 수; 검증 실패 건 포함 |
| raw_linked_cancel_amount_krw | int64 | False | 0 | 회원·원전표·선택 연결 후보의 비영 취소금액 절댓값 합; 불량 건 포함 |
| verified_cancel_amount_krw | int64 | False | 0 | 행별 연결 검증을 통과한 취소 상세 절댓값 합; 묶음별 초과·불명확이면 분석에서 제외 |
| verified_cancel_stake_units | int64 | False | 0 | 행별 연결 검증 통과 취소 구좌 절댓값 합 |
| first_cancel_at | timestamp[ms, tz=Asia/Seoul] | False | 40187 | 행별 검증 통과 취소의 최초 KST 시각; 묶음이 분석 적격인지는 별도 |
| cancel_delay_seconds | int64 | False | 40187 | 최초 행별 검증 통과 취소시각 - 원구매시각(초) |
| late_cancel_detail_count | int64 | False | 0 | 행별 검증 통과 취소 중 취소시각≥출발시각인 상세 수; 0원 제외 |
| unresolved_cancel_order_count | int64 | False | 0 | 해당 구매를 후보로 가진 미연결 취소의 고유 전표 수 |
| header_detail_mismatch | int32 | False | 0 | 원구매 전표의 공용 헤더 불일치 플래그; 상세 합계를 사용하며 단독 제외 안 함 |
| observation_end_at | timestamp[ms, tz=Asia/Seoul] | False | 0 | 입력 전표의 최대 유효 발생시각; 수집 완전성 보장은 아님 |
| analysis_eligible | int32 | False | 0 | 주 분석은 반드시 1만 사용 |
| exclusion_reasons | string | False | 0 | 복수 분석 부적격 사유; &#124;로 구분 |
| purchase_order_row_id | string | False | 0 | 해당 clean 테이블의 _DQ_ROW_ID; 원천 계보 |
| entry_row_id | string | False | 0 | 해당 clean 테이블의 _DQ_ROW_ID; 원천 계보 |
| snapshot_row_id | string | False | 0 | 해당 clean 테이블의 _DQ_ROW_ID; 원천 계보 |
| dq_dataset_version | string | False | 0 | 공용 clean 버전 |
| rule_version | string | False | 0 | Gold 규칙 버전 |

## ticket_disposition

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| source_row_id | string | True | 0 | clean의 _DQ_ROW_ID; 해당 입력 처분/감사 테이블 PK |
| source_bronze_file | string | False | 0 | clean에 보존된 _SRC_BRONZE_FILE |
| source_row_no | int64 | False | 0 | clean에 보존된 _SRC_ROW_NO |
| order_no | string | False | 0 | 입력 마권의 전표번호 |
| ticket_seq | int32 | False | 0 | 입력 상세 순번; 취소 연결키 아님 |
| bet_amt | int64 | False | 0 | 원래 부호를 보존한 입력 상세 금액(원) |
| unit_cnt | int64 | False | 0 | 원래 부호를 보존한 입력 상세 구좌 수 |
| disposition | string | False | 0 | FACT_PURCHASE / CANCEL_AUDIT / OUT_OF_SCOPE; 입력 1행당 정확히 하나 |
| reason | string | False | 0 | 범위 포함/제외 사유 |
| fact_id | string | False | 460934 | 原구매 전표·경주일·경주번호·WIN·출주번호의 내부 해시 |
| rule_id | string | False | 0 | 적용 Gold 규칙 |
| decision_id | string | False | 0 | 적용 Gold/공용 근거 결정 ID |

## cancel_link_audit

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| source_row_id | string | True | 0 | clean의 _DQ_ROW_ID; 해당 입력 처분/감사 테이블 PK |
| source_bronze_file | string | False | 0 | clean에 보존된 _SRC_BRONZE_FILE |
| source_row_no | int64 | False | 0 | clean에 보존된 _SRC_ROW_NO |
| cancel_order_no | string | False | 0 | 취소 전표번호 |
| reference_order_no | string | False | 704 | 취소 전표에 기록된 원전표번호 |
| member_no | string | False | 94 | 표준 회원 업무키 |
| race_date | date32[day] | False | 0 | 달력 날짜; 원천 또는 해당 사건 기준 |
| race_no | int32 | False | 0 | 경주번호 |
| chul_no | int32 | False | 0 | 해당 경주의 출주번호; 말 영구 속성 아님 |
| cancel_at | timestamp[ms, tz=Asia/Seoul] | False | 0 | Asia/Seoul KST 사건 시각 |
| cancel_amount_krw | int64 | False | 0 | 입력 취소 상세 금액의 절댓값(원) |
| cancel_stake_units | int64 | False | 0 | 입력 취소 상세 구좌 절댓값 |
| matched_target_fact_id | string | False | 4065 | 원전표·회원·선택이 연결되는 대상 팩트 ID; 실제 검증 통과는 link_status로 확인 |
| plausible_target_group_count | int64 | False | 0 | 미연결 비영 취소의 같은 회원·선택·이전 구매 후보 수; 자동 배정 아님 |
| link_status | string | False | 0 | ZERO_EXCLUDED / VERIFIED_TARGET_LINK / INVALID_TARGET_LINK / NOT_ASSIGNED_TO_TARGET |
| reasons | string | False | 0 | 취소 상세 검증 사유 |
| late_cancel_yn | string | False | 0 | 취소시각≥해당 경주출발시각 Y; NULL 시각은 비교 불가 |
| rule_id | string | False | 0 | 적용 Gold 규칙 |
| decision_id | string | False | 0 | 적용 Gold/공용 근거 결정 ID |

## fact_analysis_exclusions

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| fact_id | string | True | 0 | 原구매 전표·경주일·경주번호·WIN·출주번호의 내부 해시 |
| exclusion_reasons | string | False | 0 | 복수 분석 부적격 사유; &#124;로 구분 |
| rule_id | string | False | 0 | 적용 Gold 규칙 |
| decision_id | string | False | 0 | 적용 Gold/공용 근거 결정 ID |

## win_rate_cancel_summary

| 컬럼 | 타입 | PK | NULL 행 | 의미 |
| --- | --- | --- | --- | --- |
| summary_id | string | True | 0 | scope와 승률구간으로 구성한 요약 PK |
| scope | string | False | 0 | all_positive_starts / min_10_recent_starts |
| win_rate_band | string | False | 0 | 승률 구간 |
| purchase_selection_groups | int64 | False | 0 | 적격 구매 선택 묶음 수 |
| cancelled_groups | int64 | False | 0 | 확인취소 적격 구매 묶음 수 |
| observed_cancel_rate | double | False | 0 | 적격 확인취소 구매묶음수/적격 구매묶음수 |
| purchase_amount_krw | int64 | False | 0 | 0원 상세를 제외한 원구매 상세 금액 합(원); 헤더 금액 아님 |
| cancel_amount_krw | int64 | False | 0 | 입력 취소 상세 금액의 절댓값(원) |
| amount_cancel_rate | double | False | 0 | 적격 확인취소금액/적격 원구매금액 |
| unique_members | int64 | False | 0 | 적격 고유 회원 수 |
| unique_horses | int64 | False | 0 | 적격 고유 내부 말 키 수 |
| unique_races | int64 | False | 0 | 적격 고유 경주 수 |
