# Gold 공통 차원

- **코드:** `src/common/04_common_dims.py` (생성), `src/common/04_common_dims_check.py` (검증)
- **입력:** `data/02_silver/clean/` (D-012)
- **출력:** `data/03_gold/common/` 6개 차원
- **근거:** 팀 합의 D-013 ~ D-016 (`meta/decision_log.md`)

네 팩트(race_entry, horse_medical, race_sales, bet_cancel)가 함께 쓰는 차원입니다. 팩트 전용 차원(진료 유형, 나이대, 승식, 마권 상태 등)은 각자 팩트 폴더에 둡니다.

## 1. 차원 목록

| 차원 | 행 | 키 (업무 키 정렬 순번) | 미상 행 | 비고 |
|:--|--:|:--|:--|:--|
| `DIM_DATE` | 188 | `DATE_KEY` = YYYYMMDD | `0` | 2026-05-16 ~ 2026-11-18 연속 187일 + 미상. `RACE_DAY_YN` = 경주일(52일) |
| `DIM_RACE` | 387 | `RACE_KEY` (`RC_DT`, `RC_NO` 순) | `0` | 경주 386개 |
| `DIM_HORSE` | 4,127 | `HORSE_KEY` (`HR_NM`, `VALID_FROM_DT` 순) | `0` | SCD2. 말 1,250두, 버전 4,126개 |
| `DIM_TRAINER` | 19 | `TRAINER_KEY` (`TR_NM` 순) | `0` | 조교사 18명 |
| `DIM_MEMBER` | 4,385 | `MEMBER_KEY` (`MBR_NO` 순) | `0` | 회원 4,383명 + `NON_MEMBER`(키 4,384). `MEMBER_TYPE_CD`로 구분 |
| `DIM_CHANNEL` | 40 | `CHANNEL_KEY` (`CHNL_CD`, `OTB_BRANCH_NO` 순) | `0` | 앱·현장·장외 지점 37개. 채널 빈칸(`UNKNOWN`, 전표 13건)은 미상 행 |

미상 행은 키 0, 이름 컬럼 `UNKNOWN`, 나머지 NULL입니다. 날짜 미상은 `DATE_KEY = 0`, `FULL_DT` NULL입니다.

## 2. 팩트에서 연결하는 방법

| 차원 | 연결 조건 | 못 찾으면 |
|:--|:--|:--|
| `DIM_DATE` | 날짜를 YYYYMMDD 정수로 바꿔 `DATE_KEY`. 구매일·취소일·진료일처럼 역할이 여럿이면 FK 이름으로 구분 (예: `VET_DT_KEY`, `REPORT_DT_KEY`) | `0` |
| `DIM_RACE` | `RC_DT` + `RC_NO` | `0` |
| `DIM_HORSE` | `HR_NM` 같고 `VALID_FROM_DT ≤ 기준일 ≤ VALID_TO_DT`. 기준일: 경주는 경주일, 진료는 진료일, 취소 분석은 원구매일. 버전은 스냅샷 **다음 날**부터 유효하므로 기준일 **이전** 스냅샷의 속성이 됩니다 | `0` |
| `DIM_TRAINER` | `TR_NM` (진료처럼 조 번호만 있으면 `TR_GRP_NO`) | `0` |
| `DIM_MEMBER` | `MBR_NO`. 회원번호 빈칸(비회원)은 `MEMBER_TYPE_CD = 'NON_MEMBER'` 행의 키 | `0` |
| `DIM_CHANNEL` | `CHNL_CD` + `OTB_BRANCH_NO`. `CHNL_CD = 'UNKNOWN'`은 키 0 | `0` |

## 3. 기존 차원과 비교

| 차원 | 기존 | 공통으로 바뀐 점 |
|:--|:--|:--|
| race_entry `DIM_DATE` | 177일 (경주 기간) | 기존 177일은 키·값 그대로, 범위만 5/16 ~ 11/18로 넓어짐 |
| race_entry `DIM_RACE`·`DIM_HORSE`·`DIM_TRAINER` | | 미상 행(0)만 추가. 나머지 키·값 그대로 |
| horse_medical `DIM_HORSE` | 미상 행 포함 4,127 | 키·값 그대로. 미상 행 `HR_NM`만 NULL → `UNKNOWN` |
| horse_medical `DIM_TRAINER` | 18 | 미상 행(0)만 추가 |
| race_sales `DIM_RACE`·`DIM_CHANNEL`·`DIM_MEMBER`·`DIM_DATE` | 문자 키 (`2026-05-22\|1`, `OTB\|01`, `M0012346`, `NON_MEMBER`, `'20260522'`) | 정수 순번 키로 다시 연결. 날짜는 경주일 52일 → 연속 187일 |
| bet_cancel 차원 5개 | 해시 키, 소문자 컬럼, 팩트에 나온 값만 | 정수 순번 키, 대문자 컬럼, clean 전체 |

## 4. 검증 결과 (`src/common/04_common_dims_check.py`)

| 검증 | 결과 |
|:--|:--|
| 테이블마다 PK 중복·NULL 0, 미상 행(키 0) 1개 | 통과 |
| 행 수 = clean 기준 (경주 386, 조교사 18, 회원 4,383, 장외 지점 37 + 특수 행) | 통과 |
| `DIM_DATE` 연속, 경주일·진료일·보고일·스냅샷일·판매일 모두 포함, 범위 = 팀 합의 | 통과 |
| `DIM_HORSE` SCD2 기간 겹침·빈틈 없음, 현재 버전 1개, `VALID_FROM_DT` = 스냅샷 다음 날 | 통과 |
| 비회원 전표 4,921건, 회원 마스터에 없는 회원번호 0건 | 통과 |
| 기존 race_entry·horse_medical 차원은 키·값 그대로 포함 | 통과 |
| race_sales·bet_cancel 팩트의 경주·날짜·회원·채널·말이 모두 공통 차원에 연결됨 | 통과 |
| 두 번 실행해 결과 파일 해시 동일 | 통과 |

## 5. 다음 단계 (각자)

| 팩트 | 공통 차원 전환 |
|:--|:--|
| race_entry | 완료 (팩트 전환 전후 바이트까지 동일) |
| horse_medical | 진행 예정 |
| race_sales | 진행 예정 |
| bet_cancel | 진행 예정 |


1. 팩트 코드가 자기 차원 대신 `data/03_gold/common/`을 읽어 키를 붙이도록 수정
2. 공통 차원과 겹치는 자기 폴더의 차원 파일 삭제 (팩트 전용 차원은 유지)
3. 다시 실행 후 대사: 팩트 행 수, 측정값 합계, PK 중복 0, FK 누락 0
