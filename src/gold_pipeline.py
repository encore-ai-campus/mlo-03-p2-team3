"""Manifest-controlled publication and read-only verification of Gold artifacts."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

import gold

ROOT = Path(__file__).resolve().parents[1]
CODE_FILES = ('gold.py', 'gold_pipeline.py', '03_gold.py', '03_gold_check.py')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + '\n').encode('utf-8')


def code_hashes():
    return {name:sha(Path(__file__).with_name(name)) for name in CODE_FILES}


def load_inputs(input_root, dq_meta_root):
    input_root = Path(input_root).resolve(); dq_meta_root = Path(dq_meta_root).resolve()
    manifest_path = dq_meta_root / 'dq_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    report_path = dq_meta_root / 'dq_validation.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report['status'] != 'passed' or not all(c['passed'] for c in report['checks']) or report['dataset_version'] != manifest['dataset_version']:
        raise ValueError('DQ validation/version does not pass')
    declared = {key.split('/')[1] for key in manifest['outputs'] if key.startswith('clean/')}
    if declared != {p.stem for p in input_root.glob('*.parquet')}:
        raise ValueError('Clean file set differs from approved DQ manifest')
    snapshots = {}
    tables = {}
    for name in sorted(declared):
        path = input_root / (name + '.parquet'); digest = sha(path)
        if digest != manifest['outputs']['clean/' + name]['sha256']:
            raise ValueError(f'Unapproved clean input: {name}')
        snapshots[name] = dict(path=str(path), sha256=digest, mtime_ns=path.stat().st_mtime_ns)
        if name in gold.SOURCES:
            table = pq.read_table(path)
            if set(table['_DQ_DATASET_VERSION'].to_pylist()) != {manifest['dataset_version']}:
                raise ValueError(f'Clean version differs: {name}')
            tables[name] = table
    controls = {str(p):dict(sha256=sha(p), mtime_ns=p.stat().st_mtime_ns) for p in [manifest_path, report_path]}
    return tables, snapshots, controls


def assert_preserved(sources, controls):
    for info in list(sources.values()) + [dict(path=p, **v) for p,v in controls.items()]:
        path = Path(info['path'])
        if sha(path) != info['sha256'] or path.stat().st_mtime_ns != info['mtime_ns']:
            raise RuntimeError(f'Input changed during Gold: {path}')


def md(headers, rows):
    def cell(v): return str(v).replace('|', '&#124;').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in rows])


DESCRIPTIONS = {
    'fact_id':'原구매 전표·경주일·경주번호·WIN·출주번호의 내부 해시',
    'original_order_no':'원구매 전표 식별자; 퇴화 차원',
    'age_at_purchase':'원구매일 기준 생일을 반영한 만 나이',
    'purchase_amount_krw':'0원 상세를 제외한 원구매 상세 금액 합(원); 헤더 금액 아님',
    'purchase_stake_units':'원구매 상세 UNIT_CNT 합; 마권 장수와 다름',
    'purchase_detail_count':'묶음에 포함된 원구매 상세 행 수',
    'recent1y_win_rate':'채택 스냅샷 최근1년 1착수/출전수; 출전0 또는 불량 전적은 NULL',
    'career_win_rate':'채택 스냅샷 통산 1착수/출전수; 출전0은 NULL',
    'has_verified_customer_cancel':'1 확인 취소, 0 관측 확인취소 없음, NULL 불명확',
    'analysis_eligible':'주 분석은 반드시 1만 사용',
    'exclusion_reasons':'복수 분석 부적격 사유; |로 구분',
    'horse_snapshot_date':'구매일보다 엄격히 이전인 최신 채택 관측일',
    'snapshot_age_days':'구매일과 채택 스냅샷일의 날짜 차',
    'verified_cancel_amount_krw':'행별 연결 검증을 통과한 취소 상세 절댓값 합; 묶음별 초과·불명확이면 분석에서 제외',
    'raw_linked_cancel_amount_krw':'회원·원전표·선택 연결 후보의 비영 취소금액 절댓값 합; 불량 건 포함',
    'verified_cancel_stake_units':'행별 연결 검증 통과 취소 구좌 절댓값 합',
    'cancel_transaction_count':'확정 연결 후보의 고유 비영 취소 전표 수; 검증 실패 건 포함',
    'late_cancel_detail_count':'행별 검증 통과 취소 중 취소시각≥출발시각인 상세 수; 0원 제외',
    'first_cancel_at':'행별 검증 통과 취소의 최초 KST 시각; 묶음이 분석 적격인지는 별도',
    'cancel_delay_seconds':'최초 행별 검증 통과 취소시각 - 원구매시각(초)',
    'observation_end_at':'입력 전표의 최대 유효 발생시각; 수집 완전성 보장은 아님',
    'header_detail_mismatch':'원구매 전표의 공용 헤더 불일치 플래그; 상세 합계를 사용하며 단독 제외 안 함',
    'horse_key':'내부 마명·생일 키. 공식 마번 아님; 불명은 UNKNOWN',
    'member_key':'회원번호 기반 내부 대리키; UNKNOWN 미상',
    'race_id':'MEET_CD·RC_DT·RC_NO 기반 내부 대리키; UNKNOWN 미상',
    'channel_key':'CHNL_CD·OTB_BRANCH_NO 기반 내부 대리키; UNKNOWN 미상',
    'source_row_id':'clean의 _DQ_ROW_ID; 해당 입력 처분/감사 테이블 PK',
    'source_bronze_file':'clean에 보존된 _SRC_BRONZE_FILE',
    'source_row_no':'clean에 보존된 _SRC_ROW_NO',
    'fact_id_reference':'대상 팩트가 있으면 그 fact_id',
    'disposition':'FACT_PURCHASE / CANCEL_AUDIT / OUT_OF_SCOPE; 입력 1행당 정확히 하나',
    'link_status':'ZERO_EXCLUDED / VERIFIED_TARGET_LINK / INVALID_TARGET_LINK / NOT_ASSIGNED_TO_TARGET',
    'matched_target_fact_id':'원전표·회원·선택이 연결되는 대상 팩트 ID; 실제 검증 통과는 link_status로 확인',
    'plausible_target_group_count':'미연결 비영 취소의 같은 회원·선택·이전 구매 후보 수; 자동 배정 아님',
    'weekday':'ISO 요일: 월1~일7',
    'identity_status':'INTERNAL_NAME_BIRTH_CONSISTENT는 내부 식별 일관성 확인; 공식 개체 검증 아님',
    'observed_cancel_rate':'적격 확인취소 구매묶음수/적격 구매묶음수',
    'amount_cancel_rate':'적격 확인취소금액/적격 원구매금액',
}


def describe(name):
    if name in DESCRIPTIONS: return DESCRIPTIONS[name]
    if name.endswith('_date_key'): return 'dim_date 역할별 FK; 미상/취소 없음은 0'
    if name.endswith('_row_id'): return '해당 clean 테이블의 _DQ_ROW_ID; 원천 계보'
    if name.endswith('_at'): return 'Asia/Seoul KST 사건 시각'
    if name.endswith('_date'): return '달력 날짜; 원천 또는 해당 사건 기준'
    if name.endswith('_starts'): return '채택 과거 스냅샷의 출전 수'
    if name.endswith('_wins'): return '채택 과거 스냅샷의 1착 수'
    return {
        'date_key':'YYYYMMDD 달력 키, 미상은 0', 'year':'연도', 'quarter':'분기1~4', 'month':'월1~12', 'day_of_month':'일1~31',
        'year_month':'YYYY-MM', 'calendar_date':'달력 날짜', 'member_no':'표준 회원 업무키', 'horse_name':'표준 마명',
        'birth_date':'원천 생일', 'join_date':'회원 가입일', 'sire_name':'부마명', 'dam_name':'모마명',
        'race_date':'경주일', 'race_no':'경주번호', 'meet_cd':'공용 경마장 코드', 'distance_m':'경주 거리(m)', 'race_grade':'공용 등급 코드',
        'channel_cd':'표준 채널+장외지점 코드; OTB01 등', 'channel_group':'공용 CHNL_CD', 'branch_no':'장외지점 번호', 'channel_name':'현장/앱/장외/미상 표시명',
        'bet_type_cd':'승식 WIN 고정', 'chul_no':'해당 경주의 출주번호; 말 영구 속성 아님',
        'horse_age_at_race':'출전표의 경주 당시 말 나이', 'horse_sex_at_race':'출전표의 경주 당시 성별 코드',
        'recent1y_win_rate_band':'0%, (0,5%], (5,10%], (10,20%], >20%; 계산 불가 UNKNOWN',
        'cancel_label_status':'AMBIGUOUS / VERIFIED_CANCEL / NO_CANCEL_OBSERVED',
        'unresolved_cancel_order_count':'해당 구매를 후보로 가진 미연결 취소의 고유 전표 수',
        'dq_dataset_version':'공용 clean 버전', 'rule_version':'Gold 규칙 버전',
        'order_no':'입력 마권의 전표번호', 'ticket_seq':'입력 상세 순번; 취소 연결키 아님', 'bet_amt':'원래 부호를 보존한 입력 상세 금액(원)',
        'unit_cnt':'원래 부호를 보존한 입력 상세 구좌 수', 'reason':'범위 포함/제외 사유', 'rule_id':'적용 Gold 규칙', 'decision_id':'적용 Gold/공용 근거 결정 ID',
        'cancel_order_no':'취소 전표번호', 'reference_order_no':'취소 전표에 기록된 원전표번호',
        'cancel_amount_krw':'입력 취소 상세 금액의 절댓값(원)', 'cancel_stake_units':'입력 취소 상세 구좌 절댓값',
        'reasons':'취소 상세 검증 사유', 'late_cancel_yn':'취소시각≥해당 경주출발시각 Y; NULL 시각은 비교 불가',
        'summary_id':'scope와 승률구간으로 구성한 요약 PK', 'scope':'all_positive_starts / min_10_recent_starts',
        'win_rate_band':'승률 구간', 'purchase_selection_groups':'적격 구매 선택 묶음 수', 'cancelled_groups':'확인취소 적격 구매 묶음 수',
        'cancel_amount_krw_summary':'적격 확인취소 금액 합', 'unique_members':'적격 고유 회원 수', 'unique_horses':'적격 고유 내부 말 키 수',
        'unique_races':'적격 고유 경주 수',
    }.get(name, name)


def dictionary(tables):
    return [dict(table=name, column=f.name, type=str(f.type), pk=f.name == gold.PKS[name],
                 null_rows=table[f.name].null_count, description=describe(f.name)) for name,table in tables.items() for f in table.schema]


def ddl(tables):
    names = ['dim_member', 'dim_horse', 'dim_race', 'dim_date', 'dim_channel', gold.FACT]
    fk = {'member_key':'dim_member','horse_key':'dim_horse','race_id':'dim_race','channel_key':'dim_channel',
          **{c:'dim_date' for c in ['purchase_date_key','cancel_date_key','race_date_key','snapshot_date_key']}}
    text = '-- MariaDB example only; not executed. DATETIME values are KST, without timezone conversion.\n'
    for name in names:
        parts = []
        for f in tables[name].schema:
            if pa.types.is_string(f.type):
                kind = 'VARCHAR(128)' if f.name in {*fk, gold.PKS[name], 'original_order_no', 'bet_type_cd', 'member_no', 'channel_cd'} else 'TEXT'
            elif pa.types.is_timestamp(f.type): kind = 'DATETIME(3)'
            elif pa.types.is_date(f.type): kind = 'DATE'
            elif pa.types.is_floating(f.type): kind = 'DOUBLE'
            else: kind = 'BIGINT' if pa.types.is_int64(f.type) else 'INT'
            parts.append(f'  `{f.name}` {kind}' + (' NOT NULL' if f.name == gold.PKS[name] else ' NULL'))
        parts.append(f'  PRIMARY KEY (`{gold.PKS[name]}`)')
        if name == gold.FACT:
            parts.append('  UNIQUE KEY uq_selection (`original_order_no`,`race_id`,`bet_type_cd`,`chul_no`)')
            parts.extend(f'  FOREIGN KEY (`{f}`) REFERENCES `{d}` (`{gold.PKS[d]}`)' for f,d in fk.items())
        text += f'\nCREATE TABLE `{name}` (\n' + ',\n'.join(parts) + '\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n'
    text += f'''\n-- Always filter eligible purchases; cancellation orders are not denominator rows.
SELECT recent1y_win_rate_band, COUNT(*) AS purchase_groups,
       SUM(has_verified_customer_cancel) AS cancelled_groups,
       SUM(has_verified_customer_cancel) / NULLIF(COUNT(*),0) AS cancel_rate,
       SUM(verified_cancel_amount_krw) / NULLIF(SUM(purchase_amount_krw),0) AS amount_cancel_rate
FROM {gold.FACT} WHERE analysis_eligible=1 GROUP BY recent1y_win_rate_band;
'''
    return text


def generated_docs(tables, report, manifest):
    counts = report['counts']; m = report['metrics']
    lines = [f'# Gold 스타 스키마 작업 기록\n\n2026-11-20 (KST). 설계: [GOLD_DESIGN.md](GOLD_DESIGN.md), [사용법](gold_usage.md), [컬럼](GOLD_COLUMNS.md).',
             f"\n입력 clean 버전 `{report['dq_dataset_version']}`. Gold 버전 `{manifest['dataset_version']}`.",
             '\n팩트 한 행은 원구매 전표×경주일×경주번호×WIN×출주번호의 구매 선택 묶음입니다. 0원 상세는 업무 분자·분모에서 제외합니다. 늦은 취소는 D-004에 따라 허용하며 연결 검증을 통과해야 합니다.',
             '\n## 실제 생성 결과\n', md(['산출물','행 수','PK','형식·위치'], [[n, f'{v:,}', gold.PKS[n], 'meta/WIN_RATE_CANCEL_SUMMARY.csv (분석 보조)' if n=='win_rate_cancel_summary' else n.upper()+'.parquet'] for n,v in counts.items()]),
             '\n## 분석 적격 결과\n', md(['지표','실측'], [[k,f'{v:,}'] for k,v in m.items()]),
             '\n전체 팩트는 분석 부적격 행도 포함합니다. 주 분석은 `analysis_eligible=1`을 반드시 적용합니다. 분석 제외 사유는 FACT_ANALYSIS_EXCLUSIONS.parquet에, 전체 입력의 범위 제외는 TICKET_DISPOSITION.parquet에, 취소 행별 검증은 CANCEL_LINK_AUDIT.parquet에 보존하며 이 감사 파일3개는 meta/audit/에 둡니다. Gold 데이터 폴더에는 스타 스키마6개만 둡니다.',
             '\n## 입력 마권 전수 처분 사유\n', md(['사유','행 수'], report['dispositions'].items()),
             '\n## 분석 제외 사유 (중복 집계)\n', md(['사유','팩트 수'], report['exclusions_nonexclusive'].items()),
             '\n## 검증 결과\n', md(['검사','기대','실제','결과'], [[c['check'],c['expected'],c['actual'],'통과' if c['passed'] else '실패'] for c in report['checks']]),
             '\n## 공통 차원 계약과 한계\n\n이번 대리키·컬럼·코드 계약은 이 브랜치의 제안이며 팀 합의 완료를 의미하지 않습니다. 다른 팀원과 통합할 때 member_no, 말 이름·생일, MEET_CD·경주일·경주번호, 날짜, 채널·지점의 자연키로 연결한 뒤 팩트 FK를 다시 검증합니다. 세부 계약은 meta/gold_dimension_contract.json에 기록합니다.',
             '\n말 키는 내부 이름·생일 기반이며 공식 마번이 아닙니다. 전체 스냅샷에서 생일·부·모가 충돌하면 UNKNOWN으로 두며, 미래 성적은 사용하지 않습니다. 성별과 승률·출주번호는 차원의 고정 속성으로 두지 않습니다. UNKNOWN 키(날짜는0)는 FK 무결성용이며 해당 분석은 제외 사유를 확인합니다.',
             '\n관측 종료는 전체 전표 최대 시각을 이용한 보수적 경계이며 수집 완료 인증은 아닙니다. 미연결 취소가 알려진 같은 회원·선택의 이전 구매에 영향을 줄 때 NULL 라벨을 유지하며, 회원조차 미상인 취소의 관측 누락은 해소하지 못합니다.',
             '\n생일 생성값·소매 재매핑 거래를 포함한 시뮬레이션 분석입니다. 실제 마사회 고객 행동·인과효과로 일반화하지 않습니다. 회원·말·경주의 반복 관측을 독립표본으로 가정하지 않습니다. 참고 폴더의 41,149·39,263·875는 현재 규칙 기대값으로 사용하지 않았습니다.',
             '\nDB 연결·적재는 수행하지 않았습니다. 스타 스키마 Parquet와 SQL 예제를 생성했습니다. 입력 Silver·Bronze·원천은 수정하지 않습니다.']
    columns = dictionary(tables)
    col_doc = '# Gold 컬럼 사전\n\n2026-11-20 (KST). 실제 Parquet 스키마와 NULL 실측 기준. 데이터 파일명은 대문자이며 논리 테이블명·컬럼명은 기존 소문자를 유지합니다. 요약은 meta/WIN_RATE_CANCEL_SUMMARY.csv에 저장하며 해당 타입은 계산 시 논리형, NULL은 CSV 빈칸입니다. [작업 기록](GOLD.md).\n'
    for name in tables:
        col_doc += f'\n## {name}\n\n' + md(['컬럼','타입','PK','NULL 행','의미'], [[r['column'],r['type'],r['pk'],r['null_rows'],r['description']] for r in columns if r['table']==name]) + '\n'
    usage = '''# Gold 실행과 확인

2026-11-20 (KST). Python 3.11+와 requirements.txt 환경에서 프로젝트 루트 기준으로 실행합니다. 기존 결과가 있으면 확인 명령만 사용합니다.

```powershell
.\\.venv\\Scripts\\python.exe src/03_gold_check.py
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p test_gold.py -v
```

최초 생성:

```powershell
.\\.venv\\Scripts\\python.exe src/03_gold.py
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
.\\.venv\\Scripts\\python.exe src/03_gold.py `
  --input-root 'D:\\other_racing_project\\data\\02_silver\\clean' `
  --dq-meta-root 'D:\\other_racing_project\\meta\\quality_v1' `
  --output-root 'D:\\other_racing_project\\data\\03_gold_v1' `
  --meta-root 'D:\\other_racing_project\\meta\\gold_v1' `
  --docs-root 'D:\\other_racing_project\\docs\\gold_v1' --unit-amount 100
.\\.venv\\Scripts\\python.exe src/03_gold_check.py --meta-root 'D:\\other_racing_project\\meta\\gold_v1'
```

동일 결과 재실행은 파일 바이트·수정 시각을 유지합니다. 기존 Gold와 다른 결과는 덮어쓰지 않으며 output/meta/docs를 새 버전 경로로 모두 지정합니다. 입력/출력의 충돌 경로는 거부합니다. manifest는 절대 경로·mtime을 사용하므로 다른 컴퓨터에 파일을 옮긴 뒤 임의로 해시 기록을 고쳐 검증 완료로 취급하지 않습니다.

주 분석은 analysis_eligible=1만 사용합니다. unknown(날짜0) 차원 행을 제거하면 FK가 끊어질 수 있습니다. 스타 스키마는 DIM_MEMBER.parquet·FCT_BET_SELECTION_CANCEL_50S.parquet 등 대문자 파일명, 분석 보조 요약은 meta/WIN_RATE_CANCEL_SUMMARY.csv(UTF-8 BOM)로 제공합니다. 논리 테이블명·컬럼명은 기존 소문자를 유지합니다. 요약 CSV는 스타 스키마 테이블이 아닙니다. DB에 자동 접속하지 않습니다. 공통 차원 계약은 팀 합의 전 제안이며 다른 팀 키로 통합할 때 FK 재연결이 필요합니다.
'''
    return {'GOLD.md':'\n'.join(lines)+'\n', 'GOLD_COLUMNS.md':col_doc, 'gold_usage.md':usage}


def csv_bytes(rows):
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def run(input_root=ROOT/'data/02_silver/clean', dq_meta_root=ROOT/'meta', output_root=ROOT/'data/03_gold',
        meta_root=ROOT/'meta', docs_root=ROOT/'docs', unit_amount=100):
    paths = [Path(p).resolve() for p in [input_root,dq_meta_root,output_root,meta_root,docs_root]]
    input_root,dq_meta_root,output_root,meta_root,docs_root = paths
    # Quality and Gold metadata may share a folder; their filenames never overlap.
    for out in [output_root,meta_root,docs_root]:
        if out == input_root or out in input_root.parents or input_root in out.parents:
            raise ValueError('Gold output/meta/docs must not overlap clean input')
    for a,b in [(output_root,meta_root),(output_root,docs_root),(meta_root,docs_root)]:
        if a == b or a in b.parents or b in a.parents: raise ValueError('Gold publication directories must differ and not overlap')
    tables,sources,controls = load_inputs(input_root,dq_meta_root)
    print('Approved clean hashes matched; building Gold.', flush=True)
    outputs,report = gold.build(tables, unit_amount)
    codes = code_hashes()
    version = 'GOLD-' + hashlib.sha256(json_bytes(dict(inputs={n:v['sha256'] for n,v in sources.items()}, code=codes, unit_amount=unit_amount))).hexdigest()[:20]
    report['dataset_version'] = version
    output_root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gold-stage-',dir=output_root.parent) as temporary:
        stage=Path(temporary); publications=[]; recorded={}
        for name,table in outputs.items():
            if name=='win_rate_cancel_summary':
                path=stage/(name.upper()+'.csv'); path.write_bytes(csv_bytes(table.to_pylist()))
                dest=meta_root/path.name; format_name='csv'
            else:
                audit=name in ['ticket_disposition','cancel_link_audit','fact_analysis_exclusions']
                rel=Path('audit')/(name.upper()+'.parquet') if audit else Path(name.upper()+'.parquet')
                path=stage/(name+'.parquet'); pq.write_table(table,path,compression='snappy')
                if not pq.read_table(path).equals(table): raise RuntimeError(f'Parquet roundtrip failed: {name}')
                dest=(meta_root if audit else output_root)/rel; format_name='parquet'
            recorded[name]=dict(path=str(dest),sha256=sha(path),rows=table.num_rows,format=format_name)
            publications.append((path,dest))
        manifest=dict(dataset_version=version, dq_dataset_version=report['dq_dataset_version'], code=codes, sources=sources,
                      controls=controls, outputs=recorded, input_root=str(input_root),dq_meta_root=str(dq_meta_root),
                      output_root=str(output_root),meta_root=str(meta_root),docs_root=str(docs_root),unit_amount=unit_amount)
        docs=generated_docs(outputs,report,manifest)
        natural={'dim_member':['member_no'], 'dim_horse':['horse_name','birth_date'], 'dim_race':['meet_cd','race_date','race_no'],
                 'dim_date':['calendar_date'],'dim_channel':['channel_group','branch_no']}
        contract=dict(status='PROPOSED_FOR_THIS_BRANCH_NOT_TEAM_APPROVED', key_algorithm='SHA256 of compact JSON [namespace,*natural_values], first24 lowercase hex; dates YYYYMMDD int32',
                      unknown_key='UNKNOWN; date_key=0',natural_keys=natural, schema={n:str(outputs[n].schema) for n in natural},
                      remapping='Join natural keys to integrated dimensions; reconnect all fact FKs; verify uniqueness and amount/row preservation')
        blobs={'gold_validation.json':json_bytes(report),'gold_dimension_contract.json':json_bytes(contract),
               'gold_decisions.json':json_bytes(gold.GOLD_DECISIONS),'gold_column_dictionary.csv':csv_bytes(dictionary(outputs)),
               'gold_schema.sql':ddl(outputs).encode('utf-8')}
        for filename,blob in blobs.items():
            path=stage/filename; path.write_bytes(blob); publications.append((path,meta_root/filename))
        for filename,body in docs.items():
            path=stage/filename; path.write_text(body,encoding='utf-8'); publications.append((path,docs_root/filename))
        manifest['artifacts']={str(dest):sha(path) for path,dest in publications if path.suffix!='.parquet'}
        path=stage/'gold_manifest.json'; path.write_bytes(json_bytes(manifest)); publications.append((path,meta_root/'gold_manifest.json'))
        expected={Path(info['path']).resolve() for info in recorded.values() if info['format']=='parquet'}
        existing=set(output_root.rglob('*.parquet')) | set((meta_root/'audit').rglob('*.parquet'))
        if existing-expected: raise RuntimeError('Unexpected existing Gold Parquet files; choose new output root')
        for path,dest in publications:
            if dest.exists() and sha(path)!=sha(dest): raise RuntimeError(f'Existing Gold artifact immutable; choose new output/meta/docs version: {dest}')
        assert_preserved(sources,controls)
        for path,dest in publications:
            if dest.exists(): continue
            dest.parent.mkdir(parents=True,exist_ok=True); path.replace(dest)
    print(f"Gold passed: {report['counts'][gold.FACT]:,} facts; {report['metrics']['eligible_facts']:,} eligible; {len(report['checks'])} checks.",flush=True)
    return report


def verify(meta_root=ROOT/'meta'):
    meta_root=Path(meta_root).resolve(); manifest=json.loads((meta_root/'gold_manifest.json').read_text(encoding='utf-8'))
    if manifest['code'] != code_hashes(): raise RuntimeError('Gold code hash differs from recorded generation')
    tables,sources,controls=load_inputs(manifest['input_root'],manifest['dq_meta_root'])
    if sources!=manifest['sources'] or controls!=manifest['controls']: raise RuntimeError('Input paths/hashes/mtime differ from Gold manifest')
    outputs,report=gold.build(tables,manifest['unit_amount']); report['dataset_version']=manifest['dataset_version']
    recorded=json.loads((meta_root/'gold_validation.json').read_text(encoding='utf-8'))
    if report!=recorded: raise RuntimeError('Gold remeasurement differs from stored report')
    expected={Path(info['path']) for info in manifest['outputs'].values() if info['format']=='parquet'}
    existing=set(Path(manifest['output_root']).rglob('*.parquet')) | set((Path(manifest['meta_root'])/'audit').rglob('*.parquet'))
    if existing!=expected: raise RuntimeError('Gold/audit Parquet file set differs')
    for name,table in outputs.items():
        info=manifest['outputs'][name]; path=Path(info['path'])
        matches=path.read_bytes()==csv_bytes(table.to_pylist()) if info['format']=='csv' else pq.read_table(path).equals(table)
        if sha(path)!=info['sha256'] or table.num_rows!=info['rows'] or not matches:
            raise RuntimeError(f'Gold data mismatch: {name}')
    for path,digest in manifest['artifacts'].items():
        if sha(path)!=digest: raise RuntimeError(f'Gold documentation/metadata mismatch: {path}')
    assert_preserved(sources,controls)
    print(f"Read-only Gold verified: {len(outputs)-1} Parquet tables + summary CSV, {len(report['checks'])} checks; all values/schemas/hashes, audits and documentation matched.",flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option,default in [('input-root',ROOT/'data/02_silver/clean'),('dq-meta-root',ROOT/'meta'),('output-root',ROOT/'data/03_gold'),('meta-root',ROOT/'meta'),('docs-root',ROOT/'docs')]:
        parser.add_argument('--'+option,type=Path,default=default)
    parser.add_argument('--unit-amount',type=int,default=100)
    run(**vars(parser.parse_args()))
