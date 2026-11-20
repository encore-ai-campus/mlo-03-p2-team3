# Silver 표준화 작업 기록

## 적용 기준

`docs/매핑_규칙서.md`의 공통 원칙, 테이블/컬럼 매핑, 타입·날짜 규칙, 코드표와 분리 규칙을 기준으로 `src/load_silver.py`를 작성했습니다. Bronze 파일을 읽기만 하며 결과는 `data/02_silver/`에 테이블별 Parquet로 저장합니다.

## 구현 범위

- 입력: `data/01_bronze/`의 12개 Parquet 파일
- 출력: `BET_ORDER`, `BET_TICKET`, `MBR_MASTER`, `HR_WEEKLY_SNAPSHOT`, `TR_WEEKLY_SNAPSHOT`, `RC_RACE`, `RC_ENTRY`, `RC_ODDS`, `RC_RESULT`, `RC_SALES`, `RC_SALES_TOTAL`, `HR_VET_HIST`, `HR_VET_TYPE_BRIDGE`, `RC_CHANGE_EVENT`
- 컬럼 이름은 규칙서의 UPPER_SNAKE 표준명으로 바꾸고, `_SRC_FILE`, `_LOAD_DTM` 출처 컬럼은 Silver에도 유지합니다.
- 앞뒤 공백과 빈 값 표기(`-----`)를 정리하고, 날짜·시간·숫자·코드를 규칙서대로 변환합니다. 파싱 불가능한 날짜·숫자나 매핑이 명시된 코드 필드의 미등록 값은 임의 변환하지 않고 오류로 중단합니다.
- Parquet는 임시 파일에 쓴 뒤 교체합니다. 쓰기 전후 행 수를 검사하고 출처 메타데이터 컬럼이 문자열로 저장됐는지도 확인합니다.
- JSON 중첩 필드의 숫자가 결측값 때문에 실수형으로 추론되는 경우도 문자열 변환 없이 안전하게 정수/소수 처리합니다. 빈 채널 등 Pandas `NA` 결측도 규칙에 맞게 처리합니다.
- Silver Parquet 저장과 행 수 확인이 끝나면 `meta/silver_change_log.csv`에 입력·출력 행 수, 컬럼 목록 및 추가·제외 컬럼을 기록합니다.

## 특별 분리 및 행 수 대사

- 1:1 테이블은 Silver 출력 행 수가 Bronze 입력 행 수와 같은지 확인합니다.
- `RC_SALES`: `POOL_NM='합계'`를 `RC_SALES_TOTAL`로 분리합니다. 두 Silver 테이블의 행 수 합계가 Bronze `RC_SALES` 행 수와 같아야 합니다.
- `HR_VET_HIST`: 기본 Silver 행 수는 Bronze 행 수와 같게 유지합니다. 쉼표로 구분된 진료명을 `HR_VET_TYPE_BRIDGE`의 여러 행으로 펼치며, `VET_SEQ`로 기본 테이블을 연결합니다. 브리지 행은 규칙서대로 입력 행 수보다 많을 수 있습니다.
- 규칙서의 제외 컬럼(`PRD_NM`, `HR_BREED`, 중복 원천 순위 등)은 해당 표준 테이블에서 제외합니다. 이는 행 삭제가 아니라 컬럼 제거입니다.

## 주요 변환

- 일자: `YYYYMMDD`, `YYYY-MM-DD`, `YYYY.MM.DD`, `YYYY/MM/DD`를 날짜 타입으로 변환합니다.
- 일시: 판매·이벤트 시각을 KST 시간대가 지정된 timestamp로 변환하고, `HH:MI`는 초 `00`으로 보정합니다.
- BET_ORDER: `OTBnn` 채널을 `CHNL_CD='OTB'`, `OTB_BRANCH_NO='nn'`으로 분리하고 빈 채널은 `UNKNOWN`으로 기록합니다.
- HR 주간 스냅샷: 성별·등급 코드 변환, `외부마`의 조교사명 비움 및 외부 여부 표시, 도입가 천원 단위 변환을 적용합니다.
- RC_RACE: 경주 등급·부담 방식, 조건명·경주명, 날씨·주로·함수율, 상금, 거리·경주일차, 출발 시각을 분리합니다.
- RC_ODDS: 구간 기록은 공백 분리 대신 7글자 고정폭으로 7개 구간을 파싱합니다.
- RC_RESULT: 94/95 순위 상태, 마체중 증감, 경주 기록 초, 착차 코드, 통과 순위를 각각 표준 컬럼으로 분리합니다.
- RC_CHANGE_EVENT: Bronze에 JSON 문자열로 저장된 중첩 객체를 펼쳐 경주·말·변경 정보를 표준 컬럼에 배치합니다. TRACK_STATUS에는 경주·말 정보가 비어 있도록 유지합니다.

## 실행

프로젝트 루트에서 실행합니다.

```powershell
python src/load_silver.py
```

필요 패키지는 `pandas`와 `pyarrow`입니다. 실행 결과 요약과 불일치가 발생한 입력/출력 행 수는 콘솔에 출력됩니다.
