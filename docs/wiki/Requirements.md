# 요구사항 명세서

| ID | 단계 | 핵심 요구사항 | 검증 방법 | 결과 |
| --- | --- | --- | --- | --- |
| B-01 | Bronze | 원천을 값 변경 없이 Parquet로 보존하고 파일별 행 수를 일치시킨다. | [01_bronze_check.py](../../src/01_bronze_check.py) | ✅ 12개·625,411행 일치 |
| B-02 | Bronze | 원천 파일·적재 시각·행 번호·해시를 기록해 출처와 재적재 이력을 추적한다. | [01_bronze_check.py](../../src/01_bronze_check.py) · 적재 로그 | ✅ 출처·원천 해시 확인 |
| N-01 | 표준화 | 컬럼명·날짜·타입·코드·단위를 통일하고 데이터 사전에 기록한다. | [02_normalize_check.py](../../src/02_normalize_check.py) · 사전/스키마 대조 | ✅ 변환 실패·코드표 밖 값 0건 |
| N-02 | 표준화 | 기본 행을 보존하고, 매출 합계 분리·진료 브리지 확장은 출력 단위에 맞게 대사한다. | [02_normalize_check.py](../../src/02_normalize_check.py) | ✅ 매출 3,088 = 2,702 + 386, 진료명 항목 1,664개 |
| N-03 | 표준화 | 원천값의 변경·NULL 처리·제외 사유를 기록한다. | [02_normalize_check.py](../../src/02_normalize_check.py) · 데이터 사전·이슈 로그 | ✅ 원천 컬럼 기록·값 보존 대사 통과 |
| Q-01 | 품질 검증 | 6개 품질 차원의 규칙을 정의하고 근거 결정 ID를 연결한다. | [03_quality_check.py](../../src/03_quality_check.py) · 결정 로그 | ✅ 26개 규칙 근거 확인 |
| Q-02 | 품질 검증 | 키·금액·참조·시점을 점검하고 위반 행의 처리 근거를 남긴다. | [03_quality_check.py](../../src/03_quality_check.py) · 규칙별 결과 | ✅ 확인용 16개 규칙 위반 0, 표시·보정 이력 보존 |
| S-01 | Silver | 완전 중복을 분리 보존하고 입력 = 유지 + 제외, 유지·제외 겹침 0을 확인한다. | [03_quality_check.py](../../src/03_quality_check.py) | ✅ 마권 523,416 = 522,364 + 1,052행 |
| S-02 | Silver | 마명을 근거에 따라 보정하고 0원·늦은 취소·불일치는 플래그로 보존한다. | [03_quality_check.py](../../src/03_quality_check.py) | ✅ 마명 1,560행 보정·플래그 재계산 일치 |
| S-03 | Silver | 정제 결과를 공용 clean으로 관리하고 버전·파일 해시를 고정한다. | [clean manifest](../../data/02_silver/clean/_manifest.json) · SHA-256 대조 | ✅ 14개 파일 일치 |
| G-01 | Gold | 같은 clean에서 업무별 grain에 맞는 팩트와 공통 차원을 생성한다. | 팩트별 입력·grain 대사 | ✅ 팩트 4개·공통 차원 6개 |
| G-02 | Gold | PK 중복·NULL과 FK 누락이 없어야 하며 말의 SCD2 기준일을 지킨다. | [공통 차원 검증](../../src/common/04_common_dims_check.py) · 팩트별 키/시점 검증 | ✅ 키 오류 0건·기간 검증 통과 |
| G-03 | Gold | 팩트·브리지의 행 수와 측정값을 해당 입력·집계 정의에 맞춰 대사한다. | [팩트별 검증 결과](Results.md) | ✅ 행 수·금액·건수 일치 |
| G-04 | Gold | 컬럼 이름이 매핑 규칙서 13장(Gold 이름 규칙)을 따르고, 종합 데이터 사전과 실제 파일이 같다. | [04_gold_naming_check.py](../../src/common/04_gold_naming_check.py) | ✅ 이름 위반 0, 사전 대조 18개 테이블 일치 |
| A-01 | AI Ready | 실제 출주마 1두를 1행으로 구성하고 미출주마는 사유와 함께 별도 보존한다. | [05_ai_ready_check.py](../../src/ai_ready/05_ai_ready_check.py) | ✅ 유지 3,644 + 제외 22 = 3,666행, PK 중복 0 |
| A-02 | AI Ready | 출발 전 정보로 피처를 구성하고 정답·최종 배당을 학습 피처와 분리한다. | [05_ai_ready_check.py](../../src/ai_ready/05_ai_ready_check.py) · 과거 성적/진료/거래 재계산 | ✅ 시점별 재계산 일치 |
| A-03 | AI Ready | 범주형을 인코딩하고 결측 표시를 유지해 학습 피처를 숫자형으로 만든다. | [05_ai_ready_check.py](../../src/ai_ready/05_ai_ready_check.py) · 원-핫/결측 검증 | ✅ 행·순서 일치, 결측 0건 |
| A-04 | AI Ready | 정답은 3착 이내 여부로 정의하고 TRAIN/TEST를 날짜로 분할한다. | [05_ai_ready_check.py](../../src/ai_ready/05_ai_ready_check.py) · 정답/분할 검증 | ✅ TRAIN 2,895행·TEST 749행, 날짜 겹침 0 |

상세 변환 규칙은 [매핑 규칙서](../../meta/mapping_rules.md), AI 피처 조건은 [AI Ready 문서](../ai_ready.md)에서 확인할 수 있습니다.
