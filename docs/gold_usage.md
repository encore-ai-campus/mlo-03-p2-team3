# Gold 실행과 확인

2026-11-20 (KST). Python 3.11+와 requirements.txt 환경에서 프로젝트 루트 기준으로 실행합니다. 기존 결과가 있으면 확인 명령만 사용합니다.

```powershell
.\.venv\Scripts\python.exe src/03_gold_check.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_gold.py -v
```

최초 생성:

```powershell
.\.venv\Scripts\python.exe src/03_gold.py
```

| 옵션 | 기본값 / 의미 |
| --- | --- |
| --input-root | data/02_silver/clean; 공용 clean 14개 전체 해시 확인, 필요한7개만 계산에 사용 |
| --dq-meta-root | meta; 승인된 dq_manifest.json·dq_validation.json |
| --output-root | data/03_gold; 대문자 파일명의 스타6개 Parquet만 저장 |
| --meta-root | meta; audit/ 감사3개 Parquet·gold_manifest·validation·column_dictionary·decisions·dimension_contract·SQL·WIN_RATE_CANCEL_SUMMARY.csv |
| --docs-root | docs; GOLD.md·GOLD_COLUMNS.md·gold_usage.md |
| --unit-amount | 100; 금액=구좌×단가 검사, 다른 단가의 프로젝트에서는 명시 |

다른 프로젝트에서도 같은 공용 clean 스키마·코드·KST 시각과 유효 DQ manifest가 있으면 경로 인자로 실행할 수 있습니다. 처리 엔진 gold.py·gold_pipeline.py와 CLI 2개를 함께 사용합니다. 예:

```powershell
.\.venv\Scripts\python.exe src/03_gold.py `
  --input-root 'D:\other_racing_project\data\02_silver\clean' `
  --dq-meta-root 'D:\other_racing_project\meta\quality_v1' `
  --output-root 'D:\other_racing_project\data\03_gold_v1' `
  --meta-root 'D:\other_racing_project\meta\gold_v1' `
  --docs-root 'D:\other_racing_project\docs\gold_v1' --unit-amount 100
.\.venv\Scripts\python.exe src/03_gold_check.py --meta-root 'D:\other_racing_project\meta\gold_v1'
```

동일 결과 재실행은 파일 바이트·수정 시각을 유지합니다. 기존 Gold와 다른 결과는 덮어쓰지 않으며 output/meta/docs를 새 버전 경로로 모두 지정합니다. 입력/출력의 충돌 경로는 거부합니다. manifest는 절대 경로·mtime을 사용하므로 다른 컴퓨터에 파일을 옮긴 뒤 임의로 해시 기록을 고쳐 검증 완료로 취급하지 않습니다.

주 분석은 analysis_eligible=1만 사용합니다. unknown(날짜0) 차원 행을 제거하면 FK가 끊어질 수 있습니다. 스타 스키마는 DIM_MEMBER.parquet·FCT_BET_SELECTION_CANCEL_50S.parquet 등 대문자 파일명, 분석 보조 요약은 meta/WIN_RATE_CANCEL_SUMMARY.csv(UTF-8 BOM)로 제공합니다. 논리 테이블명·컬럼명은 기존 소문자를 유지합니다. 요약 CSV는 스타 스키마 테이블이 아닙니다. DB에 자동 접속하지 않습니다. 공통 차원 계약은 팀 합의 전 제안이며 다른 팀 키로 통합할 때 FK 재연결이 필요합니다.
