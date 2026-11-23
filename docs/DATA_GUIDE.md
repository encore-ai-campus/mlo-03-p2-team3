# 데이터 안내서: 무엇이 들어 있나

## 한 줄 요약

**제주 경마장의 경주 정보와 마권 판매 기록**입니다. 기간은 2026-05-22 ~ 2026-11-14이고, 경마일 52일, 경주 386개입니다.

데이터는 다섯 덩어리로 나뉩니다.

```
[경주]  RC_RACE ─┬─ RC_ENTRY (누가 나왔나)
                 ├─ RC_ODDS (배당률·구간기록)
                 ├─ RC_RESULT (몇 등 했나)
                 ├─ RC_SALES / RC_SALES_TOTAL (승식별 매출)
                 └─ RC_CHANGE_EVENT (기수변경·말취소·주로상태 공지)

[판매]  MBR_MASTER ── BET_ORDER (전표) ── BET_TICKET (마권 한 장 한 장)

[말·조교사]  HR_WEEKLY_SNAPSHOT (말 주간 현황)
             TR_WEEKLY_SNAPSHOT (조교사 주간 현황)
             HR_VET_HIST ── HR_VET_TYPE_BRIDGE (진료 기록)
```

- 아래의 테이블 이름과 행 수는 Silver(`data/02_silver/`) 기준입니다.
- 컬럼별 자세한 뜻과 실제 값은 `docs/BRONZE_COLUMNS.md`(원천 그대로)와 `docs/SILVER_COLUMNS.md`(표준화 후)에 있습니다.

## 경마 용어

| 용어 | 뜻 |
|:--|:--|
| 경주번호 `RC_NO` | 그날 몇 번째 경주인지 (하루 6~9경주) |
| 마번 `CHUL_NO` | 경주에서 말이 받은 출전 번호 (1~10) |
| 착순 `FINISH_ORD` | 들어온 순위 |
| 부담중량 `BUDAM_KG` | 말이 지고 뛰는 무게 (기수 + 추) |
| 착차 `MARGIN` | 앞 말과의 거리. 말 몸 길이 단위(1½ 등), 또는 코·머리·목 차이 |
| 주로 상태 / 함수율 | 경주로 모래가 얼마나 젖었는지. 건조 → 양호 → 다습 → 포화 → 불량 |
| 승식 `BET_TYPE` | 마권 종류. 단승(WIN), 연승(PLC), 복승(QNL), 복연승(QPL), 쌍승(EXA), 삼복승(TRI), 삼쌍승(TLA) |
| 전표 / 마권 | 한 번 구매한 영수증이 전표, 그 안의 개별 베팅이 마권 |
| 구좌 | 100원 단위. 마권 금액 ÷ 100 |
| OTB | 장외발매소 (경마장 밖 판매점). 지점 37개 |

---

## 1. 경주

### RC_RACE: 경주 (386행)
- **한 행 = 경주 1개**
- 키: `RC_DT` + `RC_NO`

| 주요 컬럼 | 내용 |
|:--|:--|
| `RC_DIST_M` | 거리. 900 / 1000 / 1110 / 1200 / 1300 / 1400 / 1610m |
| `RC_GRADE_CD` | 경주 등급. 1~6, OPEN |
| `BUDAM_TYPE_CD` | 부담 방식. HANDICAP / SPECIAL_A |
| `WEATHER_CD`, `TRACK_STAT_CD`, `TRACK_MOIST_RT` | 날씨, 주로 상태, 함수율(%) |
| `PRIZE1_AMT` ~ `PRIZE5_AMT` | 1~5위 상금(원) |
| `START_TM`, `START_DTM` | 출발 시각 |
| `RC_TITLE_NM` | 이름 붙은 특별 경주만 있음 (25개). 일반 경주는 NULL |

### RC_ENTRY: 출전표 (3,666행)
- **한 행 = 경주 하나에 나온 말 1마리** (경주당 7~10마리)
- 키: `RC_DT` + `RC_NO` + `CHUL_NO`
- 주요 컬럼: 말 이름 `HR_NM`, 성별 `HR_SEX_CD`(M/F/G), 나이 `HR_AGE`, 부담중량 `BUDAM_KG`, 기수 `JK_NM`, 조교사 `TR_NM`, 마주 `OW_NM`, 레이팅 `RATING_VAL`
- 등장 수: 말 833마리, 기수 24명, 조교사 18명, 마주 160명

### RC_ODDS: 배당률·구간기록 (3,666행)
- **한 행 = 출전마 1마리.** 키가 `RC_ENTRY`와 같고 행도 1:1로 대응합니다.
- 주요 컬럼:
  - `WIN_ODDS`, `PLC_ODDS`: 단승·연승 배당률(배)
  - `SECT1_SEC` ~ `SECT7_SEC`: 구간별 기록(초). 거리에 따라 비어 있는 구간이 있습니다.
- 출전하지 않은 22마리는 배당률이 NULL입니다.

### RC_RESULT: 경주 결과 (3,666행)
- **한 행 = 출전마 1마리.** 키가 `RC_ENTRY`와 같습니다.

| 주요 컬럼 | 내용 |
|:--|:--|
| `ENTRY_STAT_CD` | RAN(뜀) 3,644 / EXCLUDED(경주제외) 18 / SCRATCHED(출주취소) 4 |
| `FINISH_ORD` | 착순. 뛰지 않은 말은 NULL |
| `HR_WGT_KG`, `HR_WGT_DIFF_KG` | 말 체중, 지난번 대비 증감 |
| `RC_TIME_SEC` | 경주 기록(초) |
| `MARGIN_CD`, `MARGIN_LEN` | 착차 종류(FIRST/LEN/NOSE/HEAD/NECK/DH/NA)와 길이 |
| `PASS_ORD_S1` ~ `S6` | 구간별 통과 순위 |

### RC_SALES: 승식별 매출 (2,702행) / RC_SALES_TOTAL: 경주별 합계 (386행)
- **RC_SALES 한 행 = 경주 1개 × 승식 1개** (승식 7종 × 386경주)
- **RC_SALES_TOTAL 한 행 = 경주 1개의 매출 합계**
  - 원천에서 '합계' 행만 따로 뺀 것으로, 검증용입니다.
  - 확인 결과 386경주 모두 승식별 합 = 합계였습니다.

### RC_CHANGE_EVENT: 변경 공지 (149행)
- **한 행 = 공지 1건.** 원천은 MongoDB JSON입니다.

| `EVENT_TYPE_CD` | 건수 | 채워지는 컬럼 |
|:--|--:|:--|
| JOCKEY_CHANGE (기수 변경) | 75 | 경주·말 + `BEF_JK_NM`, `AFT_JK_NM`, `BUDAM_KG`, `CHG_REASON_NM` |
| TRACK_STATUS (주로 상태) | 52 | `TRACK_STAT_CD`, `TRACK_MOIST_RT` (경주·말 칸은 NULL) |
| SCRATCH (말 취소) | 22 | 경주·말 + `SCRATCH_REASON_NM` |

---

## 2. 판매

### MBR_MASTER: 회원 (4,383행)
- **한 행 = 회원 1명**
- 키: `MBR_NO` (중복 0)
- 주요 컬럼:
  - `BIRTH_DT`: 생일 (27명 빈칸)
  - `JOIN_DT`: 가입일 (2021-06 ~ 2026-11)
  - `REGION_CD`: 지역, 11개
  - `MBR_GRADE_CD`: 등급. NORMAL 3,287 / GOLD 876 / VIP 220
  - `MBR_STAT_CD`: 상태. 10 정상 3,479 / 20 휴면 812 / 90 탈퇴 92

### BET_ORDER: 전표 (27,907행)
- **한 행 = 구매(또는 취소) 1건**
- 키: `ORDER_NO`

| 주요 컬럼 | 내용 |
|:--|:--|
| `ORDER_TYPE_CD` | SALE 23,802 / CANCEL 4,105. 취소 전표는 금액이 음수 |
| `ORIG_ORDER_NO` | 취소 전표가 가리키는 원래 전표. CANCEL 4,105건 중 3,461건에만 있음 |
| `MBR_NO` | 회원번호. 빈칸 4,921건은 비회원. 나머지 회원번호는 모두 `MBR_MASTER`에 있음 |
| `CHNL_CD`, `OTB_BRANCH_NO` | 채널(ONSITE 25,991 / OTB 1,543 / APP 360 / UNKNOWN 13), 장외발매소 지점 번호 |
| `SALE_DTM`, `BIZ_DT` | 판매 일시, 영업일 |
| `TICKET_CNT`, `TOTAL_AMT` | 마권 장수, 총액 |

### BET_TICKET: 마권 (523,416행)
- **한 행 = 전표 안의 베팅 1개**
- 키: `ORDER_NO` + `TICKET_SEQ`
- 주의: 이 키가 완전히 같은 중복 행이 1,052개 있습니다. 품질 관리 단계에서 처리할 예정입니다.

| 주요 컬럼 | 내용 |
|:--|:--|
| `RC_DT`, `RC_NO` | 어느 경주에 걸었는지 |
| `BET_TYPE_CD` | 승식. WIN 255,993 / PLC 160,114 / QNL 107,309 |
| `CHUL_NO`, `HR_NM` | 고른 말 |
| `CHUL_NO2`, `HR_NM2` | 복승(QNL)일 때 두 번째 말 |
| `UNIT_CNT`, `BET_AMT` | 구좌 수, 금액 (`BET_AMT` = `UNIT_CNT` × 100) |
| `TICKET_STAT_CD` | SOLD 512,032 / CANCEL 9,610 / VOID 1,774 |

- 모든 마권의 경주가 `RC_RACE`에 있고, 경주+마번이 `RC_ENTRY`에 있습니다.

---

## 3. 말·조교사

### HR_WEEKLY_SNAPSHOT: 말 주간 현황 (52,642행)
- **한 행 = 특정 주(`SNAPSHOT_DT`)의 말 1마리 상태**
- 53주 × 주당 약 1,000마리, 말은 모두 1,250마리입니다.
- 키: `SNAPSHOT_DT` + `HR_NM` (중복 0)

| 주요 컬럼 | 내용 |
|:--|:--|
| `HR_GRADE_CD` | 등급. 1~6, NONE(미등급) |
| `TR_GRP_NO`, `TR_NM`, `TR_EXTERNAL_YN` | 소속 조, 조교사. 외부마는 조 88, `TR_NM` NULL, `TR_EXTERNAL_YN`=Y (25,428행) |
| `TOT_*_CNT`, `Y1_*_CNT` | 통산·최근 1년 출전 수, 1·2·3착 수 |
| `PRIZE_AMT`, `RATING_VAL` | 상금, 레이팅 |
| `INTRO_AMT`, `INTRO_TYPE_NM` | 도입가(원), 도입 유형(개별 / 자가생산) |
| `SIRE_NM`, `DAM_NM` | 부마, 모마 |

- `RC_ENTRY`의 말은 모두 이 테이블에 있습니다.

### TR_WEEKLY_SNAPSHOT: 조교사 주간 현황 (954행)
- **한 행 = 특정 주의 조교사 1명** (53주 × 18명)
- 주요 컬럼: `TR_GRP_NO`(조), `TR_BIRTH_DT`, `TR_AGE`, `DEBUT_DT`, 통산·1년 성적
- `RC_ENTRY`의 조교사는 모두 이 테이블에 있습니다.

### HR_VET_HIST: 진료 기록 (1,488행) / HR_VET_TYPE_BRIDGE: 진료명 (1,664행)
- **HR_VET_HIST 한 행 = 진료 1건** (말 569마리, 2026-05-16 ~ 2026-11-18)
  - 주요 컬럼: `VET_DT`, `HR_NM`, `VET_NM`(원본 진료명), `REPORT_DT`
- **HR_VET_TYPE_BRIDGE 한 행 = 진료 1건 × 진료명 1개**
  - 원천에서 한 칸에 '정치,낭치'처럼 진료명이 여러 개 들어 있는 경우를 나눈 것입니다.
  - `VET_SEQ`로 진료 기록에 연결됩니다.
  - 진료명은 54종입니다. 많은 순서로 좌전지파행, 운동기질환 기타, 우전지파행, 정치, 감기입니다.

---

## 테이블을 잇는 키

| 연결 | 키 |
|:--|:--|
| 경주 ↔ 출전·배당·결과·매출·공지 | `RC_DT` + `RC_NO` |
| 출전 ↔ 배당 ↔ 결과 ↔ 마권 | `RC_DT` + `RC_NO` + `CHUL_NO` |
| 전표 ↔ 마권 | `ORDER_NO` |
| 회원 ↔ 전표 | `MBR_NO` |
| 출전 ↔ 말 현황 ↔ 진료 | `HR_NM` (말 고유번호가 없어서 이름으로 연결) |
| 출전 ↔ 조교사 현황 | `TR_NM` |
| 진료 ↔ 진료명 | `VET_SEQ` |

## 데이터가 있는 곳

| 단계 | 경로 | 상태 |
|:--|:--|:--|
| 원천 | `data/00_origin/` | CSV 11개 + JSONL 1개, 지저분한 원본 |
| Bronze | `data/01_bronze/` | 원천을 값 그대로 Parquet로 저장 → `docs/BRONZE.md` |
| Silver | `data/02_silver/` | 이름·타입·코드 표준화 → `docs/SILVER.md` |
| Silver 품질 관리 | `data/02_silver/clean/`, `_excluded/` | 중복 제외, 0원·늦은 취소 등 표시, 마명 보정 → `docs/품질관리.md` |
| Gold | `data/03_gold/` | 경주 출전 스타 스키마 (FCT_RACE_ENTRY + 차원 4개) → `docs/GOLD.md` |
