# Silver 품질관리

공용 품질관리 코드는 `src/03_quality.py`입니다. 표준화 Silver 파일을 읽고 품질관리 결과는 `data/02_silver/clean/`에, 완전 중복 마권은 `data/02_silver/_excluded/`에 저장합니다.

```powershell
python -X utf8 src/03_quality.py
python -X utf8 src/03_quality_check.py
```

기존 Silver 컬럼의 자료형을 보존합니다. 매니페스트에는 표준화 입력, 품질관리·제외 산출물의 해시, 테이블별 유지 행 수와 `CLEAN_VERSION`을 기록합니다. 같은 입력이면 Parquet, 매니페스트, 행별 로그와 보고서의 내용이 같습니다.

진료 브리지는 표준화 결과 1,664행을 보존하고, `clean/`에서는 D-011에 따라 1,662행으로 통합합니다. 마권과 전표의 `ZERO_LATE_CANCEL_YN`은 0원 늦은 취소를 표시하며, 전표는 해당 마권이 하나라도 있으면 `Y`입니다. 매출 집계는 마권의 `SALES_AGG_INCLUDE_YN`을 사용할 수 있습니다.

현재 결과와 근거는 [품질관리 보고서](품질관리.md), [행별 처리 로그](../meta/dq_log.csv), [규칙별 결과](../meta/dq_result.csv)에서 확인합니다. `dq_change_log.csv`와 `dq_validation.csv`는 이전 실행의 감사 기록입니다.
