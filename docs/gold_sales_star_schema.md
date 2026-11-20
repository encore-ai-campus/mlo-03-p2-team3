# 경주·승식별 매출 Gold 스타 스키마

## 실행

```powershell
python src/build_gold_sales.py
```

입력은 `data/02_silver/clean/`의 `BET_TICKET`, `BET_ORDER`, `MBR_MASTER`, `RC_RACE`, `RC_SALES`, `RC_SALES_TOTAL` Parquet입니다. 출력은 `data/03_gold/`의 아홉 Parquet과 `_validation.json`입니다. Silver 파일은 읽기만 합니다.

## 테이블과 그레인

| 테이블 | 한 행의 의미 | 기본 키 |
|---|---|---|
| `DIM_RACE` | 경주 1개 | `RACE_KEY` |
| `DIM_DATE` | 경주 날짜 1일 | `DATE_KEY` |
| `DIM_POOL` | 실제 매출의 승식 풀 1개 | `POOL_CD` |
| `DIM_BET_TYPE` | 가상 마권의 구매 승식 1개 | `BET_TYPE_CD` |
| `DIM_CHANNEL` | 판매 채널·장외 지점 조합 1개 | `CHANNEL_KEY` |
| `DIM_MEMBER` | 회원 1명 또는 비회원 | `MEMBER_KEY` |
| `DIM_TICKET_STATUS` | 마권 상태 1개 | `TICKET_STAT_CD` |
| `FACT_BET_TICKET` | 전표번호 + 마권순번당 마권 1개 | `ORDER_NO`, `TICKET_SEQ` |
| `FACT_ACTUAL_RACE_SALES` | 경주 + 승식 풀 1개 | `RACE_KEY`, `POOL_CD` |

두 팩트는 `RACE_KEY`, `DATE_KEY`로 경주·날짜 차원을 공유합니다. 실제 매출 팩트는 `POOL_CD`로 7개 풀의 `DIM_POOL`에 연결됩니다. 가상 마권 팩트는 `BET_TYPE_CD`, `CHANNEL_KEY`, `MEMBER_KEY`, `TICKET_STAT_CD`로 나머지 차원에 연결됩니다. 따라서 풀과 구매 승식은 코드값이 겹쳐도 별개의 차원입니다. `ORDER_NO`, `TICKET_SEQ`는 마권 식별자입니다.

`RACE_KEY`는 `RC_DT|RC_NO`, `DATE_KEY`는 `YYYYMMDD` 형식입니다. `DIM_RACE`에는 거리 수치·표시값(`900m`)과 날씨 코드·한글 이름을 둡니다. `DIM_DATE`에는 연·월·일과 ISO 요일 번호(월=1)·한글 요일을 둡니다. `DIM_POOL`에는 단식·연식·복식·복연·쌍식·삼복·삼쌍 이름을 둡니다. `DIM_BET_TYPE`에는 마권에 실제로 나타난 WIN·PLC·QNL을 둡니다. `CHANNEL_KEY`는 `CHNL_CD|OTB_BRANCH_NO` 형식입니다. 회원번호가 없는 전표의 마권은 `MEMBER_KEY=NON_MEMBER`로 `DIM_MEMBER`의 비회원 행에 연결하고, 원래의 빈 `MBR_NO`는 팩트에 보존합니다.

Gold 입력은 `clean` Parquet만 사용합니다. 원천의 `RC_DIST_RAW`, `WEATHER_TRACK_RAW`, `RC_DATE`, `POOL_NM`은 다시 읽지 않고 Silver의 표준 컬럼으로 표시값을 만듭니다.

## 금액 정의

`FACT_BET_TICKET`은 정제된 Silver 마권 **전체 행**을 유지합니다. `SALES_AGG_INCLUDE_YN=N`인 행은 금액 지표에 0원을 기여하며, 원래 `BET_AMT`와 품질 플래그는 보존합니다.

| 지표 | 행별 계산, 단위 원 |
|---|---|
| `VIRTUAL_GROSS_SALES_AMT` | 집계 대상 `SOLD`의 `BET_AMT`, 나머지 0 |
| `CANCEL_AMT` | 집계 대상 `CANCEL`의 `-BET_AMT` (양수), 나머지 0 |
| `VOID_AMT` | 집계 대상 `VOID`의 `BET_AMT` (양수), 나머지 0 |
| `NET_AFTER_CANCEL_AMT` | `VIRTUAL_GROSS_SALES_AMT - CANCEL_AMT` |
| `ACTUAL_SALES_AMT` | `RC_SALES.SALES_AMT` 그대로. `FACT_ACTUAL_RACE_SALES`에만 존재 |

`VOID_AMT`는 별도 표시하고 `NET_AFTER_CANCEL_AMT`에서 차감하지 않습니다. 취소 마권은 Silver에서 음수로 기록되어 있습니다. 가상 마권 매출과 실제 승식 풀 매출은 **서로 다른 모집단**입니다. 정제된 마권에는 WIN·PLC·QNL만 있지만, 실제 승식 풀에는 7개 승식이 모두 있습니다. 두 팩트를 직접 조인해 금액을 합산하면 마권 수만큼 실제 매출이 중복되므로, 비교하려면 각각 `RACE_KEY`와 각 팩트의 승식 코드(`BET_TYPE_CD` 또는 `POOL_CD`)로 먼저 집계해야 합니다.

## 대사와 검증

Gold 단계에서 제외하는 행은 없습니다. 마권 522,364행과 실제 승식 풀 2,702행을 그대로 팩트에 보존합니다. 각 테이블의 PK 중복 및 두 팩트의 차원 외래 키 누락을 0건으로 검증합니다. 마권 상태별 금액은 `BET_TICKET`의 포함 대상 원천 금액과 대사합니다. 실제 풀 금액은 `RC_SALES`와 대사하며, 각 경주의 7개 풀 합계는 `RC_SALES_TOTAL`과 비교합니다. 검증에 실패하면 오류를 내고 결과 파일을 쓰지 않습니다. 검증 결과는 `data/03_gold/_validation.json`에 저장합니다.

실행 결과: 가상 정상 매출 1,903,091,700원, 취소액 41,064,800원, 무효액 8,192,700원, 취소 차감 후 매출 1,862,026,900원, 실제 승식 풀 매출 747,386,251,200원입니다.
