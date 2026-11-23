"""Manifest-controlled publication and read-only verification of Gold artifacts."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

import gold

ROOT = Path(__file__).resolve().parents[2]
CLEAN_ROOT = ROOT / 'data/02_silver/clean'
GOLD_ROOT = ROOT / 'data/03_gold/bet_cancel'
DOCS_ROOT = ROOT / 'docs/gold'
CONFIG_PATH = ROOT / 'src/config.py'
sys.path.insert(0, str(CONFIG_PATH.parent))
import config

CODE_FILES = ('gold.py', 'gold_pipeline.py', '04_fct_bet_cancel.py', '04_fct_bet_cancel_check.py')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + '\n').encode('utf-8')


def text_sha(payload):
    """Track source and document content across Git newline conventions."""
    return hashlib.sha256(payload.replace(b'\r\n', b'\n')).hexdigest()


def code_hashes():
    paths = [Path(__file__).with_name(name) for name in CODE_FILES] + [CONFIG_PATH]
    return {path.relative_to(ROOT).as_posix(): text_sha(path.read_bytes()) for path in paths}


def relative_path(path, base):
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:  # Paths on different Windows drives are necessarily absolute.
        return Path(path).as_posix()


def load_inputs(input_root):
    input_root = Path(input_root).resolve()
    manifest_path = input_root / '_manifest.json'
    if not manifest_path.is_file():
        raise ValueError(f'Develop clean manifest required: {manifest_path}')
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    version = manifest['CLEAN_VERSION']
    approved = manifest['CLEAN_SHA256']
    expected = {name + '.parquet' for name in config.SILVER_FROM_BRONZE}
    if not isinstance(version, str) or not version or set(approved) != expected:
        raise ValueError('Develop clean manifest has an invalid version or table set')
    if {path.name for path in input_root.glob('*.parquet')} != expected:
        raise ValueError('Clean file set differs from the develop snapshot')

    tables = {}
    snapshots = {}
    for filename, expected_hash in sorted(approved.items()):
        path = input_root / filename
        digest = sha(path)
        name = path.stem
        if digest != expected_hash:
            raise ValueError(f'Unapproved clean input: {name}')
        snapshots[name] = dict(path=path, sha256=digest, mtime_ns=path.stat().st_mtime_ns)
        if name not in gold.SOURCES:
            continue
        table = pq.ParquetFile(path).read()
        row_numbers = table['_SRC_ROW_NO'].to_pylist()
        if len(set(row_numbers)) != len(row_numbers) or any(type(n) is not int or n < 1 for n in row_numbers):
            raise ValueError(f'{name}: expected unique positive Bronze row numbers')
        # Shared Silver records the row number and the team config defines its Bronze file.
        bronze_path = f'data/01_bronze/{config.SILVER_FROM_BRONZE[name]}.parquet'
        tables[name] = (table.append_column('_SRC_BRONZE_FILE', pa.repeat(pa.scalar(bronze_path), table.num_rows))
                        .append_column('_DQ_ROW_ID', pa.array([f'{name}:{n:08d}' for n in row_numbers]))
                        .append_column('_DQ_DATASET_VERSION', pa.repeat(pa.scalar(version), table.num_rows)))
    control = dict(path=manifest_path, sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                   mtime_ns=manifest_path.stat().st_mtime_ns)
    return tables, snapshots, control, version


def assert_preserved(sources, control):
    for info in [*sources.values(), control]:
        path = info['path']
        if sha(path) != info['sha256'] or path.stat().st_mtime_ns != info['mtime_ns']:
            raise RuntimeError(f'Input changed during Gold: {path}')


def output_hash(path, format_name):
    return sha(path) if format_name == 'parquet' else text_sha(path.read_bytes())


def md(headers, rows):
    def cell(v): return str(v).replace('|', '&#124;').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in rows])


DESCRIPTIONS = {
    'fact_id':'원구매 전표·경주일·경주번호·WIN·출주번호의 내부 해시',
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
    'first_cancel_at':'행별 검증 통과 취소의 최초 시각 (시간대 정보 없는 KST)',
    'cancel_delay_seconds':'최초 행별 검증 통과 취소시각 - 원구매시각(초)',
    'observation_end_at':'입력 전표의 최대 유효 발생 시각 (시간대 정보 없는 KST)',
    'header_detail_mismatch':'원구매 전표의 공용 헤더 불일치 플래그; 상세 합계를 사용하며 단독 제외 안 함',
    'horse_key':'내부 마명·생일 키. 공식 마번 아님; 불명은 UNKNOWN',
    'member_key':'회원번호 기반 내부 대리키; UNKNOWN 미상',
    'race_id':'MEET_CD·RC_DT·RC_NO 기반 내부 대리키; UNKNOWN 미상',
    'channel_key':'CHNL_CD·OTB_BRANCH_NO 기반 내부 대리키; UNKNOWN 미상',
    'source_row_id':'공용 clean 테이블명과 _SRC_ROW_NO로 만든 감사용 PK',
    'source_bronze_file':'팀 공용 SILVER_FROM_BRONZE가 지정하는 Bronze 상대 경로',
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
    if name.endswith('_row_id'): return '공용 clean 테이블명과 _SRC_ROW_NO로 만든 원천 행 식별자'
    if name.endswith('_at'): return '시간대 정보 없는 KST 사건 시각'
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
    text = '-- MariaDB example. DATETIME(3) stores KST wall-clock values without a timezone offset.\n'
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


def generated_doc(report):
    counts = report['counts']
    metrics = report['metrics']
    dataset_path = '../../data/03_gold/bet_cancel'
    data_rows = []
    for name, count in counts.items():
        filename = name.upper() + ('.csv' if name == 'win_rate_cancel_summary' else '.parquet')
        relative = f'audit/{filename}' if name in {
            'ticket_disposition', 'cancel_link_audit', 'fact_analysis_exclusions'
        } else filename
        data_rows.append([f'[{filename}]({dataset_path}/{relative})', f'{count:,}', gold.PKS[name]])
    metric_labels = {
        'eligible_facts': '분석 적격 구매 묶음',
        'excluded_facts': '분석 부적격 구매 묶음',
        'eligible_cancel_groups': '확인 취소가 있는 적격 구매 묶음',
        'eligible_purchase_amount': '적격 구매 금액 (원)',
        'eligible_cancel_amount': '적격 확인 취소 금액 (원)',
        'eligible_late_cancel_details': '적격 구매의 확인된 늦은 취소 상세',
    }
    lines = [
        '# Gold 50대 단승 마권 취소 스타 스키마',
        f"\n공용 clean 버전 `{report['dq_dataset_version']}`을 사용했습니다. Gold 버전은 `{report['dataset_version']}`입니다.",
        """
## 팩트와 차원

`FCT_BET_SELECTION_CANCEL_50S` 한 행은 **원구매 전표 × 경주일 × 경주번호 × WIN × 출주번호**로 묶은 구매 한 건입니다. 원구매일의 만 나이가 50~59세인 회원을 대상으로 합니다. 같은 묶음의 구매 상세를 합산하고, 확인된 취소를 묶음에 연결합니다.

| 차원 | 업무 키 | 팩트 외래키 |
| --- | --- | --- |
| `DIM_MEMBER` | 회원번호 | `member_key` |
| `DIM_HORSE` | 마명과 생일 | `horse_key` |
| `DIM_RACE` | 경마장, 경주일, 경주번호 | `race_id` |
| `DIM_DATE` | 날짜 | `purchase_date_key`, `cancel_date_key`, `race_date_key`, `snapshot_date_key` |
| `DIM_CHANNEL` | 발매 채널과 지점 | `channel_key` |

확인할 수 없는 차원 참조에는 `UNKNOWN`(날짜는 `0`) 행을 연결합니다. 말 키는 내부 마명·생일 식별자입니다. 팀 공통 차원 통합 시 업무 키로 팩트 외래키를 다시 연결하고 대사합니다.

## 측정값

| 측정값 | 계산 및 기준 |
| --- | --- |
| `purchase_amount_krw`, `purchase_stake_units`, `purchase_detail_count` | 공용 `BET_TICKET`의 원구매 상세 금액, 구좌, 행 수를 묶음별로 합산합니다. 0원 상세는 업무 집계에서 제외합니다(D-003). |
| `has_verified_customer_cancel` | 원전표·회원·선택·시각 등으로 확인된 취소가 있으면 1, 관측 구간에서 확인된 취소가 없으면 0, 미연결이나 초과 취소 등으로 판정할 수 없으면 NULL입니다. |
| `verified_cancel_amount_krw`, `verified_cancel_stake_units` | 연결 검증을 통과한 취소 상세의 금액과 구좌 절댓값을 합산합니다. 0원 상세는 분자와 분모 모두에서 제외합니다. |
| `late_cancel_detail_count` | 연결 검증을 통과한 취소 중 취소 시각이 경주 출발 시각 이상인 상세를 셉니다(D-004). |
| `recent1y_win_rate`, `career_win_rate` | 구매일보다 엄격히 이전인 최신 `HR_WEEKLY_SNAPSHOT`의 1착수 ÷ 출전수입니다. 출전 0이나 유효하지 않은 값은 NULL입니다. |
| 관측 취소율 | `analysis_eligible = 1`인 확인 취소 구매 묶음 수 ÷ 적격 구매 묶음 수입니다. 금액 취소율은 같은 범위의 확인 취소 금액 ÷ 구매 금액입니다. |

시각은 모두 시간대 정보 없는 KST `timestamp[ms]`입니다. 팩트에는 분석 부적격 구매도 남겨 두므로, 취소율 집계에는 `analysis_eligible = 1`을 적용합니다. 관측 종료 시각은 입력 전표의 최대 발생 시각을 사용합니다. 취소 회원이 미상인 거래는 개별 구매에 배정할 수 없습니다. 생일 생성값과 재매핑 거래를 포함한 시뮬레이션 데이터이므로 결과를 실제 고객 행동이나 인과효과로 해석할 수 없습니다.

## 생성과 검증

저장소 루트에서 Python 3.11 이상과 `requirements.txt` 환경으로 실행합니다.

```powershell
python src/bet_cancel/04_fct_bet_cancel.py
python src/bet_cancel/04_fct_bet_cancel_check.py
python -m unittest discover -s src/bet_cancel -p test_bet_cancel.py -v
```

생성 코드는 공용 `data/02_silver/clean/_manifest.json`에 기록된 14개 Parquet 해시를 확인한 뒤 `BET_ORDER`, `BET_TICKET`, `MBR_MASTER`, `HR_WEEKLY_SNAPSHOT`, `RC_RACE`, `RC_ENTRY`, `RC_RESULT`를 읽습니다. 동일 입력으로 재실행하면 새 계산 결과와 기존 산출물의 해시를 대사합니다. 읽기 전용 검증은 공용 clean에서 다시 계산해 Parquet 값·스키마·해시, 검증 보고서와 문서까지 비교합니다.
""",
        '## 생성 결과',
        md(['산출물', '행 수', 'PK'], data_rows),
        '\n' + md(['분석 지표', '건수·금액'], [
            [metric_labels[key], f'{value:,}'] for key, value in metrics.items()
        ]),
        f'\n전체 clean 마권의 처리 내역은 `audit/TICKET_DISPOSITION.parquet`에서 Bronze 경로와 원천 행 번호로 추적합니다. 취소 상세 연결과 분석 제외 사유는 별도 감사 파일에 저장합니다.',
        '\n' + md(['입력 마권 처리 사유', '행 수'], [
            [reason, f'{value:,}'] for reason, value in report['dispositions'].items()
        ]),
        '\n' + md(['분석 제외 사유 (한 팩트에 복수 적용 가능)', '팩트 수'], [
            [reason, f'{value:,}'] for reason, value in report['exclusions_nonexclusive'].items()
        ]),
        '\n## 실제 검증 결과',
        md(['검사', '기대', '실제', '결과'], [
            [c['check'], c['expected'], c['actual'], '통과' if c['passed'] else '실패']
            for c in report['checks']
        ]),
        f'\n[입력·출력 매니페스트]({dataset_path}/_manifest.json) · [검증 결과 JSON]({dataset_path}/_validation.json) · [컬럼 사전]({dataset_path}/_column_dictionary.csv) · [차원 키 계약]({dataset_path}/_dimension_contract.json) · [분석 판단 규칙]({dataset_path}/_decisions.json) · [SQL 스키마 예제]({dataset_path}/_schema.sql)',
    ]
    return '\n'.join(lines) + '\n'


def csv_bytes(rows):
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def run(input_root=CLEAN_ROOT, output_root=GOLD_ROOT, docs_root=DOCS_ROOT, unit_amount=100):
    input_root, output_root, docs_root = (Path(p).resolve() for p in (input_root, output_root, docs_root))
    protected = [input_root, ROOT / 'data/00_origin', ROOT / 'data/01_bronze', ROOT / 'data/02_silver']
    for out in (output_root, docs_root):
        if any(out == source or out in source.parents or source in out.parents for source in protected):
            raise ValueError('Gold destinations must not overlap earlier layers')
    if output_root == docs_root or output_root in docs_root.parents or docs_root in output_root.parents:
        raise ValueError('Gold publication directories must differ and not overlap')
    tables, sources, control, clean_version = load_inputs(input_root)
    print('Approved clean hashes matched; building Gold.', flush=True)
    outputs,report = gold.build(tables, unit_amount)
    if report['dq_dataset_version'] != clean_version:
        raise RuntimeError('Gold does not match the approved clean version')
    codes = code_hashes()
    version = 'GOLD-' + hashlib.sha256(json_bytes(dict(inputs={n:v['sha256'] for n,v in sources.items()}, clean_version=clean_version, code=codes, unit_amount=unit_amount))).hexdigest()[:20]
    report['dataset_version'] = version
    output_root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gold-stage-',dir=output_root.parent) as temporary:
        stage=Path(temporary); publications=[]; recorded={}
        for name,table in outputs.items():
            if name=='win_rate_cancel_summary':
                path=stage/(name.upper()+'.csv'); path.write_bytes(csv_bytes(table.to_pylist()))
                dest=output_root/path.name; format_name='csv'
            else:
                audit=name in ['ticket_disposition','cancel_link_audit','fact_analysis_exclusions']
                rel=Path('audit')/(name.upper()+'.parquet') if audit else Path(name.upper()+'.parquet')
                path=stage/(name+'.parquet'); pq.write_table(table,path,compression='snappy')
                if not pq.read_table(path).equals(table): raise RuntimeError(f'Parquet roundtrip failed: {name}')
                dest=output_root/rel; format_name='parquet'
            recorded[name]=dict(path=dest.relative_to(output_root).as_posix(), sha256=output_hash(path, format_name),
                                rows=table.num_rows, format=format_name)
            publications.append((path,dest))
        manifest = dict(dataset_version=version, dq_dataset_version=clean_version, code=codes,
                        sources={name: info['sha256'] for name, info in sources.items()}, outputs=recorded,
                        input_root=relative_path(input_root, output_root),
                        unit_amount=unit_amount)
        natural={'dim_member':['member_no'], 'dim_horse':['horse_name','birth_date'], 'dim_race':['meet_cd','race_date','race_no'],
                 'dim_date':['calendar_date'],'dim_channel':['channel_group','branch_no']}
        contract=dict(status='PROPOSED_FOR_THIS_BRANCH_NOT_TEAM_APPROVED', key_algorithm='SHA256 of compact JSON [namespace,*natural_values], first24 lowercase hex; dates YYYYMMDD int32',
                      unknown_key='UNKNOWN; date_key=0',natural_keys=natural, schema={n:str(outputs[n].schema) for n in natural},
                      remapping='Join natural keys to integrated dimensions; reconnect all fact FKs; verify uniqueness and amount/row preservation')
        blobs={'_validation.json':json_bytes(report),'_dimension_contract.json':json_bytes(contract),
               '_decisions.json':json_bytes(gold.GOLD_DECISIONS),'_column_dictionary.csv':csv_bytes(dictionary(outputs)),
               '_schema.sql':ddl(outputs).encode('utf-8')}
        for filename,blob in blobs.items():
            path=stage/filename; path.write_bytes(blob); publications.append((path,output_root/filename))
        doc = stage / 'bet_cancel.md'
        doc.write_bytes(generated_doc(report).encode('utf-8'))
        publications.append((doc, docs_root / doc.name))
        manifest['artifacts'] = {relative_path(dest, output_root): text_sha(path.read_bytes())
                                 for path, dest in publications if path.suffix != '.parquet'}
        path=stage/'_manifest.json'; path.write_bytes(json_bytes(manifest)); publications.append((path,output_root/'_manifest.json'))
        expected={(output_root / info['path']).resolve() for info in recorded.values() if info['format']=='parquet'}
        existing=set(output_root.rglob('*.parquet'))
        if existing-expected: raise RuntimeError('Unexpected existing Gold Parquet files; choose new output root')
        for path,dest in publications:
            if dest.exists() and output_hash(path, path.suffix.lstrip('.')) != output_hash(dest, path.suffix.lstrip('.')):
                raise RuntimeError(f'Existing Gold artifact immutable; choose new output/docs locations: {dest}')
        assert_preserved(sources, control)
        for path,dest in publications:
            if dest.exists(): continue
            dest.parent.mkdir(parents=True,exist_ok=True); path.replace(dest)
    print(f"Gold passed: {report['counts'][gold.FACT]:,} facts; {report['metrics']['eligible_facts']:,} eligible; {len(report['checks'])} checks.",flush=True)
    return report


def verify(output_root=GOLD_ROOT):
    output_root = Path(output_root).resolve()
    manifest = json.loads((output_root / '_manifest.json').read_text(encoding='utf-8'))
    if manifest['code'] != code_hashes():
        raise RuntimeError('Gold code hash differs from recorded generation')
    tables, sources, control, version = load_inputs(output_root / manifest['input_root'])
    if version != manifest['dq_dataset_version'] or {n: v['sha256'] for n, v in sources.items()} != manifest['sources']:
        raise RuntimeError('Develop clean version or hashes differ from Gold manifest')
    outputs, report = gold.build(tables, manifest['unit_amount'])
    report['dataset_version'] = manifest['dataset_version']
    recorded = json.loads((output_root / '_validation.json').read_text(encoding='utf-8'))
    if report != recorded:
        raise RuntimeError('Gold remeasurement differs from stored report')
    expected = {(output_root / info['path']).resolve() for info in manifest['outputs'].values() if info['format'] == 'parquet'}
    existing = set(output_root.rglob('*.parquet'))
    if existing != expected:
        raise RuntimeError('Gold/audit Parquet file set differs')
    for name, table in outputs.items():
        info = manifest['outputs'][name]
        path = output_root / info['path']
        digest = output_hash(path, info['format'])
        matches = (pq.read_table(path).equals(table) if info['format'] == 'parquet'
                   else digest == text_sha(csv_bytes(table.to_pylist())))
        if digest != info['sha256'] or table.num_rows != info['rows'] or not matches:
            raise RuntimeError(f'Gold data mismatch: {name}')
    for relative, digest in manifest['artifacts'].items():
        if text_sha((output_root / relative).read_bytes()) != digest:
            raise RuntimeError(f'Gold documentation/metadata mismatch: {relative}')
    assert_preserved(sources, control)
    print(f"Read-only Gold verified: {len(outputs)-1} Parquet tables + summary CSV, {len(report['checks'])} checks; all values/schemas/hashes, audits and documentation matched.", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
