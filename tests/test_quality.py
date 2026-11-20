"""Quality decisions: exclusion, marking, unambiguous repairs and semantic merge."""
from datetime import date,datetime,timedelta,timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

spec=importlib.util.spec_from_file_location('quality_tests_engine',Path(__file__).resolve().parents[1]/'src/02_quality.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
KST=timezone(timedelta(hours=9))


def traced(name,data,source_rows=None):
    size=len(next(iter(data.values())))
    result=pa.table(data)
    result=result.append_column('_SRC_ROW_NO',pa.array(source_rows or range(1,size+1),type=pa.int64()))
    result=result.append_column('_SRC_BRONZE_FILE',pa.array([name+'.parquet']*size))
    return result


def fixture():
    tables={name:traced(name,{'DUMMY':['keep']}) for name in q.TABLES}
    tables['BET_ORDER']=traced('BET_ORDER',{
      'ORDER_NO':['S','C'],'ORDER_TYPE_CD':['SALE','CANCEL'],'ORIG_ORDER_NO':[None,'S'],
      'SALE_DTM':pa.array([datetime(2026,1,3,9,tzinfo=KST),datetime(2026,1,3,10,tzinfo=KST)],type=pa.timestamp('ms',tz='Asia/Seoul')),
      'TICKET_CNT':pa.array([1,1],type=pa.int32()),'TOTAL_AMT':pa.array([300,0],type=pa.int64())})
    tables['BET_TICKET']=traced('BET_TICKET',{
      'ORDER_NO':['S','S','C'],'TICKET_SEQ':pa.array([1,1,1],type=pa.int32()),
      'RC_DT':pa.array([date(2026,1,3)]*3,type=pa.date32()),'RC_NO':pa.array([1]*3,type=pa.int32()),
      'BET_TYPE_CD':['WIN']*3,'CHUL_NO':pa.array([1]*3,type=pa.int32()),'HR_NM':pa.array([None,None,'말'],type=pa.string()),
      'BET_AMT':pa.array([300,300,0],type=pa.int32()),'TICKET_STAT_CD':['SOLD','SOLD','CANCEL'],
      'SOURCE_FILE':['bet_ticket.csv']*3,'INGESTED_AT':['earlier','later','later']})
    tables['RC_RACE']=traced('RC_RACE',{'RC_DT':pa.array([date(2026,1,3)],type=pa.date32()),'RC_NO':pa.array([1],type=pa.int32()),
      'START_DTM':pa.array([datetime(2026,1,3,10,tzinfo=KST)],type=pa.timestamp('ms',tz='Asia/Seoul'))})
    tables['RC_ENTRY']=traced('RC_ENTRY',{'RC_DT':pa.array([date(2026,1,3)],type=pa.date32()),'RC_NO':pa.array([1],type=pa.int32()),
      'CHUL_NO':pa.array([1],type=pa.int32()),'HR_NM':['말']})
    tables['HR_VET_HIST']=traced('HR_VET_HIST',{'VET_SEQ':pa.array([595,664],type=pa.int32()),
      'VET_DT':pa.array([date(2026,1,2)]*2,type=pa.date32()),'HR_NM':['A','B'],'VET_NM':['일,열사병']*2,'TR_GRP_NO':['01','01']},[595,664])
    tables['HR_VET_TYPE_BRIDGE']=traced('HR_VET_TYPE_BRIDGE',{'VET_SEQ':pa.array([595,595,664,664],type=pa.int32()),
      'VET_TYPE_SEQ':pa.array([1,2,1,2],type=pa.int32()),'VET_TYPE_NM':['일','열사병','일','열사병']},[595,595,664,664])
    tables['HR_WEEKLY_SNAPSHOT']=traced('HR_WEEKLY_SNAPSHOT',{'SNAPSHOT_DT':pa.array([date(2026,1,2),date(2026,1,1)],type=pa.date32()),
      'HR_NM':['A','B'],'TR_GRP_NO':['99','02']})
    return tables


class QualityTests(unittest.TestCase):
    def test_minimum_row_and_path_tie_break_ignore_tracking(self):
        frame=pd.DataFrame({'ORDER_NO':['A']*3,'TICKET_SEQ':[1]*3,'BET_AMT':[100]*3,
                            'SOURCE_FILE':['x','y','z'],'INGESTED_AT':['a','b','c'],
                            '_SRC_ROW_NO':[5,2,2],'_SRC_BRONZE_FILE':['z','b','a'],
                            '_DQ_INPUT_ROW_NO':[1,2,3],'_DQ_ROW_ID':['r1','r2','r3']})
        kept,removed,_,columns=q.duplicate_partition(frame)
        self.assertEqual(list(kept._DQ_ROW_ID),['r3'])
        self.assertEqual(len(removed),2)
        self.assertEqual(columns,['ORDER_NO','TICKET_SEQ','BET_AMT'])

    def test_same_pk_different_values_not_automatically_deleted(self):
        frame=pd.DataFrame({'ORDER_NO':['A']*2,'TICKET_SEQ':[1]*2,'BET_AMT':[100,200],
                            '_SRC_ROW_NO':[1,2],'_SRC_BRONZE_FILE':['x']*2,
                            '_DQ_INPUT_ROW_NO':[1,2],'_DQ_ROW_ID':['r1','r2']})
        with self.assertRaises(ValueError):q.duplicate_partition(frame)

    def test_boundary_zero_late_and_no_business_exclusion_of_other_late(self):
        engine=q.Quality(fixture());clean,excluded=engine.run()
        self.assertFalse([c for c in engine.checks if not c['passed']])
        self.assertEqual(engine.metrics['duplicate_excluded'],1)
        self.assertEqual(engine.metrics['zero_tickets'],1)
        self.assertEqual(engine.metrics['zero_late_tickets'],1)
        ticket=clean['BET_TICKET'].to_pandas().set_index('ORDER_NO')
        self.assertEqual(ticket.loc['C','LATE_CANCEL_YN'],'Y') # exactly start time counts
        self.assertEqual(ticket.loc['C','ZERO_LATE_CANCEL_YN'],'Y')
        self.assertEqual(ticket.loc['C','BUSINESS_AGG_ELIGIBLE_YN'],'N')
        self.assertEqual(ticket.loc['S','HR_NM'],'말')
        self.assertIsNone(clean['BET_TICKET']['HR_NM_BEFORE'][0].as_py())
        self.assertEqual(excluded['BET_TICKET'].num_rows,1)
        self.assertEqual(set(excluded),{'BET_TICKET'})

    def test_positive_late_cancel_remains_business_eligible(self):
        tables=fixture()
        # Set by schema name, preserving any future fixture column ordering.
        tables['BET_TICKET']=fixture()['BET_TICKET'].set_column(fixture()['BET_TICKET'].schema.get_field_index('BET_AMT'),'BET_AMT',pa.array([300,300,-100],type=pa.int32()))
        engine=q.Quality(tables);clean,_=engine.run()
        t=clean['BET_TICKET'].to_pandas().set_index('ORDER_NO')
        self.assertEqual(t.loc['C','LATE_CANCEL_YN'],'Y')
        self.assertEqual(t.loc['C','BUSINESS_AGG_ELIGIBLE_YN'],'Y')

    def test_ambiguous_entry_does_not_fill_name(self):
        tables=fixture();tables['RC_ENTRY']=pa.concat_tables([tables['RC_ENTRY'],tables['RC_ENTRY']])
        engine=q.Quality(tables);clean,_=engine.run()
        self.assertEqual(engine.metrics['filled_names'],0)
        sale=clean['BET_TICKET'].to_pandas().set_index('ORDER_NO').loc['S']
        self.assertEqual(sale['HR_NM_FILL_STATUS_CD'],'AMBIGUOUS')
        self.assertTrue(pd.isna(sale['HR_NM']))

    def test_strict_prior_medical_and_merge_not_exclusion(self):
        engine=q.Quality(fixture());clean,excluded=engine.run()
        self.assertEqual(engine.metrics['vet_no_prior'],1) # same-day snapshot is not earlier
        self.assertEqual(engine.metrics['vet_group_mismatch'],1)
        self.assertEqual(clean['HR_VET_HIST']['VET_NM'].to_pylist(),['일,열사병']*2)
        self.assertEqual(clean['HR_VET_TYPE_BRIDGE']['VET_TYPE_NM'].to_pylist(),['일·열사병']*2)
        self.assertNotIn('HR_VET_TYPE_BRIDGE',excluded)
        self.assertEqual(len(engine.merges),2)
        self.assertEqual(sum(m['INPUT_ITEMS'] for m in engine.merges),4)
        self.assertEqual(sum(m['OUTPUT_ITEMS'] for m in engine.merges),2)
        self.assertEqual(clean['HR_VET_HIST'].num_rows,2)

    def test_disk_idempotence_and_immutable_existing_clean(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'silver';source.mkdir()
            for name,table in fixture().items():pq.write_table(table,source/(name+'.parquet'))
            before={p:q.sha(p) for p in source.glob('*.parquet')}
            args=dict(input_root=source,meta_root=root/'meta',docs_root=root/'docs')
            import contextlib,io
            with contextlib.redirect_stdout(io.StringIO()):
                first=q.run(**args)
            artifacts=[p for d in [source/'clean',source/'_excluded',root/'meta',root/'docs'] for p in d.glob('*') if p.is_file()]
            snapshot={p:(q.sha(p),p.stat().st_mtime_ns) for p in artifacts}
            with contextlib.redirect_stdout(io.StringIO()):
                second=q.run(**args)
            self.assertEqual(first,second)
            self.assertEqual(snapshot,{p:(q.sha(p),p.stat().st_mtime_ns) for p in artifacts})
            self.assertEqual(before,{p:q.sha(p) for p in source.glob('*.parquet')})
            t=pq.read_table(source/'BET_TICKET.parquet')
            column=t.schema.get_field_index('BET_AMT')
            pq.write_table(t.set_column(column,'BET_AMT',pa.array([400,400,0],type=pa.int32())),source/'BET_TICKET.parquet')
            with self.assertRaisesRegex(RuntimeError,'immutable'):
                q.run(**args)
            self.assertEqual(snapshot,{p:(q.sha(p),p.stat().st_mtime_ns) for p in artifacts})


if __name__=='__main__':unittest.main()
