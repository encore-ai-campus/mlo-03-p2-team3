"""Hand-authored boundary and end-to-end tests for reusable normalization."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date, datetime, time
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location('normalize_test_engine',Path(__file__).resolve().parents[1]/'src/02_normalize.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class ConversionTests(unittest.TestCase):
    def convert(self,value,kind='string',op='text',**options):
        return n.convert(value,n.column('raw','RESULT',kind,op,**options))[0]

    def test_mixed_dates_and_kst(self):
        for raw in ('20260522','2026-05-22','2026.05.22','2026/05/22'):
            self.assertEqual(self.convert(raw,'date32'),date(2026,5,22))
        a=self.convert('20260529103300','timestamp')
        b=self.convert('2026-05-29 10:33:00','timestamp')
        self.assertEqual(a,b)
        self.assertEqual(a.utcoffset().total_seconds(),32400)
        self.assertEqual(self.convert('20260522 23:58','timestamp').second,0)
        for bad in ('20260230','2026131','2026-5-22'):
            with self.assertRaises(n.ConversionError):
                self.convert(bad,'date32')

    def test_fraction_and_non_numeric_margin(self):
        self.assertEqual(self.convert('1½','decimal(5,2)','margin_length'),Decimal('1.50'))
        self.assertEqual(self.convert('¾','decimal(5,2)','margin_length'),Decimal('0.75'))
        self.assertEqual(self.convert('','string','margin_code'),'FIRST')
        self.assertEqual(self.convert('-','string','margin_code'),'NA')
        self.assertIsNone(self.convert('코','decimal(5,2)','margin_length'))

    def test_fixed_width_positions_preserve_internal_blanks(self):
        raw='0:48.8'.ljust(7)+'0:16.7'.ljust(7)+' '*7+'0:24.4'.ljust(7)+' '*21
        self.assertEqual(len(raw),49)
        values=[self.convert(raw,'decimal(5,1)','section',index=i) for i in range(7)]
        self.assertEqual(values,[Decimal('48.8'),Decimal('16.7'),None,Decimal('24.4'),None,None,None])

    def test_weight_and_non_run(self):
        self.assertEqual(self.convert('279+14','int32','weight'),279)
        self.assertEqual(self.convert('279+14','int32','weight_diff'),14)
        self.assertEqual(self.convert('279-4','int32','weight_diff'),-4)
        self.assertIsNone(self.convert('279','int32','weight_diff'))
        self.assertIsNone(self.convert('0','int32','weight'))
        self.assertIsNone(self.convert('94','int32','finish'))
        self.assertEqual(self.convert('95','string','entry_status'),'SCRATCHED')

    def test_pass_positions_and_missing_non_run(self):
        raw=('1-  -  - 1- 1- 2','1')
        self.assertEqual([self.convert(raw,'int32','pass_order',index=i) for i in range(6)],[1,None,None,1,1,2])
        self.assertIsNone(self.convert(('-  -  -  -','94'),'int32','pass_order',index=0))
        with self.assertRaises(n.ConversionError):
            self.convert(('1-2','1'),'int32','pass_order',index=0)

    def test_codes_do_not_guess_unlisted_sex(self):
        self.assertEqual(self.convert(' 암 ','string','map',mapping=n.SEX),'F')
        with self.assertRaises(n.ConversionError):
            self.convert('2','string','map',mapping=n.SEX)
        self.assertEqual(self.convert('2','string','map',mapping={'2':'F'}),'F')
        self.assertEqual(self.convert('OTB08','string','branch'),'08')
        self.assertEqual(self.convert('','string','channel'),'UNKNOWN')
        with self.assertRaises(n.ConversionError):
            self.convert('OTB38','string','channel')

    def test_money_units_precision_and_no_rounding(self):
        self.assertEqual(self.convert('3,000천원(개별)','int64','intro_amount'),3000000)
        self.assertIsNone(self.convert('자가생산','int64','intro_amount'))
        self.assertEqual(self.convert('1:13.2','decimal(5,1)','seconds'),Decimal('73.2'))
        for raw,kind in [('1.55','decimal(4,1)'),('1000','decimal(4,1)'),('2147483648','int32'),('1.1','int64')]:
            with self.assertRaises((n.ConversionError,ValueError)):
                self.convert(raw,kind)

    def test_track_optional_moisture(self):
        self.assertEqual(self.convert('날씨: 흐림  주로: 다습 (14%)','string','weather'),'CLOUDY')
        self.assertEqual(self.convert('다습      ( 14.0%)','decimal(5,1)','event_moisture'),Decimal('14.0'))
        self.assertIsNone(self.convert('날씨: 비  주로: 불량','decimal(5,1)','moisture'))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.input=self.root/'input'
        (self.input/'nested').mkdir(parents=True)
        self.output=self.root/'silver'
        self.meta=self.root/'meta'
        self.docs=self.root/'docs'

    def run_engine(self,rules):
        return n.run(self.input,self.output,self.meta,self.docs,specs=rules)

    def test_other_schema_exact_mapping_counts_and_idempotence(self):
        source=self.input/'nested/people.parquet'
        pq.write_table(pa.table({'sex':['2']*5+['1'], 'id':['001']*6}),source)
        before=source.read_bytes()
        rules={'PEOPLE':dict(input='people',columns=[n.column('sex','SEX_CD',op='map',mapping={'2':'F','1':'M'}),n.column('id','PERSON_NO')])}
        self.run_engine(rules)
        table=pq.read_table(self.output/'PEOPLE.parquet')
        self.assertEqual(table['SEX_CD'].to_pylist(),['F']*5+['M'])
        self.assertEqual(table['PERSON_NO'].to_pylist(),['001']*6)
        self.assertEqual(table.num_rows,6)  # duplicates retained
        changes=n.pd.read_csv(self.meta/'silver_value_changes.csv',keep_default_na=False,dtype=str)
        row=changes[(changes.raw_value=='2') & (changes.standard_value=='F')].iloc[0]
        self.assertEqual(row['count'],'5')
        snapshot={str(p.relative_to(self.root)):p.read_bytes() for directory in (self.output,self.meta,self.docs) for p in directory.rglob('*') if p.is_file()}
        self.run_engine(rules)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(snapshot,{str(p.relative_to(self.root)):p.read_bytes() for directory in (self.output,self.meta,self.docs) for p in directory.rglob('*') if p.is_file()})

    def test_standalone_copy_uses_no_project_config(self):
        import shutil, subprocess, sys
        portable=self.root/'portable'
        portable.mkdir()
        script=portable/'02_normalize.py'
        shutil.copyfile(n.__file__,script)
        pq.write_table(pa.table({'gender':['2']*5}),self.input/'person.parquet')
        rules={'tables':{'PERSON':dict(input='person',columns=[n.column('gender','SEX_CD',op='map',mapping={'2':'F'})])}}
        path=portable/'rules.json'
        path.write_text(json.dumps(rules),encoding='utf-8')
        subprocess.run([sys.executable,str(script),'--input-root',str(self.input),
                        '--output-root',str(self.output),'--meta-root',str(self.meta),'--docs-root',str(self.docs),
                        '--spec',str(path)],check=True,capture_output=True)
        self.assertFalse((portable/'config.py').exists())
        self.assertEqual(pq.read_table(self.output/'PERSON.parquet')['SEX_CD'].to_pylist(),['F']*5)

    def test_invalid_conversion_keeps_previous_output(self):
        source=self.input/'x.parquet'
        pq.write_table(pa.table({'amount':['1']}),source)
        rules={'X':dict(input='x',columns=[n.column('amount','AMT','int64')])}
        self.run_engine(rules)
        before=(self.output/'X.parquet').read_bytes()
        pq.write_table(pa.table({'amount':['1.5']}),source)
        with self.assertRaises(RuntimeError):
            self.run_engine(rules)
        self.assertEqual((self.output/'X.parquet').read_bytes(),before)
        self.assertIn('1.5',(self.meta/'silver_issue_log.csv').read_text(encoding='utf-8-sig'))

    def test_missing_mapping_and_overlapping_paths_rejected(self):
        pq.write_table(pa.table({'a':['1'],'unmapped':['keep']}),self.input/'x.parquet')
        rules={'X':dict(input='x',columns=[n.column('a','A')])}
        with self.assertRaises(ValueError):
            self.run_engine(rules)
        with self.assertRaises(ValueError):
            n.run(self.input,self.input/'out',self.meta,self.docs,specs=rules)
        self.assertFalse(self.output.exists())

    def test_sales_split_and_bridge_row_trace(self):
        sales=pa.table({'RC_DATE':['20260522','20260522'],'RC_NO':['1','1'],
                        'POOL_NM':['단식','합계'],'SALES_AMT_RAW':['1,000','1,000']})
        pq.write_table(sales,self.input/'RC_SALES.parquet')
        vet=pa.table({'VET_DT_RAW':['2026.05.22'],'HR_NAME':['말'],'TR_GRP_NO':['01'],
                      'VET_PLACE_NM':['진료소'],'VET_NM_RAW':['정치, 낭치'],'REPORT_DT':['20260522']})
        pq.write_table(vet,self.input/'HR_VET_HIST.parquet')
        specs=n.default_specs()
        rules={name:specs[name] for name in ('RC_SALES','HR_VET_HIST')}
        self.run_engine(rules)
        self.assertEqual(len(list(self.output.glob('*.parquet'))),4)
        self.assertEqual(pq.read_table(self.output/'RC_SALES.parquet')['_SRC_ROW_NO'].to_pylist(),[1])
        self.assertEqual(pq.read_table(self.output/'RC_SALES_TOTAL.parquet')['_SRC_ROW_NO'].to_pylist(),[2])
        bridge=pq.read_table(self.output/'HR_VET_TYPE_BRIDGE.parquet')
        self.assertEqual(bridge['VET_TYPE_NM'].to_pylist(),['정치','낭치'])
        self.assertEqual(bridge['VET_SEQ'].to_pylist(),[1,1])
        self.assertEqual(bridge['VET_TYPE_SEQ'].to_pylist(),[1,2])
        changes=n.pd.read_csv(self.meta/'silver_value_changes.csv',keep_default_na=False,dtype=str)
        diagnosis=changes[(changes.table=='HR_VET_TYPE_BRIDGE') & (changes.standard_column=='VET_TYPE_NM')]
        self.assertEqual(set(diagnosis.raw_value),{'정치, 낭치'})
        self.assertEqual(set(diagnosis.standard_value),{'정치','낭치'})


if __name__=='__main__':
    unittest.main()
