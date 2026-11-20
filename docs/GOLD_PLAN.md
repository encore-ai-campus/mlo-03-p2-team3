# Gold 구현 계획

2026-11-20 (KST). writing-plans / executing-plans / test-driven-development 적용. 명세: [GOLD_DESIGN.md](GOLD_DESIGN.md). 사용자의 기존 설계 및 진행 요청에 따라 현재 작업 브랜치에서 직접 구현한다. 기존 미커밋 파일은 보존하고 자동 커밋하지 않는다.

| 순서 | 파일·작업 | 검증 |
| --- | --- | --- |
| 1 | tests/test_gold.py에 경계·취소·시점·집계·불변성 테스트 선작성 | 기능 부재 실패 확인 |
| 2 | src/gold.py: build(tables, unit_amount=100) → 테이블 dict, report; age_at, stable_key, 입력 검증·팩트·차원·감사·요약 | 동일 테스트 통과 |
| 3 | src/03_gold.py: manifest 검증·단계 저장·불변 게시; src/03_gold_check.py: 읽기 전용 재계산 | 실제 clean 실행 후 전수 비교 |
| 4 | docs/GOLD.md, GOLD_COLUMNS.md, gold_usage.md; meta/gold_*와 공통 차원 계약, SQL; 상태 문서 갱신 | PK/FK·전수 처분·금액·구좌·집계 대사 |
| 5 | 독립 코드 검토 및 필요한 수정 | unittest 전체, 읽기 전용 검증, 입력 해시 보존 |

| 중점 실패 조건 | 기대 동작 |
| --- | --- |
| 출발 시각과 같은 취소·0원 늦은 취소 | 늦은 취소 유지, 0원은 업무집계 양쪽 제외 |
| 초과 취소·다른 회원·미연결 취소 | 자동 재배정 금지, 후보 불확실성 유지 |
| 동일일 스냅샷·복수 말 생일 | 미래 유입 금지, 임의 개체 통합 금지 |
| 가입일·생일/0회 출전·상태 이상 | 시점 나이·분모0 구분, 부적격 사유 보존 |
| 다른 프로젝트 입력·기존 결과 | 명시 경로·단가 옵션, 바뀐 결과 덮어쓰기 거부 |

실행 기록과 실측은 GOLD.md에 남기며 이 계획의 기대값을 실측으로 사용하지 않는다.
