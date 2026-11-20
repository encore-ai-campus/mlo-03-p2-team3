from datetime import date, datetime, timedelta, timezone
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

KST = timezone(timedelta(hours=9))


def fixture():
    moment = datetime(2026, 1, 3, 9, tzinfo=KST)
    tables = {
        'MBR_MASTER': [dict(MBR_NO='M', BIRTH_DT=date(1970, 1, 4), JOIN_DT=date(2020, 1, 1))],
        'BET_ORDER': [dict(ORDER_NO='S', ORDER_TYPE_CD='SALE', ORIG_ORDER_NO=None, MBR_NO='M',
                           CHNL_CD='OTB', OTB_BRANCH_NO='01', SALE_DTM=moment, HEADER_MISMATCH_YN='N'),
                      dict(ORDER_NO='C', ORDER_TYPE_CD='CANCEL', ORIG_ORDER_NO='S', MBR_NO='M',
                           CHNL_CD='APP', OTB_BRANCH_NO=None, SALE_DTM=moment + timedelta(hours=1), HEADER_MISMATCH_YN='N')],
        'BET_TICKET': [dict(ORDER_NO='S', TICKET_SEQ=1, RC_DT=date(2026, 1, 3), RC_NO=1,
                            BET_TYPE_CD='WIN', CHUL_NO=1, CHUL_NO2=None, HR_NM='A', HR_NM2=None,
                            UNIT_CNT=3, BET_AMT=300, TICKET_STAT_CD='SOLD', INVALID_YN='N', LATE_CANCEL_YN='N'),
                       dict(ORDER_NO='C', TICKET_SEQ=99, RC_DT=date(2026, 1, 3), RC_NO=1,
                            BET_TYPE_CD='WIN', CHUL_NO=1, CHUL_NO2=None, HR_NM='A', HR_NM2=None,
                            UNIT_CNT=-1, BET_AMT=-100, TICKET_STAT_CD='CANCEL', INVALID_YN='N', LATE_CANCEL_YN='Y')],
        'RC_RACE': [dict(RC_DT=date(2026, 1, 3), RC_NO=1, MEET_CD='JEJU', START_DTM=moment + timedelta(hours=1),
                         RC_DIST_M=1000, RC_GRADE_CD='5')],
        'RC_ENTRY': [dict(RC_DT=date(2026, 1, 3), RC_NO=1, CHUL_NO=1, HR_NM='A', HR_AGE=4, HR_SEX_CD='F')],
        'RC_RESULT': [dict(RC_DT=date(2026, 1, 3), RC_NO=1, CHUL_NO=1, ENTRY_STAT_CD='RAN')],
        'HR_WEEKLY_SNAPSHOT': [dict(HR_NM='A', HR_BIRTH_DT=date(2022, 1, 1), SIRE_NM='P', DAM_NM='Q',
                                    SNAPSHOT_DT=date(2026, 1, 2), Y1_RC_CNT=10, Y1_1ST_CNT=2,
                                    TOT_RC_CNT=20, TOT_1ST_CNT=3)]}
    for name, rows in tables.items():
        for i, row in enumerate(rows, 1):
            row.update(_DQ_ROW_ID=f'{name}:{i}', _SRC_BRONZE_FILE=f'{name}.parquet', _SRC_ROW_NO=i,
                       _DQ_DATASET_VERSION='fixture')
    return tables


class GoldTests(unittest.TestCase):
    def engine(self):
        path = Path(__file__).resolve().parents[1] / 'src/gold.py'
        self.assertTrue(path.exists(), 'Gold implementation is missing')
        spec = importlib.util.spec_from_file_location('gold_test_engine', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def build(self, tables=None):
        return self.engine().build(tables or fixture())

    def fact(self, output):
        return output['fct_bet_selection_cancel_50s'].to_pylist()[0]

    def test_late_cancel_allowed_and_sequence_not_a_link_key(self):
        output, report = self.build()
        f = self.fact(output)
        self.assertEqual((f['age_at_purchase'], f['analysis_eligible'], f['has_verified_customer_cancel']), (55, 1, 1))
        self.assertEqual(f['verified_cancel_amount_krw'], 100)
        self.assertEqual(f['late_cancel_detail_count'], 1)
        self.assertEqual(f['first_cancel_at'], fixture()['BET_ORDER'][1]['SALE_DTM'])
        self.assertTrue(all(c['passed'] for c in report['checks']))

    def test_zero_cancel_excluded_from_both_aggregates(self):
        t = fixture(); t['BET_TICKET'][1].update(BET_AMT=0, UNIT_CNT=0, INVALID_YN='Y')
        output, _ = self.build(t); f = self.fact(output)
        self.assertEqual(f['has_verified_customer_cancel'], 0)
        self.assertEqual(f['verified_cancel_amount_krw'], 0)
        self.assertEqual(f['late_cancel_detail_count'], 0)
        self.assertEqual(output['cancel_link_audit'].to_pylist()[0]['link_status'], 'ZERO_EXCLUDED')

    def test_unknown_reference_marks_plausible_purchase_ambiguous(self):
        t = fixture(); t['BET_ORDER'][1]['ORIG_ORDER_NO'] = None
        output, _ = self.build(t); f = self.fact(output)
        self.assertIsNone(f['has_verified_customer_cancel'])
        self.assertIn('UNRESOLVED_CANCEL_CONTEXT', f['exclusion_reasons'])
        self.assertEqual(f['analysis_eligible'], 0)

    def test_excess_cancel_not_reported_as_verified_binary_label(self):
        t = fixture(); t['BET_TICKET'][1].update(BET_AMT=-400, UNIT_CNT=-4)
        output, _ = self.build(t); f = self.fact(output)
        self.assertIsNone(f['has_verified_customer_cancel'])
        self.assertIn('CANCEL_EXCEEDS_PURCHASE', f['exclusion_reasons'])

    def test_cumulative_excess_across_multiple_partial_cancellations(self):
        t = fixture(); t['BET_TICKET'][1].update(BET_AMT=-200, UNIT_CNT=-2)
        second = dict(t['BET_TICKET'][1]); second.update(TICKET_SEQ=100, _DQ_ROW_ID='BET_TICKET:3', _SRC_ROW_NO=3)
        t['BET_TICKET'].append(second)
        output, _ = self.build(t); f = self.fact(output)
        self.assertIsNone(f['has_verified_customer_cancel'])
        self.assertEqual(f['analysis_eligible'], 0)
        self.assertIn('CANCEL_EXCEEDS_PURCHASE', f['exclusion_reasons'])

    def test_future_snapshot_and_zero_starts_have_distinct_exclusion(self):
        t = fixture(); t['HR_WEEKLY_SNAPSHOT'][0]['SNAPSHOT_DT'] = date(2026, 1, 3)
        output, _ = self.build(t)
        self.assertIn('NO_PRIOR_SNAPSHOT', self.fact(output)['exclusion_reasons'])
        t = fixture(); t['HR_WEEKLY_SNAPSHOT'][0].update(Y1_RC_CNT=0, Y1_1ST_CNT=0)
        output, _ = self.build(t)
        self.assertIn('ZERO_RECENT_STARTS', self.fact(output)['exclusion_reasons'])
        self.assertIsNone(self.fact(output)['recent1y_win_rate'])

    def test_same_name_multiple_births_cannot_be_merged(self):
        t = fixture(); second = dict(t['HR_WEEKLY_SNAPSHOT'][0]); second.update(HR_BIRTH_DT=date(2021, 1, 1), SNAPSHOT_DT=date(2026, 1, 1))
        t['HR_WEEKLY_SNAPSHOT'].append(second)
        output, _ = self.build(t)
        self.assertEqual(self.fact(output)['horse_key'], 'UNKNOWN')
        self.assertIn('AMBIGUOUS_HORSE_IDENTITY', self.fact(output)['exclusion_reasons'])

    def test_purchase_group_sum_and_input_partition(self):
        t = fixture(); second = dict(t['BET_TICKET'][0]); second.update(TICKET_SEQ=2, _DQ_ROW_ID='BET_TICKET:3', _SRC_ROW_NO=3)
        t['BET_TICKET'].append(second)
        output, _ = self.build(t); f = self.fact(output)
        self.assertEqual((f['purchase_amount_krw'], f['purchase_stake_units'], f['purchase_detail_count']), (600, 6, 2))
        self.assertEqual(output['ticket_disposition'].num_rows, 3)
        self.assertEqual(output['dim_channel'].to_pylist()[1]['channel_cd'], 'OTB01')

    def test_deterministic_order_and_age_boundaries(self):
        g = self.engine()
        self.assertEqual(g.age_at(date(1970, 1, 4), date(2026, 1, 3)), 55)
        self.assertEqual(g.age_at(date(1970, 1, 4), date(2026, 1, 4)), 56)
        a, _ = g.build(fixture()); t = fixture()
        for rows in t.values(): rows.reverse()
        b, _ = g.build(t)
        for name in a: self.assertTrue(a[name].equals(b[name]), name)

    def test_disk_replay_partial_recovery_and_changed_input_rejection(self):
        src = Path(__file__).resolve().parents[1] / 'src'
        sys.path.insert(0, str(src))
        try:
            import gold_pipeline as pipeline
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder); source = root/'clean'; dqmeta = root/'dqmeta'
            source.mkdir(); dqmeta.mkdir()
            approved = {}
            for name, rows in fixture().items():
                path = source/(name+'.parquet'); pq.write_table(pa.Table.from_pylist(rows), path)
                approved['clean/'+name] = dict(sha256=pipeline.sha(path))
            (dqmeta/'dq_manifest.json').write_text(json.dumps(dict(dataset_version='fixture', outputs=approved)), encoding='utf-8')
            (dqmeta/'dq_validation.json').write_text(json.dumps(dict(status='passed', dataset_version='fixture', checks=[dict(passed=True)])), encoding='utf-8')
            args = dict(input_root=source, dq_meta_root=dqmeta, output_root=root/'gold', meta_root=root/'meta', docs_root=root/'docs')
            first = pipeline.run(**args)
            self.assertTrue((root/'meta/WIN_RATE_CANCEL_SUMMARY.csv').is_file())
            self.assertFalse((root/'gold/win_rate_cancel_summary.parquet').exists())
            self.assertTrue((root/'gold/DIM_MEMBER.parquet').is_file())
            self.assertTrue((root/'gold/FCT_BET_SELECTION_CANCEL_50S.parquet').is_file())
            self.assertIn('DIM_MEMBER.parquet', {p.name for p in (root/'gold').iterdir()})
            self.assertIn('WIN_RATE_CANCEL_SUMMARY.csv', {p.name for p in (root/'meta').iterdir()})
            self.assertTrue((root/'meta/audit/TICKET_DISPOSITION.parquet').is_file())
            self.assertFalse((root/'gold/audit').exists())
            with (root/'meta/WIN_RATE_CANCEL_SUMMARY.csv').open(encoding='utf-8-sig', newline='') as stream:
                import csv
                summary = list(csv.DictReader(stream))
            self.assertEqual(len(summary), 10)
            self.assertEqual(sum(int(row['purchase_selection_groups']) for row in summary if row['scope']=='all_positive_starts'), 1)
            artifacts = [p for directory in ['gold','meta','docs'] for p in (root/directory).rglob('*') if p.is_file()]
            snapshot = {p:(pipeline.sha(p),p.stat().st_mtime_ns) for p in artifacts}
            upstream = {p:(pipeline.sha(p),p.stat().st_mtime_ns) for directory in [source,dqmeta] for p in directory.iterdir()}
            self.assertEqual(first, pipeline.run(**args))
            self.assertEqual(snapshot, {p:(pipeline.sha(p),p.stat().st_mtime_ns) for p in artifacts})
            self.assertEqual(first, pipeline.verify(root/'meta'))
            missing = root/'gold/DIM_MEMBER.parquet'; missing.unlink()
            self.assertEqual(first, pipeline.run(**args))
            self.assertEqual(pipeline.sha(missing), snapshot[missing][0])
            self.assertEqual(upstream, {p:(pipeline.sha(p),p.stat().st_mtime_ns) for p in upstream})
            path = source/'BET_TICKET.parquet'; table = pq.read_table(path)
            pq.write_table(table.slice(0,1), path)
            before = {p:(pipeline.sha(p),p.stat().st_mtime_ns) for p in artifacts}
            with self.assertRaisesRegex(ValueError, 'Unapproved clean input'):
                pipeline.run(**args)
            self.assertEqual(before, {p:(pipeline.sha(p),p.stat().st_mtime_ns) for p in artifacts})


if __name__ == '__main__':
    unittest.main()
