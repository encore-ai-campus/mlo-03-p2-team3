"""Verify quality results without writing data or rerunning upstream stages."""
import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quality_check_engine',Path(__file__).with_name('02_quality.py'))
engine=importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def verify(meta_root=ROOT/'meta'):
    meta_root=Path(meta_root)
    manifest=json.loads((meta_root/'dq_manifest.json').read_text(encoding='utf-8'))
    report=json.loads((meta_root/'dq_validation.json').read_text(encoding='utf-8'))
    if manifest['code_sha256']!=engine.sha(engine.__file__):
        raise RuntimeError('Quality code differs from recorded run; verify in a new output version if data changes.')
    if report['status']!='passed' or not all(c['passed'] for c in report['checks']):
        raise RuntimeError('Recorded quality validation did not pass.')
    source={}
    for name,info in manifest['sources'].items():
        path=Path(info['path'])
        if engine.sha(path)!=info['sha256'] or path.stat().st_mtime_ns!=info['mtime_ns']:
            raise RuntimeError(f'Standardized input changed: {name}')
        source[name]=pq.read_table(path)
    q=engine.Quality(source)
    expected_clean,expected_excluded=q.run()
    if q.metrics!=report['metrics']:
        raise RuntimeError('Independent remeasurement differs from stored quality metrics.')
    for category,expected in [('clean',expected_clean),('_excluded',expected_excluded)]:
        directory=Path(manifest['gold_input'] if category=='clean' else manifest['excluded_input'])
        actual_files={p.stem for p in directory.glob('*.parquet')}
        if actual_files!=set(expected):
            raise RuntimeError(f'{category} file set differs: {actual_files}')
        for name,table in expected.items():
            info=manifest['outputs'][category+'/'+name]
            path=Path(info['path'])
            actual=pq.read_table(path)
            expected_table=table.append_column('_DQ_DATASET_VERSION',pa.array([manifest['dataset_version']]*table.num_rows,type=pa.string()))
            if engine.sha(path)!=info['sha256'] or actual.num_rows!=info['rows'] or not actual.equals(expected_table):
                raise RuntimeError(f'Full value/schema/hash mismatch: {category}/{name}')
    expected_log=pd.DataFrame(q.logs,columns=engine.LOG_FIELDS).to_csv(index=False,lineterminator='\n')
    if (meta_root/'dq_log.csv').read_text(encoding='utf-8-sig')!=expected_log:
        raise RuntimeError('Row-level quality audit differs from recomputed decisions.')
    merge=pd.read_csv(meta_root/'vet_type_merge_log.csv',encoding='utf-8-sig',dtype=str,keep_default_na=False)
    if len(merge)!=len(q.merges) or set(merge.ABSORBED_ROW_ID)!={m['ABSORBED_ROW_ID'] for m in q.merges}:
        raise RuntimeError('Semantic merge lineage differs.')
    print(f"Read-only quality check passed: {len(expected_clean)} clean tables, {report['excluded_rows']:,} duplicate exclusions, {report['semantic_merge_reduction']} semantic reductions, all values/schemas/audit rows/hashes matched.")
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--meta-root',type=Path,default=ROOT/'meta')
    args=parser.parse_args()
    verify(args.meta_root)
