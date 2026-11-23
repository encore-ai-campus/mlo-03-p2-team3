# 스타 스키마

네 팩트가 공통 차원을 공유하는 통합 모델입니다.

```mermaid
erDiagram
    direction TB
    DIM_DATE ||--o{ FCT_RACE_ENTRY : DATE_KEY
    DIM_RACE ||--o{ FCT_RACE_ENTRY : RACE_KEY
    DIM_HORSE ||--o{ FCT_RACE_ENTRY : HORSE_KEY
    DIM_TRAINER ||--o{ FCT_RACE_ENTRY : TRAINER_KEY
    DIM_DATE ||--o{ FCT_HORSE_MEDICAL : "VET_DT_KEY / REPORT_DT_KEY"
    DIM_HORSE ||--o{ FCT_HORSE_MEDICAL : HORSE_KEY
    DIM_TRAINER ||--o{ FCT_HORSE_MEDICAL : TRAINER_KEY
    DIM_AGE_GROUP ||--o{ FCT_HORSE_MEDICAL : AGE_GROUP_KEY
    FCT_HORSE_MEDICAL ||--|{ BRIDGE_HR_VET_TYPE : VET_SEQ
    DIM_VET_TYPE ||--o{ BRIDGE_HR_VET_TYPE : VET_TYPE_KEY
    DIM_DATE ||--o{ race_sales : "DATE_KEY / SALE_DATE_KEY"
    DIM_RACE ||--o{ race_sales : RACE_KEY
    DIM_MEMBER ||--o{ race_sales : MEMBER_KEY
    DIM_CHANNEL ||--o{ race_sales : CHANNEL_KEY
    DIM_BET_TYPE ||--o{ race_sales : BET_TYPE_CD
    DIM_TICKET_STATUS ||--o{ race_sales : TICKET_STAT_CD
    DIM_DATE ||--o{ FCT_BET_SELECTION_CANCEL_50S : "구매일 / 취소일 / 경주일 / 스냅샷일"
    DIM_RACE ||--o{ FCT_BET_SELECTION_CANCEL_50S : RACE_KEY
    DIM_HORSE ||--o{ FCT_BET_SELECTION_CANCEL_50S : HORSE_KEY
    DIM_MEMBER ||--o{ FCT_BET_SELECTION_CANCEL_50S : MEMBER_KEY
    DIM_CHANNEL ||--o{ FCT_BET_SELECTION_CANCEL_50S : CHANNEL_KEY
```

## 팩트 grain

| 주제 · 팩트 | 한 행의 의미 | PK | 실제 행 수 |
| --- | --- | --- | ---: |
| [경주 출전](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/race_entry.md) · `FCT_RACE_ENTRY` | 경주별 출전표에 오른 말 1두 | `RACE_KEY + CHUL_NO` | 3,666 |
| [말 진료](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/horse_medical.md) · `FCT_HORSE_MEDICAL` | 진료 기록 1건 | `VET_SEQ` | 1,488 |
| [마권 매출](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/race_sales.md) · `race_sales` | 전표 내 마권 기록 1건(발매·취소·무효 포함) | `ORDER_NO + TICKET_SEQ` | 522,364 |
| [50대 단승 취소](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/bet_cancel.md) · `FCT_BET_SELECTION_CANCEL_50S` | 만 50~59세 회원의 전표별·경주별·출주마별 단승 구매 묶음 | `FACT_ID` | 41,141 |

## 차원

| 공통 차원 | 행 수(미상 포함) | 의미 |
| --- | ---: | --- |
| `DIM_DATE` | 188 | 2026-05-16~11-18 연속 187일 + 미상 |
| `DIM_RACE` | 387 | 경주 386개 + 미상 |
| `DIM_HORSE` | 4,127 | 말 1,250두의 SCD2 버전 4,126개 + 미상 |
| `DIM_TRAINER` | 19 | 조교사 18명 + 미상 |
| `DIM_MEMBER` | 4,385 | 회원 4,383명 + 비회원 + 미상 |
| `DIM_CHANNEL` | 40 | 현장·앱·장외 37개 지점 + 미상 |

전용 차원은 진료의 `DIM_AGE_GROUP` 5행·`DIM_VET_TYPE` 53행, 매출의 `DIM_BET_TYPE` 3행·`DIM_TICKET_STATUS` 3행입니다. 진료 유형 브리지 `BRIDGE_HR_VET_TYPE`은 1,662행입니다.

미상 키 `0`은 실제 차원 행으로 존재합니다. 비회원은 별도 양수 키로 연결합니다. 말 버전은 기준일 이전 스냅샷을 사용하며 유효 시작일은 스냅샷 다음 날입니다. 상세 규칙은 [공통 차원 문서](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/common.md)를 따릅니다.

## 측정값

| 팩트 | 측정값 | 입력과 계산 정의 |
| --- | --- | --- |
| 출전 | `START_CNT`, `WIN_CNT`, `PLACE_CNT` | clean `RC_RESULT`에서 출주(`RAN`) 1, 1착 1, 3착 이내 1. 미출주마는 0 |
| 출전 | `EXPECT_WIN` | clean `RC_ODDS.WIN_ODDS`의 역수를 경주별 역수 합으로 나눈 값. 미출주마는 0 |
| 진료 | `VET_CNT` | clean `HR_VET_HIST`의 진료 기록 1건당 1. 유형을 넘나들어 집계할 때는 `VET_SEQ` 중복 제거 |
| 매출 | `VIRTUAL_GROSS_SALES_AMT`, `SOLD_TICKET_CNT` | clean `BET_TICKET`에서 `INVALID_YN=N`인 `SOLD`의 금액과 행 수, 나머지 0 |
| 매출 | `CANCEL_AMT`, `VOID_AMT`, `NET_AFTER_CANCEL_AMT` | 유효 `CANCEL` 금액의 부호를 반전, 유효 `VOID` 금액은 별도 집계. 취소 차감 후 금액 = 정상 발매액 − 취소액 |
| 취소 | `PURCHASE_DETAIL_COUNT`, `PURCHASE_STAKE_UNITS`, `PURCHASE_AMOUNT_KRW` | 구매 당시 만 50~59세 회원의 0원 제외 단승 구매 상세를 전표·경주·출주마별로 묶어 건수·구좌·금액 합산 |
| 취소 | `VERIFIED_CANCEL_AMOUNT_KRW`, `HAS_VERIFIED_CUSTOMER_CANCEL` | 원전표·회원·선택이 일치하고 상세 검증을 통과한 취소 금액의 절댓값 합계, 취소 유무. 판정 불명확은 NULL |
| 취소 | `RECENT1Y_WIN_RATE`, `CAREER_WIN_RATE` | 구매일보다 앞선 최신 말 스냅샷의 최근 1년·통산 1착수 ÷ 출전수. 분모 0·유효하지 않은 전적은 NULL |

금액은 원 단위입니다. 매출의 취소 차감 후 금액에는 무효액을 추가 차감하지 않습니다. 마권 매출은 WIN·PLC·QNL 입력 기준이며 별도 `RC_SALES`의 7개 승식 매출과 동일한 모집단으로 가정하지 않습니다. `EXPECT_WIN`은 최종 배당 기반이므로 후속 예측 데이터에서는 이용 가능한 시점을 검토해야 합니다.
