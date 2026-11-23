# mlo-03-p2-team3

원천 데이터 → Bronze → Silver → 품질 관리 → Gold → AI Ready Data

> **Bronze → Silver → 품질 관리 → Gold(팩트 4개 + 공통 차원)까지 완료했습니다.** AI Ready Data는 진행 중입니다.
> 단계별 코드와 문서는 `develop` 브랜치에 있습니다. 아래 문서 링크는 `develop` 브랜치를 가리킵니다.

## 1. 팀 소개

- **팀명:** (호올스)

| 이름 | GitHub | 담당 팩트 (Gold) |
|:--|:--|:--|
| 원주 | [@wonju0516](https://github.com/wonju0516) | 경주 출전 `FCT_RACE_ENTRY` |
| 세은 | [@wlstpdms](https://github.com/wlstpdms) | 말 진료 `FCT_HORSE_MEDICAL` |
| 희정 | [@gmlwjd0055](https://github.com/gmlwjd0055) | 마권 매출 `race_sales` |
| 은빈 | [@eunbinko](https://github.com/eunbinko) | 배팅 취소 `FCT_BET_SELECTION_CANCEL_50S` |

## 2. 프로젝트 개요

### 프로젝트명
말 많은 데이터 

### 프로젝트 소개
- **주제:** 제주 경마(2026-05-22 ~ 2026-11-14, 경주 386개) 운영 데이터
- **원천:** 6개 시스템, 12개 파일

| 원천 시스템 | 파일 | 내용 |
|:--|:--|:--|
| 발매 (bet) | `bet_order.csv`, `bet_ticket.csv` | 전표 27,907건, 마권 523,416건 |
| 회원 (mbr) | `MBR_MASTER.csv` | 회원 4,383명 |
| 말 관리 (hms) | `HR_WEEKLY_SNAPSHOT.csv`, `TR_WEEKLY_SNAPSHOT.csv` | 말·조교사 주간 스냅샷 |
| 경주 운영 (rms) | `RC_RACE.csv`, `RC_ENTRY.csv`, `RC_ODDS.csv`, `RC_RESULT.csv`, `RC_SALES.csv` | 경주, 출전표, 배당, 결과, 매출 |
| 수의 진료 (vms) | `HR_VET_HIST.csv` | 진료 이력 1,488건 |
| 변경 이벤트 (mongodb) | `race_change_events.jsonl` | 말 취소·기수 변경 149건 |

- **하는 일:** 형식과 품질이 제각각인 원천을 **Bronze(원본 보존) → Silver(표준화·품질 관리) → Gold(스타 스키마) → AI Ready Data** 순서로 가공합니다. 단계마다 앞 단계와 숫자를 맞춰 보는 검증(대사)을 합니다.

### 프로젝트 필요성 (AS-IS)
원천 데이터에는 아래 문제가 있습니다. 자세한 내용은 [`docs/AS-IS.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/AS-IS.md)에 있습니다.

| 문제 | 예 |
|:--|:--|
| 이름이 제각각 | `member_no` / `MBR_NO`, 같은 `ticket_cnt`가 파일마다 다른 뜻 |
| 날짜 형식이 섞임 | 회원 생일 `YYYYMMDD` / `YYYY-MM-DD` / `YYYY.MM.DD` / 빈칸 |
| 코드값 불일치 | 승식 영문·한글 혼용(`WIN` / `단승`), 상태값 대소문자 혼용 |
| 한 칸에 여러 값 | 마체중 `279+14`, 날씨·주로 `날씨: 흐림 주로: 다습 (14%)`, 진료명 `정치,낭치` |
| 단위·표기 혼용 | 상금 `만원`, 도입가 `천원`, 매출 쉼표 문자열 |
| 의미가 다른 값이 같은 칸에 | 순위 칸에 `94`(경주제외)·`95`(출주취소), 조교사 칸에 `외부마` |
| 중복·불일치 | 마권 완전 중복 1,052행, 전표 헤더와 마권 합계 불일치 93건 |

### 프로젝트 목표
- AI가 바로 쓸 수 있는 **정확하고, 추적 가능하고, 재현 가능한** 데이터를 만듭니다.
  - **정확:** 표준 코드·타입으로 통일하고, 품질 문제를 규칙과 근거(결정 ID)로 처리
  - **추적:** 모든 행이 원천 파일과 행 번호(`_SRC_ROW_NO`)로 거슬러 올라감
  - **재현:** 다시 실행해도 같은 결과 (정렬 고정, 실행 시각을 본문에 넣지 않음)
- 데이터의 양보다 **얼마나 더러운 데이터를 얼마나 깔끔하게 만들었는지**가 핵심입니다.

## 3. 기술 스택

| 구분 | 기술 스택 |
|:---:|:---|
| **언어** | ![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white) |
| **데이터 처리** | ![pandas](https://img.shields.io/badge/pandas-3.1.1-150458?style=flat-square&logo=pandas&logoColor=white) ![PyArrow](https://img.shields.io/badge/PyArrow-26.0.1-E95420?style=flat-square) |
| **저장 형식** | ![Parquet](https://img.shields.io/badge/Parquet-Data-50ABF1?style=flat-square) ![CSV](https://img.shields.io/badge/CSV-Metadata-217346?style=flat-square) ![Markdown](https://img.shields.io/badge/Markdown-Documentation-000000?style=flat-square&logo=markdown&logoColor=white) |


## 4. WBS

2026-11-20(금) 커밋 기록 기준입니다.

| 시간 | 작업 | 담당 |
|:--|:--|:--|
| 09:40 ~ 11:49 | 저장소 생성, 디렉토리 구조 | 세은, 원주 |
| 12:54 ~ 14:11 | 팀 공용 원천 데이터·대사 규칙 공유 | 세은 |
| 14:33 ~ 15:54 | 원천 → Bronze → Silver 표준화 (각자) | 전원 |
| 15:14 | 데이터 안내서, 컬럼 사전 | 원주 |
| 16:36 ~ 17:34 | 품질 관리, Gold 스타 스키마 (각자), AS-IS 정리 | 전원 |
| 17:46 ~ 18:01 | 공용 Bronze·Silver `develop` 병합 (PR #1, #2) | 원주 |
| 18:09 ~ 19:57 | 공용 품질 관리 통합 (PR #3 ~ #6) | 희정, 세은, 원주 |
| 11-23 | Gold 팩트 4개 `develop` 병합 (PR #8, #9, #11, #12, #13) | 전원 |
| 11-23 | 공통 차원 규칙 합의(D-013 ~ D-016), 공통 차원 6개 생성 (PR #14) | 전원 합의, 원주 |
| 11-23 | 팩트 4개를 공통 차원으로 전환 (PR #15 ~ #18) | 원주, 세은, 희정, 은빈 |
| 진행 중 | AI Ready Data (출전마 3착 이내 예측 테이블) | 전원 |
| 예정 | `develop` → `main` | 전원 |

## 5. 요구사항 명세서

| 단계 | 해야 하는 일 | 상태 |
|:--|:--|:--|
| Bronze | 원천 12개를 값 그대로 Parquet로 저장. 출처(`_SRC_SYSTEM`, `_LOAD_FILE`, `_LOAD_DTM`, `_SRC_ROW_NO`) 기록. 원천 행 수 = Bronze 행 수 | 완료 |
| 표준화 | 컬럼명 UPPER_SNAKE, 날짜·시각·숫자 타입 변환, 코드값 통일, 한 칸 여러 값 분리. 행은 지우지 않음. 바뀐 내용은 데이터 사전, NULL이 된 원천값은 이슈 로그에 기록 | 완료 |
| 품질 검증 | 품질 규칙 26개(유일성·완전성·유효성·일관성·참조 무결성·시점). 규칙마다 근거 결정 ID(D-001 ~ D-012) | 완료 |
| Silver | 표준화 결과는 그대로 두고, 품질 처리 결과를 `clean/`(유지 행 + 표시 컬럼)과 `_excluded/`(제외 행)로 나눠 저장. 표준화 행 수 = clean + 제외 | 완료 |
| Gold | 팀원마다 스타 스키마 1개. `clean/`만 입력(D-012). PK 중복 0, 팩트 키가 모두 차원에 있어야 함. 겹치는 차원은 공통 차원 6개로 통합(D-013 ~ D-016) | 완료 (4/4) |
| AI Ready Data | 출전마 1두 = 1행, 정답 = 3착 이내. 네 팩트를 공통 키로 붙이고, 경주 출발 시각 이전 정보만 피처로 사용. 학습·검증은 날짜로 분할 | 진행 중 |

## 6. ERD

### 경주 출전 `FCT_RACE_ENTRY` (원주)

```mermaid
erDiagram
    DIM_DATE ||--o{ FCT_RACE_ENTRY : "DATE_KEY"
    DIM_RACE ||--o{ FCT_RACE_ENTRY : "RACE_KEY"
    DIM_HORSE ||--o{ FCT_RACE_ENTRY : "HORSE_KEY (경주일 기준 버전)"
    DIM_TRAINER ||--o{ FCT_RACE_ENTRY : "TRAINER_KEY"

    FCT_RACE_ENTRY {
        int RACE_KEY PK
        int CHUL_NO PK
        int DATE_KEY FK
        int HORSE_KEY FK
        int TRAINER_KEY FK
        int START_CNT
        int WIN_CNT
        int PLACE_CNT
        double EXPECT_WIN
    }
```

- **그레인 (한 행의 의미):** 경주별 출전마 1두 (`RC_DT` + `RC_NO` + `CHUL_NO`). 출전표 1행 = 팩트 1행, 3,666행
- **측정값**

| 측정값 | 계산 |
|:--|:--|
| `START_CNT` | 실제로 뛰었으면 1, 경주제외(94)·출주취소(95)면 0 (`RC_RESULT`) |
| `WIN_CNT` | 착순 1이면 1 (`RC_RESULT`) |
| `PLACE_CNT` | 착순 3 이하면 1 (`RC_RESULT`) |
| `EXPECT_WIN` | 경주 안에서 (1 / 단승 배당) ÷ Σ(1 / 단승 배당). 뛰지 않은 말은 0 (`RC_ODDS`) |

- `DIM_HORSE`는 SCD2입니다. 경주일 **이전** 가장 최근 스냅샷의 말 속성을 씁니다.
- 자세한 내용: [`docs/gold/race_entry.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/race_entry.md)

### 말 진료 `FCT_HORSE_MEDICAL` (세은)

```mermaid
erDiagram
    DIM_DATE ||--o{ FCT_HORSE_MEDICAL : "VET_DT_KEY / REPORT_DT_KEY"
    DIM_HORSE ||--o{ FCT_HORSE_MEDICAL : "HORSE_KEY (진료일 기준 버전)"
    DIM_TRAINER ||--o{ FCT_HORSE_MEDICAL : "TRAINER_KEY"
    DIM_AGE_GROUP ||--o{ FCT_HORSE_MEDICAL : "AGE_GROUP_KEY"
    FCT_HORSE_MEDICAL ||--|{ BRIDGE_HR_VET_TYPE : "VET_SEQ"
    DIM_VET_TYPE ||--o{ BRIDGE_HR_VET_TYPE : "VET_TYPE_KEY"
```

- **그레인:** 진료 기록 1건 (`VET_SEQ`), 1,488행. 측정값 `VET_CNT` = 1
- 한 진료가 여러 유형에 속할 수 있어(`정치,낭치`) 브리지 `BRIDGE_HR_VET_TYPE`(1,662행)로 유형 53개에 연결합니다.
- 진료일 이전 스냅샷이 없는 71건은 말 키 0(미상)으로 연결합니다(D-007, D-015).
- 자세한 내용: [`docs/gold/horse_medical.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/horse_medical.md)

### 마권 매출 `race_sales` (희정)

```mermaid
erDiagram
    DIM_RACE ||--o{ race_sales : "RACE_KEY"
    DIM_DATE ||--o{ race_sales : "DATE_KEY / SALE_DATE_KEY"
    DIM_CHANNEL ||--o{ race_sales : "CHANNEL_KEY"
    DIM_MEMBER ||--o{ race_sales : "MEMBER_KEY"
    DIM_BET_TYPE ||--o{ race_sales : "BET_TYPE_CD"
    DIM_TICKET_STATUS ||--o{ race_sales : "TICKET_STAT_CD"
```

- **그레인:** 마권 1장 (`ORDER_NO` + `TICKET_SEQ`), 522,364행. 발매·취소·무효를 모두 보존합니다.
- **측정값:** 발매액, 취소액, 무효액, 취소 차감 후 금액, 판매 장수
- 비회원 마권 106,647장은 `NON_MEMBER` 키로, 채널이 빈칸인 마권 308장은 채널 키 0으로 연결합니다(D-016).
- 자세한 내용: [`docs/gold/race_sales.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/race_sales.md)

### 50대 단승 취소 `FCT_BET_SELECTION_CANCEL_50S` (은빈)

```mermaid
erDiagram
    DIM_MEMBER ||--o{ FCT_BET_SELECTION_CANCEL_50S : "MEMBER_KEY"
    DIM_HORSE ||--o{ FCT_BET_SELECTION_CANCEL_50S : "HORSE_KEY"
    DIM_RACE ||--o{ FCT_BET_SELECTION_CANCEL_50S : "RACE_KEY"
    DIM_CHANNEL ||--o{ FCT_BET_SELECTION_CANCEL_50S : "CHANNEL_KEY"
    DIM_DATE ||--o{ FCT_BET_SELECTION_CANCEL_50S : "구매일 / 취소일 / 경주일 / 스냅샷일"
```

- **그레인:** 50대 회원의 단승(WIN) 구매 선택 1건 (`FACT_ID`), 41,141행
- **정답 라벨:** `HAS_VERIFIED_CUSTOMER_CANCEL` (확인된 고객 취소 926건, 판단 보류 102건)
- 구매 시점의 말 나이·성별, 최근 1년·통산 성적을 함께 담은 분석용 팩트입니다.

### 공통 차원 (D-013 ~ D-016)

여러 팩트가 함께 쓰는 차원은 `data/03_gold/common/`에 하나만 둡니다. 팩트 전용 차원(진료 유형, 나이대, 승식, 마권 상태)만 각자 폴더에 있습니다.

| 차원 | 행 | 키 | 쓰는 팩트 |
|:--|--:|:--|:--|
| `DIM_DATE` | 188 | `DATE_KEY` = YYYYMMDD. 2026-05-16 ~ 11-18 연속, `RACE_DAY_YN` | 4개 모두 |
| `DIM_RACE` | 387 | 경주일 + 경주번호 순번 | 출전, 매출, 취소 |
| `DIM_HORSE` | 4,127 | SCD2. `VALID_FROM_DT ≤ 기준일 ≤ VALID_TO_DT` | 출전, 진료, 취소 |
| `DIM_TRAINER` | 19 | 조교사명 순번 | 출전, 진료 |
| `DIM_MEMBER` | 4,385 | 회원 4,383 + `NON_MEMBER` | 매출, 취소 |
| `DIM_CHANNEL` | 40 | 앱·현장·장외 지점 37개 | 매출, 취소 |

- 모든 차원에 미상 행(키 0, 이름 `UNKNOWN`)이 있습니다. 차원에서 못 찾은 값은 키 0으로 연결합니다.
- 키는 업무 키로 정렬한 순번이라, 같은 `clean/`이면 다시 실행해도 같은 키가 나옵니다.
- 자세한 내용: [`docs/gold/common.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/gold/common.md)

## 7. 주요 프로시저

```mermaid
flowchart LR
    O[원천 12개<br/>CSV·JSONL] --> B[Bronze<br/>01_bronze.py]
    B --> S[Silver 표준화<br/>02_normalize.py]
    S --> Q[품질 관리<br/>03_quality.py]
    Q --> C[clean/ · _excluded/]
    C --> D[공통 차원<br/>src/common/]
    C --> G[Gold 팩트 4개<br/>src/팩트/]
    D --> G
    G --> A[AI Ready Data<br/>진행 중]
```

| 단계 | 실행 | 검증 | 검증 내용 |
|:--|:--|:--|:--|
| Bronze | `src/01_bronze.py` | `src/01_bronze_check.py` | 원천 행 수 = Bronze 행 수, 값 그대로 적재, 원천 파일 해시 |
| Silver 표준화 | `src/02_normalize.py` | `src/02_normalize_check.py` | Bronze 행 1:1 보존, 변환 실패·코드표 밖 값 0건, NULL 기대 건수, NULL이 된 원천값이 모두 이슈 로그에 있는지 |
| 품질 관리 | `src/03_quality.py` | `src/03_quality_check.py` | 표준화 = clean + 제외, 플래그 건수 = 팀 기준, 처리 코드 없이 다시 계산해 행 단위 일치, 모든 규칙에 결정 ID |
| Gold 공통 차원 | `src/common/04_common_dims.py` | `src/common/04_common_dims_check.py` | PK 중복 0, 미상 행 1개, 행 수 = clean, 날짜 연속, SCD2 기간 겹침·빈틈 없음, 팩트 4개의 키가 모두 공통 차원에 있음 |
| Gold 팩트 | `src/<팩트>/` 생성 코드 | 팩트별 검증 (check 스크립트, `--check`, 검증 기록 파일) | PK 중복 0, 팩트 키가 모두 차원에 있음, 행 수·측정값을 clean과 대사 |
| 공통 | — | 두 번 실행 | 결과 파일 해시가 같은지 (재현성) |

## 8. 수행 결과

### 행 수 대사

| 원천 | 원천 | Bronze | Silver 표준화 | clean | 제외 |
|:--|--:|--:|--:|--:|--:|
| bet_ticket | 523,416 | 523,416 | 523,416 | 522,364 | 1,052 (완전 중복) |
| bet_order | 27,907 | 27,907 | 27,907 | 27,907 | 0 |
| MBR_MASTER | 4,383 | 4,383 | 4,383 | 4,383 | 0 |
| HR_WEEKLY_SNAPSHOT | 52,642 | 52,642 | 52,642 | 52,642 | 0 |
| RC_ENTRY / RC_ODDS / RC_RESULT | 3,666 | 3,666 | 3,666 | 3,666 | 0 |
| RC_SALES | 3,088 | 3,088 | 2,702 + 합계 386 | 2,702 + 386 | 0 |
| HR_VET_HIST | 1,488 | 1,488 | 1,488 (진료명 브리지 1,664) | 1,488 (브리지 1,662) | 0 |

### 단계별 전후 비교 (예)

| 항목 | 원천 (Bronze) | Silver |
|:--|:--|:--|
| 회원 생년월일 | `19571206`, `1957-10-25`, `1951.06.03` | `1957-12-06`, `1957-10-25`, `1951-06-03` (DATE) |
| 승식 | `WIN`, `PLC`, `QNL`, `단승`, `연승`, `복승` | `WIN`, `PLC`, `QNL` |
| 마체중 | `279+14` | 체중 279, 증감 14 (kg) |
| 날씨·주로 | `날씨: 흐림  주로: 다습  (14%)` | 날씨 `CLOUDY`, 주로 `MOIST`, 함수율 14 |
| 상금 | `순위상금: 700만원 322만원 210만원 98만원 70만원` | 1~5위 7,000,000 / 3,220,000 / 2,100,000 / 980,000 / 700,000 (원) |

### 품질 관리 결과 (팀 기준 숫자와 일치)

| 항목 | 건수 | 처리 |
|:--|--:|:--|
| 마권 완전 중복 (D-002) | 1,052 | 제외 (`_excluded/`) |
| 0원 마권 (D-003) | 3,632 | 표시 `INVALID_YN` |
| 늦은 취소 마권 / 전표 (D-004) | 1,000 / 546 | 표시 `LATE_CANCEL_YN` |
| 빈 마명 보정 (D-005) | 1,560 | 출전표 마명으로 보정, `HR_NM_FILLED_YN` |
| 전표 헤더 불일치 / 원전표 없는 취소 (D-006) | 93 / 644 | 표시 |
| 진료 조 불일치 / 이전 스냅샷 없음 (D-007) | 11 / 71 | 표시 |

### Gold 결과

| 팩트 | 행 | 대사 (clean 기준) | 미상 키(0) |
|:--|--:|:--|:--|
| 경주 출전 | 3,666 | 출전표 1:1. 출주 3,644 / 1착 386 / 3착 안 1,158, 우승률 10.59% | 없음 |
| 말 진료 | 1,488 | 진료 1,488 = `SUM(VET_CNT)`, 유형 연결 1,662 | 말 71 (이전 스냅샷 없음) |
| 마권 매출 | 522,364 | 마권 1:1. 발매액 1,903,091,700원, 취소 차감 후 1,862,026,900원, 판매 507,383장 | 채널 308 (채널 빈칸) |
| 50대 단승 취소 | 41,141 | 분석 대상 39,284, 확인된 취소 926 | 취소일 40,187 (취소 없음) |

- 테이블마다 PK 중복 0이고, 팩트 키는 모두 차원에 있습니다. Gold 입력에서 제외한 행은 0입니다.
- 전체 파이프라인(Bronze → 공통 차원 → 팩트 4개)을 다시 실행해도 결과 파일이 바이트까지 같습니다.

자세한 보고서: [`docs/품질관리.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/품질관리.md), [`docs/DATA_GUIDE.md`](https://github.com/encore-ai-campus/mlo-03-p2-team3/blob/develop/docs/DATA_GUIDE.md)

## 9. 한 줄 회고

| 이름 | 회고 |
|:--|:--|
| 원주 | (작성 예정) |
| 세은 | (작성 예정) |
| 희정 | (작성 예정) |
| 은빈 | (작성 예정) |
