# 진료 이력 데이터 사전

공용 원천과 폴더 구조는 `main`에서 공유하고, 이 문서의 Bronze·Silver 처리 및 산출물은 진료 작업 브랜치 `feat/fct-horse-medical`에서 관리한다.

## 단계별 입력·출력 파일

| 단계 | 입력 파일 | 생성 파일 | 현재 원천 기준 |
|---|---|---|---|
| Bronze 적재 | `data/00_origin/horse/HR_VET_HIST.csv` | `data/01_bronze/HR_VET_HIST_RAW.parquet` | 1,488행 × 6열 |
| Bronze 적재 기록 | `data/00_origin/horse/HR_VET_HIST.csv`, `data/01_bronze/HR_VET_HIST_RAW.parquet` | `data/01_bronze/HR_VET_HIST_LOAD.json` | 원천·대상 경로, KST 적재 시각, SHA-256, 컬럼별 보존 규칙 |
| Silver 진료 이력 | `data/01_bronze/HR_VET_HIST_RAW.parquet` | `data/02_silver/HR_VET_HIST.parquet` | 1,488행 × 7열 |
| Silver 진료 유형 브리지 | `data/01_bronze/HR_VET_HIST_RAW.parquet`의 `VET_NM_RAW`와 레코드 순서 | `data/02_silver/HR_VET_TYPE_BRIDGE.parquet` | 1,664행 × 2열 |

## Bronze

`VET_DT_RAW`, `HR_NAME`, `TR_GRP_NO`, `VET_PLACE_NM`, `VET_NM_RAW`, `REPORT_DT`를 원래 순서와 이름으로 읽어 Parquet의 문자열 컬럼에 그대로 옮긴다. 행 순서, 빈 문자열, 날짜 표기, 조 번호의 앞자리 0, 쉼표가 포함된 진료 문구를 모두 보존한다. 컬럼명·날짜·값의 표준화는 Silver에서 적용한다.

`HR_VET_HIST_LOAD.json`에는 원천 및 대상 경로, SHA-256, KST 적재 시각, 양쪽 행·열 수, 컬럼별 처리 규칙과 비교 결과를 기록한다. 결정 ID `VET-BR-01`은 원천과 Bronze의 행·열 수, 컬럼명, 순서, 셀 값 일치를 검증하는 저장소 규칙이다.

## Silver

적재 기록의 SHA-256과 Bronze Parquet가 일치하는지 확인한 뒤, 아래 매핑을 Bronze 파일의 컬럼에 적용한다.

| Bronze 컬럼 | Silver 테이블과 컬럼 | 타입 | 처리 |
|---|---|---|---|
| 원천 레코드 순서 | `HR_VET_HIST.VET_SEQ` | INT | 헤더를 제외한 원천 레코드 순서대로 1부터 부여 |
| `VET_DT_RAW` | `HR_VET_HIST.VET_DT` | DATE | `YYYY.MM.DD`를 날짜로 파싱 |
| `HR_NAME` | `HR_VET_HIST.HR_NM` | STRING | 명칭 변경 및 양끝 공백 제거 |
| `TR_GRP_NO` | `HR_VET_HIST.TR_GRP_NO` | STRING | 양끝 공백 제거, 최대 두 글자 및 앞자리 0 유지 |
| `VET_PLACE_NM` | `HR_VET_HIST.VET_PLACE_NM` | STRING | 양끝 공백 제거 |
| `VET_NM_RAW` | `HR_VET_HIST.VET_NM` | STRING | 전체 진료 문구 유지 및 양끝 공백 제거 |
| `REPORT_DT` | `HR_VET_HIST.REPORT_DT` | DATE | `YYYYMMDD`를 날짜로 파싱 |
| 원천 레코드 순서 | `HR_VET_TYPE_BRIDGE.VET_SEQ` | INT | 해당 진료 이력과 같은 키로 연결 |
| `VET_NM_RAW` | `HR_VET_TYPE_BRIDGE.VET_TYPE_NM` | STRING | 쉼표로 나누고 각 항목의 양끝 공백을 제거한 뒤 값이 있는 항목을 원래 순서대로 저장 |

| 결정 ID | 검증 기준 | 근거 |
|---|---|---|
| `VET-SL-01` | Bronze 파일과 적재 기록의 해시가 일치해야 한다. Silver 진료 이력의 행 수는 Bronze와 같고, 브리지의 행 수는 유효한 진료명 항목 수와 같아야 한다. | 팀 공용 규칙서 1장, 7장, 10장 및 저장소의 Silver 표준화 규칙 |
| `VET-SL-02` | 빈 문자열, 공백, 하이픈으로만 된 표시는 NULL로 저장한다. 날짜가 유효한 지정 형식인지 확인하며, 두 글자를 넘는 조 번호는 오류로 처리한다. | 팀 공용 규칙서 1장, 4장, 5장, 10장 |

진료 이력에는 팀 매핑에서 별도로 지정한 논리값 컬럼이 없다. 진료 이력의 중복은 Silver 표준화에서 유지한다.

```powershell
python -m pip install -r requirements.txt
python src/horse_medical.py bronze
python src/horse_medical.py silver
```
