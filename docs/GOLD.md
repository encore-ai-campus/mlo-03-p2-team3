# Gold 스타 스키마 작업 기록

2026-11-20 (KST). 설계: [GOLD_DESIGN.md](GOLD_DESIGN.md), [사용법](gold_usage.md), [컬럼](GOLD_COLUMNS.md).

입력 clean 버전 `DQ-2a7f4bd98578ec01a8d5`. Gold 버전 `GOLD-7747958492418b0ee3ce`.

팩트 한 행은 원구매 전표×경주일×경주번호×WIN×출주번호의 구매 선택 묶음입니다. 0원 상세는 업무 분자·분모에서 제외합니다. 늦은 취소는 D-004에 따라 허용하며 연결 검증을 통과해야 합니다.

## 실제 생성 결과

| 산출물 | 행 수 | PK | 형식·위치 |
| --- | --- | --- | --- |
| dim_member | 4,384 | member_key | DIM_MEMBER.parquet |
| dim_horse | 833 | horse_key | DIM_HORSE.parquet |
| dim_race | 387 | race_id | DIM_RACE.parquet |
| dim_date | 180 | date_key | DIM_DATE.parquet |
| dim_channel | 32 | channel_key | DIM_CHANNEL.parquet |
| fct_bet_selection_cancel_50s | 41,141 | fact_id | FCT_BET_SELECTION_CANCEL_50S.parquet |
| ticket_disposition | 522,364 | source_row_id | TICKET_DISPOSITION.parquet |
| cancel_link_audit | 5,121 | source_row_id | CANCEL_LINK_AUDIT.parquet |
| fact_analysis_exclusions | 1,857 | fact_id | FACT_ANALYSIS_EXCLUSIONS.parquet |
| win_rate_cancel_summary | 10 | summary_id | meta/WIN_RATE_CANCEL_SUMMARY.csv (분석 보조) |

## 분석 적격 결과

| 지표 | 실측 |
| --- | --- |
| eligible_cancel_amount | 3,765,000 |
| eligible_cancel_groups | 894 |
| eligible_facts | 39,284 |
| eligible_late_cancel_details | 20 |
| eligible_purchase_amount | 230,209,200 |
| excluded_facts | 1,857 |

전체 팩트는 분석 부적격 행도 포함합니다. 주 분석은 `analysis_eligible=1`을 반드시 적용합니다. 분석 제외 사유는 FACT_ANALYSIS_EXCLUSIONS.parquet에, 전체 입력의 범위 제외는 TICKET_DISPOSITION.parquet에, 취소 행별 검증은 CANCEL_LINK_AUDIT.parquet에 보존하며 이 감사 파일3개는 meta/audit/에 둡니다. Gold 데이터 폴더에는 스타 스키마6개만 둡니다.

## 입력 마권 전수 처분 사유

| 사유 | 행 수 |
| --- | --- |
| AGE_UNKNOWN | 51487 |
| GROUPED | 61430 |
| NON_WIN | 266888 |
| OUTSIDE_50S | 135669 |
| WIN_CANCEL | 5120 |
| ZERO_AMOUNT | 1770 |

## 분석 제외 사유 (중복 집계)

| 사유 | 팩트 수 |
| --- | --- |
| CANCEL_EXCEEDS_PURCHASE | 20 |
| FOLLOWUP_NOT_CLOSED | 131 |
| UNRESOLVED_CANCEL_CONTEXT | 82 |
| VOID_OR_NONSTART_STATUS | 142 |
| ZERO_RECENT_STARTS | 1493 |

## 검증 결과

| 검사 | 기대 | 실제 | 결과 |
| --- | --- | --- | --- |
| dim_member PK duplicates | 0 | 0 | 통과 |
| dim_member PK nulls | 0 | 0 | 통과 |
| dim_horse PK duplicates | 0 | 0 | 통과 |
| dim_horse PK nulls | 0 | 0 | 통과 |
| dim_race PK duplicates | 0 | 0 | 통과 |
| dim_race PK nulls | 0 | 0 | 통과 |
| dim_date PK duplicates | 0 | 0 | 통과 |
| dim_date PK nulls | 0 | 0 | 통과 |
| dim_channel PK duplicates | 0 | 0 | 통과 |
| dim_channel PK nulls | 0 | 0 | 통과 |
| fct_bet_selection_cancel_50s PK duplicates | 0 | 0 | 통과 |
| fct_bet_selection_cancel_50s PK nulls | 0 | 0 | 통과 |
| ticket_disposition PK duplicates | 0 | 0 | 통과 |
| ticket_disposition PK nulls | 0 | 0 | 통과 |
| cancel_link_audit PK duplicates | 0 | 0 | 통과 |
| cancel_link_audit PK nulls | 0 | 0 | 통과 |
| fact_analysis_exclusions PK duplicates | 0 | 0 | 통과 |
| fact_analysis_exclusions PK nulls | 0 | 0 | 통과 |
| win_rate_cancel_summary PK duplicates | 0 | 0 | 통과 |
| win_rate_cancel_summary PK nulls | 0 | 0 | 통과 |
| fact business key duplicates | 0 | 0 | 통과 |
| member_key missing FK | 0 | 0 | 통과 |
| horse_key missing FK | 0 | 0 | 통과 |
| race_id missing FK | 0 | 0 | 통과 |
| channel_key missing FK | 0 | 0 | 통과 |
| purchase_date_key missing FK | 0 | 0 | 통과 |
| cancel_date_key missing FK | 0 | 0 | 통과 |
| race_date_key missing FK | 0 | 0 | 통과 |
| snapshot_date_key missing FK | 0 | 0 | 통과 |
| input ticket row coverage | 522364 | 522364 | 통과 |
| input ticket id coverage | 522364 | 522364 | 통과 |
| target purchase details | 61430 | 61430 | 통과 |
| target purchase amount | 241761600 | 241761600 | 통과 |
| target purchase units | 2417616 | 2417616 | 통과 |
| all input signed amount | 1870219600 | 1870219600 | 통과 |
| all WIN cancel details audited | 5121 | 5121 | 통과 |
| verified cancel amount audit | 4274800 | 4274800 | 통과 |
| eligible plus excluded facts | 41141 | 41141 | 통과 |
| eligible cohort/prior/time/amount bounds | True | True | 통과 |
| base summary purchase_selection_groups | 39284 | 39284 | 통과 |
| base summary cancelled_groups | 894 | 894 | 통과 |
| base summary purchase_amount_krw | 230209200 | 230209200 | 통과 |
| base summary cancel_amount_krw | 3765000 | 3765000 | 통과 |

## 공통 차원 계약과 한계

이번 대리키·컬럼·코드 계약은 이 브랜치의 제안이며 팀 합의 완료를 의미하지 않습니다. 다른 팀원과 통합할 때 member_no, 말 이름·생일, MEET_CD·경주일·경주번호, 날짜, 채널·지점의 자연키로 연결한 뒤 팩트 FK를 다시 검증합니다. 세부 계약은 meta/gold_dimension_contract.json에 기록합니다.

말 키는 내부 이름·생일 기반이며 공식 마번이 아닙니다. 전체 스냅샷에서 생일·부·모가 충돌하면 UNKNOWN으로 두며, 미래 성적은 사용하지 않습니다. 성별과 승률·출주번호는 차원의 고정 속성으로 두지 않습니다. UNKNOWN 키(날짜는0)는 FK 무결성용이며 해당 분석은 제외 사유를 확인합니다.

관측 종료는 전체 전표 최대 시각을 이용한 보수적 경계이며 수집 완료 인증은 아닙니다. 미연결 취소가 알려진 같은 회원·선택의 이전 구매에 영향을 줄 때 NULL 라벨을 유지하며, 회원조차 미상인 취소의 관측 누락은 해소하지 못합니다.

생일 생성값·소매 재매핑 거래를 포함한 시뮬레이션 분석입니다. 실제 마사회 고객 행동·인과효과로 일반화하지 않습니다. 회원·말·경주의 반복 관측을 독립표본으로 가정하지 않습니다. 참고 폴더의 41,149·39,263·875는 현재 규칙 기대값으로 사용하지 않았습니다.

DB 연결·적재는 수행하지 않았습니다. 스타 스키마 Parquet와 SQL 예제를 생성했습니다. 입력 Silver·Bronze·원천은 수정하지 않습니다.
