# Gold 50대 단승 마권 취소 스타 스키마

공용 clean 버전 `948fe690c7a42511710c7264904d9ada523c5aeb12b118aa570a423dce428b6c`을 사용했습니다. Gold 버전은 `GOLD-64c30a47ecb25dd52c0f`입니다.

## 팩트와 차원

`FCT_BET_SELECTION_CANCEL_50S` 한 행은 **원구매 전표 × 경주일 × 경주번호 × WIN × 출주번호**로 묶은 구매 한 건입니다. 원구매일의 만 나이가 50~59세인 회원을 대상으로 합니다. 같은 묶음의 구매 상세를 합산하고, 확인된 취소를 묶음에 연결합니다.

| 차원 | 업무 키 | 팩트 외래키 |
| --- | --- | --- |
| `DIM_MEMBER` | 회원번호 | `member_key` |
| `DIM_HORSE` | 마명과 생일 | `horse_key` |
| `DIM_RACE` | 경마장, 경주일, 경주번호 | `race_id` |
| `DIM_DATE` | 날짜 | `purchase_date_key`, `cancel_date_key`, `race_date_key`, `snapshot_date_key` |
| `DIM_CHANNEL` | 발매 채널과 지점 | `channel_key` |

확인할 수 없는 차원 참조에는 `UNKNOWN`(날짜는 `0`) 행을 연결합니다. 말 키는 내부 마명·생일 식별자입니다. 팀 공통 차원 통합 시 업무 키로 팩트 외래키를 다시 연결하고 대사합니다.

## 측정값

| 측정값 | 계산 및 기준 |
| --- | --- |
| `purchase_amount_krw`, `purchase_stake_units`, `purchase_detail_count` | 공용 `BET_TICKET`의 원구매 상세 금액, 구좌, 행 수를 묶음별로 합산합니다. 0원 상세는 업무 집계에서 제외합니다(D-003). |
| `has_verified_customer_cancel` | 원전표·회원·선택·시각 등으로 확인된 취소가 있으면 1, 관측 구간에서 확인된 취소가 없으면 0, 미연결이나 초과 취소 등으로 판정할 수 없으면 NULL입니다. |
| `verified_cancel_amount_krw`, `verified_cancel_stake_units` | 연결 검증을 통과한 취소 상세의 금액과 구좌 절댓값을 합산합니다. 0원 상세는 분자와 분모 모두에서 제외합니다. |
| `late_cancel_detail_count` | 연결 검증을 통과한 취소 중 취소 시각이 경주 출발 시각 이상인 상세를 셉니다(D-004). |
| `recent1y_win_rate`, `career_win_rate` | 구매일보다 엄격히 이전인 최신 `HR_WEEKLY_SNAPSHOT`의 1착수 ÷ 출전수입니다. 출전 0이나 유효하지 않은 값은 NULL입니다. |
| 관측 취소율 | `analysis_eligible = 1`인 확인 취소 구매 묶음 수 ÷ 적격 구매 묶음 수입니다. 금액 취소율은 같은 범위의 확인 취소 금액 ÷ 구매 금액입니다. |

시각은 모두 시간대 정보 없는 KST `timestamp[ms]`입니다. 팩트에는 분석 부적격 구매도 남겨 두므로, 취소율 집계에는 `analysis_eligible = 1`을 적용합니다. 관측 종료 시각은 입력 전표의 최대 발생 시각을 사용합니다. 취소 회원이 미상인 거래는 개별 구매에 배정할 수 없습니다. 생일 생성값과 재매핑 거래를 포함한 시뮬레이션 데이터이므로 결과를 실제 고객 행동이나 인과효과로 해석할 수 없습니다.

## 생성과 검증

저장소 루트에서 Python 3.11 이상과 `requirements.txt` 환경으로 실행합니다.

```powershell
python src/bet_cancel/04_fct_bet_cancel.py
python src/bet_cancel/04_fct_bet_cancel_check.py
python -m unittest discover -s src/bet_cancel -p test_bet_cancel.py -v
```

생성 코드는 공용 `data/02_silver/clean/_manifest.json`에 기록된 14개 Parquet 해시를 확인한 뒤 `BET_ORDER`, `BET_TICKET`, `MBR_MASTER`, `HR_WEEKLY_SNAPSHOT`, `RC_RACE`, `RC_ENTRY`, `RC_RESULT`를 읽습니다. 동일 입력으로 재실행하면 새 계산 결과와 기존 산출물의 해시를 대사합니다. 읽기 전용 검증은 공용 clean에서 다시 계산해 Parquet 값·스키마·해시, 검증 보고서와 문서까지 비교합니다.

## 생성 결과
| 산출물 | 행 수 | PK |
| --- | --- | --- |
| [DIM_MEMBER.parquet](../../data/03_gold/bet_cancel/DIM_MEMBER.parquet) | 4,384 | member_key |
| [DIM_HORSE.parquet](../../data/03_gold/bet_cancel/DIM_HORSE.parquet) | 833 | horse_key |
| [DIM_RACE.parquet](../../data/03_gold/bet_cancel/DIM_RACE.parquet) | 387 | race_id |
| [DIM_DATE.parquet](../../data/03_gold/bet_cancel/DIM_DATE.parquet) | 180 | date_key |
| [DIM_CHANNEL.parquet](../../data/03_gold/bet_cancel/DIM_CHANNEL.parquet) | 32 | channel_key |
| [FCT_BET_SELECTION_CANCEL_50S.parquet](../../data/03_gold/bet_cancel/FCT_BET_SELECTION_CANCEL_50S.parquet) | 41,141 | fact_id |
| [TICKET_DISPOSITION.parquet](../../data/03_gold/bet_cancel/audit/TICKET_DISPOSITION.parquet) | 522,364 | source_row_id |
| [CANCEL_LINK_AUDIT.parquet](../../data/03_gold/bet_cancel/audit/CANCEL_LINK_AUDIT.parquet) | 5,121 | source_row_id |
| [FACT_ANALYSIS_EXCLUSIONS.parquet](../../data/03_gold/bet_cancel/audit/FACT_ANALYSIS_EXCLUSIONS.parquet) | 1,857 | fact_id |
| [WIN_RATE_CANCEL_SUMMARY.csv](../../data/03_gold/bet_cancel/WIN_RATE_CANCEL_SUMMARY.csv) | 10 | summary_id |

| 분석 지표 | 건수·금액 |
| --- | --- |
| 분석 적격 구매 묶음 | 39,284 |
| 분석 부적격 구매 묶음 | 1,857 |
| 확인 취소가 있는 적격 구매 묶음 | 894 |
| 적격 구매 금액 (원) | 230,209,200 |
| 적격 확인 취소 금액 (원) | 3,765,000 |
| 적격 구매의 확인된 늦은 취소 상세 | 20 |

전체 clean 마권의 처리 내역은 `audit/TICKET_DISPOSITION.parquet`에서 Bronze 경로와 원천 행 번호로 추적합니다. 취소 상세 연결과 분석 제외 사유는 별도 감사 파일에 저장합니다.

| 입력 마권 처리 사유 | 행 수 |
| --- | --- |
| AGE_UNKNOWN | 51,487 |
| GROUPED | 61,430 |
| NON_WIN | 266,888 |
| OUTSIDE_50S | 135,669 |
| WIN_CANCEL | 5,120 |
| ZERO_AMOUNT | 1,770 |

| 분석 제외 사유 (한 팩트에 복수 적용 가능) | 팩트 수 |
| --- | --- |
| CANCEL_EXCEEDS_PURCHASE | 20 |
| FOLLOWUP_NOT_CLOSED | 131 |
| UNRESOLVED_CANCEL_CONTEXT | 82 |
| VOID_OR_NONSTART_STATUS | 142 |
| ZERO_RECENT_STARTS | 1,493 |

## 실제 검증 결과
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

[입력·출력 매니페스트](../../data/03_gold/bet_cancel/_manifest.json) · [검증 결과 JSON](../../data/03_gold/bet_cancel/_validation.json) · [컬럼 사전](../../data/03_gold/bet_cancel/_column_dictionary.csv) · [차원 키 계약](../../data/03_gold/bet_cancel/_dimension_contract.json) · [분석 판단 규칙](../../data/03_gold/bet_cancel/_decisions.json) · [SQL 스키마 예제](../../data/03_gold/bet_cancel/_schema.sql)
