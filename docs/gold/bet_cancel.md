# Gold 50대 단승 마권 취소

- 팩트 [`FCT_BET_SELECTION_CANCEL_50S.parquet`](../../data/03_gold/bet_cancel/FCT_BET_SELECTION_CANCEL_50S.parquet)
- 생성 코드 [`04_fct_bet_cancel.py`](../../src/bet_cancel/04_fct_bet_cancel.py)
- 공통 차원 [연결 규칙](common.md#2-팩트에서-연결하는-방법) · [팀 결정 D-012~D-016](../../meta/decision_log.md)

## 1. 그레인

**한 행은 구매일 기준 만 50~59세 회원의 전표별·경주별·출주마별 단승 구매 묶음 1건입니다.** Silver `BET_TICKET`에서 단승(`BET_TYPE_CD = 'WIN'`) 구매 상세를 `ORDER_NO + RC_DT + RC_NO + CHUL_NO`로 묶습니다. 같은 조합의 구매 상세는 한 행에 합산합니다. `FACT_ID`는 이 조합과 고정 승식 `WIN`으로 만든 키이며, 구매 전표번호는 `ORIG_ORDER_NO`에 저장합니다.

공용 Silver clean 입력은 `BET_ORDER`, `BET_TICKET`, `MBR_MASTER`, `RC_RACE`, `RC_ENTRY`, `RC_RESULT`, `HR_WEEKLY_SNAPSHOT`입니다. `BET_ORDER`의 발생 시각과 `MBR_MASTER.BIRTH_DT`로 구매 당시 만 나이를 계산합니다.

## 2. 공통 차원 연결

| 공통 차원 | 팩트 FK | 연결 방법 |
| --- | --- | --- |
| `DIM_RACE` | `RACE_KEY` | 구매 마권의 `RC_DT + RC_NO`로 공통 경주 키를 찾습니다. |
| `DIM_HORSE` | `HORSE_KEY` | 출전표의 `HR_NM`과 원구매일에 유효한 SCD2 버전을 연결합니다. 유효 기간의 시작일과 종료일을 모두 포함합니다. 유효한 이력이나 구매일 이전 스냅샷이 없으면 `0`입니다. |
| `DIM_MEMBER` | `MEMBER_KEY` | 구매 전표의 `MBR_NO`로 연결합니다. 회원번호가 빈 전표는 공통 차원의 `NON_MEMBER`에 해당하며, 구매 당시 만 나이를 확인한 50대 회원이 이 팩트의 대상입니다. |
| `DIM_CHANNEL` | `CHANNEL_KEY` | 구매 전표의 `CHNL_CD + OTB_BRANCH_NO`로 연결합니다. |
| `DIM_DATE` | `PURCHASE_DT_KEY`, `CANCEL_DT_KEY`, `DATE_KEY`, `SNAPSHOT_DT_KEY` | 원구매일, 최초 확인 취소일, 경주일, 승률 계산에 사용한 스냅샷일을 각각 `YYYYMMDD` 정수로 연결합니다. |

공통 차원 FK는 모두 `int32`이며, 연결 값이 없으면 공통 미상 키 `0`을 사용합니다. 말의 승률은 구매일보다 앞선 최신 Silver 스냅샷의 성적으로 계산합니다.

## 3. 컬럼

### 키와 구매 측정값

| 컬럼 | 타입 | 의미 |
| --- | --- | --- |
| `FACT_ID` | string | 팩트 기본키. 원구매 전표·경주일·경주번호·단승·출주번호의 조합으로 생성합니다. |
| `ORIG_ORDER_NO` | string | Silver 구매 마권의 `ORDER_NO`입니다. |
| `MEMBER_KEY`, `HORSE_KEY`, `RACE_KEY`, `CHANNEL_KEY` | int32 | 회원·말·경주·채널 공통 차원 FK입니다. |
| `PURCHASE_DT_KEY`, `CANCEL_DT_KEY`, `DATE_KEY`, `SNAPSHOT_DT_KEY` | int32 | 날짜 공통 차원을 가리키는 역할별 FK입니다. |
| `BET_TYPE_CD`, `CHUL_NO` | string, int32 | 승식(`WIN`)과 해당 경주의 출주번호입니다. |
| `MBR_AGE`, `PURCHASE_DTM` | int32, timestamp[ms] | 구매일 기준 만 나이와 구매 전표 발생 시각입니다. |
| `PURCHASE_DETAIL_CNT`, `PURCHASE_UNIT_CNT`, `PURCHASE_AMT` | int64 | 구매 상세 행 수, 구매 구좌 합계, 구매 금액 합계(원)입니다. 0원 마권은 제외합니다. |
| `HR_AGE`, `HR_SEX_CD` | int32, string | 출전표에 기록된 경주 당시 말의 나이와 성별입니다. |

### 말 성적과 취소 측정값

| 컬럼 | 타입 | 의미 |
| --- | --- | --- |
| `SNAPSHOT_DT`, `SNAPSHOT_AGE_DAY_CNT` | date32, int32 | 채택한 스냅샷 날짜와 그 날짜부터 구매일까지의 일수입니다. |
| `Y1_RC_CNT`, `Y1_1ST_CNT`, `TOT_RC_CNT`, `TOT_1ST_CNT` | int64 | 최신 이전 스냅샷의 최근 1년 및 통산 출전수·1착수입니다. |
| `Y1_WIN_RT`, `TOT_WIN_RT` | double | 각각 1착수 ÷ 출전수입니다. 출전수가 0이거나 전적 값이 유효하지 않으면 `NULL`입니다. |
| `Y1_WIN_RT_BAND_CD` | string | 최근 1년 승률 구간입니다. `0%`, `(0,5%]`, `(5,10%]`, `(10,20%]`, `>20%`, `UNKNOWN`을 사용합니다. |
| `VERIFIED_CANCEL_YN`, `CANCEL_LABEL_STAT_CD` | string, string | 확인 취소 있음 `Y / VERIFIED_CANCEL`, 관측된 확인 취소 없음 `N / NO_CANCEL_OBSERVED`, 판정 불명확 `NULL / AMBIGUOUS`입니다. |
| `CANCEL_ORDER_CNT`, `RAW_CANCEL_AMT` | int64 | 원전표·회원·선택이 일치하는 비영 취소의 고유 전표 수와 상세 금액 절댓값 합계입니다. 후속 검증에 실패한 상세도 포함합니다. |
| `VERIFIED_CANCEL_AMT`, `VERIFIED_CANCEL_UNIT_CNT` | int64 | 상세 검증을 통과한 취소 금액(원)과 구좌의 절댓값 합계입니다. |
| `FIRST_CANCEL_DTM`, `CANCEL_DELAY_SEC` | timestamp[ms], int64 | 상세 검증을 통과한 최초 취소 시각과 구매부터 그 취소까지의 초입니다. |
| `LATE_CANCEL_DETAIL_CNT` | int64 | 취소 시각이 경주 출발 시각 이상인 검증 통과 상세 수입니다. |
| `UNRESOLVED_CANCEL_ORDER_CNT` | int64 | 같은 회원·선택의 앞선 구매에 영향을 줄 수 있으나 확정 연결되지 않은 취소 전표 수입니다. |

### 분석 범위와 추적

| 컬럼 | 타입 | 의미 |
| --- | --- | --- |
| `HEADER_MISMATCH_YN` | string | 구매 전표의 헤더·상세 불일치 플래그(`Y` 또는 `N`)입니다. |
| `OBSERVATION_END_DTM` | timestamp[ms] | 입력 전표에 기록된 최대 발생 시각입니다. |
| `ANALYSIS_ELIGIBLE_YN`, `EXCLUDE_REASON_CD` | string, string | 취소율 분석 적격 여부(`Y` 또는 `N`)와 제외 사유입니다. 여러 사유는 파이프 문자로 구분합니다. |
| `PURCHASE_ORDER_ROW_ID`, `ENTRY_ROW_ID`, `SNAPSHOT_ROW_ID` | string | 구매 전표·출전표·스냅샷을 Silver 테이블명과 원천 행 번호로 추적하는 식별자입니다. |
| `CLEAN_VERSION_CD`, `RULE_VERSION_CD` | string | 공용 clean 입력 버전과 Gold 계산 규칙 버전입니다. |

시각 컬럼은 시간대 정보 없는 KST입니다. 구매 묶음 기준 취소율은 `ANALYSIS_ELIGIBLE_YN = Y`인 행에서 확인 취소 묶음 수를 전체 적격 묶음 수로 나눕니다. 이 Gold 팩트의 검증 통과 취소 합계에는 늦은 취소도 포함됩니다. 출발 전 피처를 계산할 때는 Silver의 개별 전표 시각을 기준으로 집계합니다.

## 4. 대사 결과

| 검증 항목 | 결과 |
| --- | ---: |
| 전체 구매 묶음 | 41,141행 |
| 분석 적격 구매 묶음 | 39,284행 |
| 분석 제외 구매 묶음 | 1,857행 |
| 적격 구매 중 확인 취소가 있는 묶음 | 894행 |
| 전체 구매 금액 | 241,761,600원 |
| 전체 검증 통과 취소 금액 | 4,274,800원 |
| 팩트 PK 중복·NULL | 0건 |
| 공통 차원 FK 누락 | 0건 |

저장소 루트에서 [공통 차원 검증 스크립트](../../src/common/04_common_dims_check.py)를 실행하면 현재 팩트 FK를 확인할 수 있습니다.

```powershell
python src/common/04_common_dims_check.py
```
