"""Approved quality decisions D-001..D-012; read Silver, create immutable QC outputs."""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('BET_ORDER','BET_TICKET','MBR_MASTER','HR_WEEKLY_SNAPSHOT','TR_WEEKLY_SNAPSHOT',
          'RC_RACE','RC_ENTRY','RC_ODDS','RC_RESULT','RC_SALES','RC_SALES_TOTAL',
          'HR_VET_HIST','HR_VET_TYPE_BRIDGE','RC_CHANGE_EVENT')
DECISIONS = {
 'D-001':'완전 중복 제거 → 나머지 규칙 측정 → 집계별 제외 조건 적용',
 'D-002':'마권 업무값 완전 중복은 최소 _SRC_ROW_NO 유지; 동률은 Bronze 경로 오름차순; 나머지 별도 보관',
 'D-003':'0원 마권 유지·INVALID_YN=Y; 업무 집계 분자/분모 제외, 오류 집계 포함',
 'D-004':'취소 시각 >= 경주 출발 시각: 마권/전표 표시·유지·취소 분석 포함; 0원 교집합 별도 표시',
 'D-005':'마명 빈칸은 출전표 키에 정확히 1행 연결될 때만 보정·원래 값/근거 보존',
 'D-006':'헤더 불일치·원전표 없는 취소는 표시만; 금액·장수·원전표 연결 보정 금지',
 'D-007':'진료 조 불일치/이전 스냅샷 없음 유지; 전체 진료 집계 포함, 해당 분석은 확인 필요',
 'D-008':'표준화 원본 보존; clean 유지, _excluded 완전 중복만; 브리지 의미 병합 별도 대사',
 'D-009':'DQ-차원nn / D-nnn 공통 ID; 모든 처리에 Bronze 경로와 원천 행 번호 기록',
 'D-010':'각자 스타 스키마 완료 후 Silver와 공통 차원 통합; 업무키/타입/코드 사전 합의',
 'D-011':'595·664번 일,열사병 원문 보존; 유형은 일·열사병 1건; 브리지 감소 2는 제외 아닌 의미 병합',
 'D-012':'Gold는 동일 버전 data/02_silver/clean만 입력; 표준화 결과 직접 사용 금지',
}
RULES = {
 'DQ-R00':('D-008;D-009;D-012','입력 행 추적·보존과 Gold 입력 계약'),
 'DQ-U01':('D-002','마권 완전 중복 제외'),
 'DQ-V01':('D-003','0원 마권 표시와 업무집계 제외'),
 'DQ-T01':('D-004','마권 늦은 취소 표시'),
 'DQ-T02':('D-004','고유 전표 늦은 취소 표시'),
 'DQ-C01':('D-005','출전표로 마명 보정'),
 'DQ-S01':('D-006','전표/마권 장수·금액 불일치 표시'),
 'DQ-R03':('D-006','원전표 없는 취소 표시'),
 'DQ-S04':('D-007','진료 기록과 직전 스냅샷 조 불일치'),
 'DQ-R05':('D-007','진료일보다 이전 스냅샷 없음/매칭 불확실'),
 'DQ-S05':('D-011','일,열사병 두 토큰의 단일 유형 의미 병합'),
}
REFERENCE = dict(duplicate_excluded=1052,zero_tickets=3632,late_tickets=1000,late_orders=546,
                 zero_late_tickets=0,filled_names=1560,header_mismatch_orders=93,orig_missing_orders=644,
                 vet_group_mismatch=11,vet_no_prior=71,vet_merge_records=2,bridge_rows=1662,multiple_vet_records=174)
TRACE = {'SOURCE_FILE','INGESTED_AT'}
LOG_FIELDS = ['TABLE_NM','RULE_ID','DECISION_ID','ACTION','REASON','_SRC_BRONZE_FILE','_SRC_ROW_NO',
              '_DQ_INPUT_ROW_NO','_DQ_ROW_ID','COLUMN_NM','OLD_VALUE','NEW_VALUE','RELATED_ROW_ID','EVIDENCE_JSON']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def scalar(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value,(date,datetime,pd.Timestamp)):
        return value.isoformat()
    if isinstance(value,Decimal):
        return str(value)
    if hasattr(value,'item'):
        return value.item()
    return value


def json_text(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,default=scalar,allow_nan=False)


def business_columns(frame):
    return [c for c in frame if not c.startswith('_') and not c.startswith('SRC_') and c not in TRACE]


def duplicate_partition(frame):
    columns = business_columns(frame)
    ordered = frame.sort_values(['_SRC_ROW_NO','_SRC_BRONZE_FILE','_DQ_INPUT_ROW_NO'],kind='stable')
    duplicates = ordered.duplicated(columns,keep='first')
    keep = ordered.loc[~duplicates]
    removed = ordered.loc[duplicates]
    # The source business key is unique after a true full duplicate removal.
    keymap = keep.set_index(['ORDER_NO','TICKET_SEQ'])['_DQ_ROW_ID'].to_dict()
    if keep.duplicated(['ORDER_NO','TICKET_SEQ']).any():
        raise ValueError('Different business values share ticket PK: no approved resolution; not removed.')
    return frame.loc[~frame.index.isin(removed.index)].copy(),removed.copy(),keymap,columns


def add_rows(original,typed):
    """Preserve every original Arrow type; new field types are explicitly supplied."""
    arrays = {}
    for field in original.schema:
        arrays[field.name] = pa.array(typed[field.name],type=field.type,from_pandas=True)
    return arrays


def table_pack(frame,original,new_types):
    arrays = add_rows(original,frame)
    for name,kind in new_types.items():
        if name not in arrays and name in frame:
            arrays[name] = pa.array(frame[name],type=kind,from_pandas=True)
    return pa.table(arrays)


class Quality:
    def __init__(self,tables):
        self.original = tables
        self.frames = {}
        self.types = defaultdict(dict)
        self.excluded = {}
        self.logs = []
        self.merges = []
        self.metrics = {}
        self.checks = []
        for name,table in tables.items():
            if not {'_SRC_ROW_NO','_SRC_BRONZE_FILE'} <= set(table.column_names):
                raise ValueError(f'{name}: existing Silver lineage is required; upstream data will not be changed.')
            frame = table.to_pandas(types_mapper=pd.ArrowDtype)
            self.frames[name] = frame
            self.add(name,'_DQ_INPUT_ROW_NO',list(range(1,len(frame)+1)),pa.int64())
            self.add(name,'_DQ_ROW_ID',[f'{name}:{i:08d}' for i in range(1,len(frame)+1)],pa.string())

    def add(self,name,column,values,kind=pa.string()):
        if column in self.original[name].column_names:
            raise ValueError(f'{name}: QC column collides with standardized input: {column}')
        self.frames[name][column] = pd.Series(values,index=self.frames[name].index,dtype=pd.ArrowDtype(kind)) if not isinstance(values,str) else pd.Series([values]*len(self.frames[name]),index=self.frames[name].index,dtype=pd.ArrowDtype(kind))
        self.types[name][column] = kind

    def log(self,name,row,rule,action,reason,column='',old=None,new=None,related='',evidence=None):
        record = dict(TABLE_NM=name,RULE_ID=rule,DECISION_ID=RULES[rule][0],ACTION=action,REASON=reason,
                      _SRC_BRONZE_FILE=str(row['_SRC_BRONZE_FILE']),_SRC_ROW_NO=int(row['_SRC_ROW_NO']),
                      _DQ_INPUT_ROW_NO=int(row['_DQ_INPUT_ROW_NO']),_DQ_ROW_ID=str(row['_DQ_ROW_ID']),
                      COLUMN_NM=column,OLD_VALUE=json_text(scalar(old)),NEW_VALUE=json_text(scalar(new)),
                      RELATED_ROW_ID=related,EVIDENCE_JSON=json_text(evidence or {}))
        self.logs.append(record)

    def check(self,name,expected,actual):
        passed=expected==actual
        expected=sorted(expected) if isinstance(expected,set) else expected
        actual=sorted(actual) if isinstance(actual,set) else actual
        self.checks.append(dict(check=name,expected=expected,actual=actual,passed=passed))

    def run(self):
        self.deduplicate()
        self.ticket_rules()
        self.medical_rules()
        self.merge_diagnosis()
        self.decorate()
        clean={name:table_pack(frame,self.original[name],self.types[name]) for name,frame in self.frames.items()}
        excluded={name:table_pack(frame,self.original[name],self.types[name]) for name,frame in self.excluded.items()}
        self.validate(clean,excluded)
        return clean,excluded

    def deduplicate(self):
        name='BET_TICKET'
        keep,removed,keymap,columns=duplicate_partition(self.frames[name])
        self.frames[name]=keep
        self.excluded[name]=removed
        for row in removed.to_dict('records'):
            self.log(name,row,'DQ-U01','EXCLUDE','업무값 완전 중복; 최소 원천 행 번호 유지',related=keymap[(row['ORDER_NO'],row['TICKET_SEQ'])],
                     evidence=dict(business_columns=columns,selection_order=['_SRC_ROW_NO','_SRC_BRONZE_FILE','_DQ_INPUT_ROW_NO']))
        self.metrics['duplicate_excluded']=len(removed)

    def ticket_rules(self):
        t=self.frames['BET_TICKET'];o=self.frames['BET_ORDER'];r=self.frames['RC_RACE'];e=self.frames['RC_ENTRY']
        if o.duplicated(['ORDER_NO']).any() or r.duplicated(['RC_DT','RC_NO']).any():
            raise ValueError('Order/race lookup is ambiguous; no arbitrary row selected.')
        self.add('BET_TICKET','INVALID_YN',['Y' if v==0 else 'N' for v in t.BET_AMT])
        self.add('BET_TICKET','BUSINESS_AGG_ELIGIBLE_YN',['N' if v==0 else 'Y' for v in t.BET_AMT])
        zero=t.INVALID_YN.eq('Y')
        self.metrics['zero_tickets']=int(zero.sum())
        for row in t.loc[zero].to_dict('records'):
            self.log('BET_TICKET',row,'DQ-V01','MARK','0원 마권 유지; 업무 분자·분모 제외, 오류 집계 포함','INVALID_YN','N','Y',evidence=dict(BET_AMT=scalar(row['BET_AMT'])))
        j=t.merge(o[['ORDER_NO','ORDER_TYPE_CD','SALE_DTM','_DQ_ROW_ID']],on='ORDER_NO',how='left',validate='many_to_one',suffixes=('','_ORDER'))
        j=j.merge(r[['RC_DT','RC_NO','START_DTM']],on=['RC_DT','RC_NO'],how='left',validate='many_to_one')
        if j[['ORDER_TYPE_CD','SALE_DTM','START_DTM']].isna().any().any():
            raise ValueError('Missing order/race time lookup: late-cancel result cannot be assumed N.')
        cancel=j.ORDER_TYPE_CD.eq('CANCEL') & j.TICKET_STAT_CD.eq('CANCEL')
        # Reject unexplained cancel semantics instead of quietly undercounting.
        self.check('cancel order vs ticket status',True,bool(j.ORDER_TYPE_CD.eq('CANCEL').equals(j.TICKET_STAT_CD.eq('CANCEL'))))
        late=cancel & j.SALE_DTM.ge(j.START_DTM)
        late_ids=set(j.loc[late,'_DQ_ROW_ID'])
        late_orders=set(j.loc[late,'ORDER_NO'])
        zero_late_ids=set(j.loc[late & j.INVALID_YN.eq('Y'),'_DQ_ROW_ID'])
        zero_late_orders=set(j.loc[late & j.INVALID_YN.eq('Y'),'ORDER_NO'])
        for name,frame in [('BET_TICKET',t),('BET_ORDER',o)]:
            ids=late_ids if name=='BET_TICKET' else late_orders
            zero_ids=zero_late_ids if name=='BET_TICKET' else zero_late_orders
            source='_DQ_ROW_ID' if name=='BET_TICKET' else 'ORDER_NO'
            self.add(name,'LATE_CANCEL_YN',['Y' if v in ids else 'N' for v in frame[source]])
            self.add(name,'ZERO_LATE_CANCEL_YN',['Y' if v in zero_ids else 'N' for v in frame[source]])
        self.metrics.update(late_tickets=len(late_ids),late_orders=len(late_orders),zero_late_tickets=len(zero_late_ids),
                            late_cancel_amount=int(j.loc[late,'BET_AMT'].sum()),zero_late_orders=len(zero_late_orders))
        for row in j.loc[late].to_dict('records'):
            self.log('BET_TICKET',row,'DQ-T01','MARK','취소 시각 >= 해당 경주 출발 시각; 취소 분석에 포함','LATE_CANCEL_YN','N','Y',
                     related=row['_DQ_ROW_ID_ORDER'],evidence=dict(SALE_DTM=scalar(row['SALE_DTM']),START_DTM=scalar(row['START_DTM']),ZERO_LATE_CANCEL_YN=row['ZERO_LATE_CANCEL_YN'] if 'ZERO_LATE_CANCEL_YN' in row else ('Y' if row['_DQ_ROW_ID'] in zero_late_ids else 'N')))
        late_counts=j.loc[late].groupby('ORDER_NO').size().to_dict()
        for row in o.loc[o.LATE_CANCEL_YN.eq('Y')].to_dict('records'):
            self.log('BET_ORDER',row,'DQ-T02','MARK','전표 내 늦은 취소 마권이 하나 이상; 전표 지표는 고유 전표 수','LATE_CANCEL_YN','N','Y',
                     evidence=dict(late_ticket_count=int(late_counts[row['ORDER_NO']])))
        # Only a unique entry row may repair the first horse name.
        entry_groups={key:g for key,g in e.groupby(['RC_DT','RC_NO','CHUL_NO'],dropna=False,sort=False)}
        self.add('BET_TICKET','HR_NM_BEFORE',t.HR_NM.tolist())
        self.add('BET_TICKET','HR_NM_FILLED_YN','N')
        self.add('BET_TICKET','HR_NM_FILL_STATUS_CD',['NOT_NEEDED' if not pd.isna(v) else 'PENDING' for v in t.HR_NM])
        filled=0
        for index,row in t.loc[t.HR_NM.isna()].iterrows():
            key=(row.RC_DT,row.RC_NO,row.CHUL_NO)
            candidate=entry_groups.get(key)
            if candidate is not None and len(candidate)==1 and pd.notna(candidate.iloc[0].HR_NM):
                match=candidate.iloc[0]
                t.at[index,'HR_NM']=match.HR_NM
                t.at[index,'HR_NM_FILLED_YN']='Y'
                t.at[index,'HR_NM_FILL_STATUS_CD']='FILLED_UNIQUE_ENTRY'
                filled+=1
                self.log('BET_TICKET',row,'DQ-C01','CORRECT','경주일+경주번호+마번으로 출전표 정확히 1행 연결','HR_NM',None,match.HR_NM,
                         related=match._DQ_ROW_ID,evidence=dict(RC_DT=scalar(row.RC_DT),RC_NO=int(row.RC_NO),CHUL_NO=int(row.CHUL_NO),match_rows=1))
            else:
                status='NO_MATCH' if candidate is None else 'AMBIGUOUS' if len(candidate)!=1 else 'ENTRY_NAME_MISSING'
                t.at[index,'HR_NM_FILL_STATUS_CD']=status
                self.log('BET_TICKET',row,'DQ-C01','KEEP','유일한 보정 근거가 없어 원래 빈값 유지','HR_NM',None,None,evidence=dict(status=status))
        self.metrics['filled_names']=filled
        # Header reconciliation intentionally uses ALL deduplicated details, including zero tickets.
        group=t.groupby('ORDER_NO',dropna=False).agg(DETAIL_ROWS=('TICKET_SEQ','size'),DETAIL_AMT=('BET_AMT','sum'))
        h=o.merge(group,on='ORDER_NO',how='left',validate='one_to_one')
        h['DETAIL_ROWS']=h.DETAIL_ROWS.fillna(0)
        h['DETAIL_AMT']=h.DETAIL_AMT.fillna(0)
        bad=h.TICKET_CNT.ne(h.DETAIL_ROWS) | h.TOTAL_AMT.ne(h.DETAIL_AMT)
        mismatches=set(h.loc[bad,'ORDER_NO'])
        sale_orders=set(o.loc[o.ORDER_TYPE_CD.eq('SALE'),'ORDER_NO'])
        missing=o.ORDER_TYPE_CD.eq('CANCEL') & ~o.ORIG_ORDER_NO.isin(sale_orders)
        orig_missing=set(o.loc[missing,'ORDER_NO'])
        self.metrics.update(header_mismatch_orders=len(mismatches),orig_missing_orders=len(orig_missing))
        order_ids=o.set_index('ORDER_NO')['_DQ_ROW_ID'].to_dict()
        header_lookup=h.set_index('ORDER_NO').to_dict('index')
        for name,frame in [('BET_ORDER',o),('BET_TICKET',t)]:
            for flag,ids,rule in [('HEADER_MISMATCH_YN',mismatches,'DQ-S01'),('ORIG_MISSING_YN',orig_missing,'DQ-R03')]:
                self.add(name,flag,['Y' if v in ids else 'N' for v in frame.ORDER_NO])
                for row in frame.loc[frame[flag].eq('Y')].to_dict('records'):
                    evidence={}
                    if flag=='HEADER_MISMATCH_YN':
                        values=header_lookup[row['ORDER_NO']]
                        evidence={c:scalar(values[c]) for c in ['TICKET_CNT','DETAIL_ROWS','TOTAL_AMT','DETAIL_AMT']}
                    self.log(name,row,rule,'MARK','전표·상세 불일치: 원천 수치 보존' if flag=='HEADER_MISMATCH_YN' else '확인되는 원구매 SALE 전표 없음: 추정 연결 금지',
                             flag,'N','Y',related=order_ids[row['ORDER_NO']],evidence=evidence)

    def medical_rules(self):
        v=self.frames['HR_VET_HIST'];h=self.frames['HR_WEEKLY_SNAPSHOT']
        history={name:g.sort_values('SNAPSHOT_DT',kind='stable') for name,g in h.groupby('HR_NM',sort=False)}
        groups=[];statuses=[];dates=[];snapshot_groups=[]
        mismatch=missing=0
        for row in v.to_dict('records'):
            prior=history.get(row['HR_NM'])
            chosen=None
            if prior is not None:
                all_dates=list(prior.SNAPSHOT_DT)
                pos=bisect_left(all_dates,row['VET_DT'])-1
                if pos>=0:
                    selected=prior.loc[prior.SNAPSHOT_DT.eq(all_dates[pos])]
                    if len(selected)==1:
                        chosen=selected.iloc[0]
            if chosen is None:
                groups.append('N');statuses.append('UNVERIFIED');dates.append(None);snapshot_groups.append(None)
                missing+=1
                self.log('HR_VET_HIST',row,'DQ-R05','MARK','진료일보다 엄격히 이전인 유일한 스냅샷 없음; 전체 진료 유지·해당 분석 확인 필요',
                         'HORSE_MATCH_STATUS_CD',None,'UNVERIFIED',evidence=dict(VET_DT=scalar(row['VET_DT'])))
            else:
                different=row['TR_GRP_NO']!=chosen.TR_GRP_NO
                groups.append('Y' if different else 'N');statuses.append('PRIOR_NAME_SNAPSHOT_FOUND')
                dates.append(chosen.SNAPSHOT_DT);snapshot_groups.append(chosen.TR_GRP_NO)
                if different:
                    mismatch+=1
                    self.log('HR_VET_HIST',row,'DQ-S04','MARK','진료 조와 직전 이름 매칭 스냅샷 조 불일치; 진료 기록은 보정하지 않음',
                             'GRP_MISMATCH_YN','N','Y',related=chosen._DQ_ROW_ID,
                             evidence=dict(VET_TR_GRP_NO=row['TR_GRP_NO'],SNAPSHOT_TR_GRP_NO=chosen.TR_GRP_NO,SNAPSHOT_DT=scalar(chosen.SNAPSHOT_DT)))
        self.add('HR_VET_HIST','GRP_MISMATCH_YN',groups)
        self.add('HR_VET_HIST','HORSE_MATCH_STATUS_CD',statuses)
        self.add('HR_VET_HIST','PRIOR_SNAPSHOT_DT',dates,pa.date32())
        self.add('HR_VET_HIST','SNAPSHOT_TR_GRP_NO',snapshot_groups)
        self.add('HR_VET_HIST','MEDICAL_ANALYSIS_REVIEW_YN',['Y' if g=='Y' or s=='UNVERIFIED' else 'N' for g,s in zip(groups,statuses)])
        self.metrics.update(vet_group_mismatch=mismatch,vet_no_prior=missing)

    def merge_diagnosis(self):
        name='HR_VET_TYPE_BRIDGE';b=self.frames[name];v=self.frames['HR_VET_HIST']
        self.add(name,'VET_TYPE_NM_BEFORE',b.VET_TYPE_NM.tolist())
        self.add(name,'VET_TYPE_CORRECTED_YN','N')
        absorbed=[]
        affected=v.loc[v._SRC_ROW_NO.isin([595,664]) & v.VET_NM.eq('일,열사병')]
        for parent in affected.to_dict('records'):
            tokens=b.loc[b.VET_SEQ.eq(parent['VET_SEQ'])].sort_values('VET_TYPE_SEQ',kind='stable')
            if list(tokens.VET_TYPE_NM)!=['일','열사병'] or len(tokens)!=2:
                raise ValueError('D-011 input tokens differ: cannot assume the intended merge.')
            first,second=tokens.iloc[0],tokens.iloc[1]
            target='일·열사병'
            b.at[tokens.index[0],'VET_TYPE_NM']=target
            b.at[tokens.index[0],'VET_TYPE_CORRECTED_YN']='Y'
            absorbed.append(tokens.index[1])
            merge=dict(RULE_ID='DQ-S05',DECISION_ID='D-011',VET_SEQ=int(parent['VET_SEQ']),
                       _SRC_ROW_NO=int(parent['_SRC_ROW_NO']),_SRC_BRONZE_FILE=parent['_SRC_BRONZE_FILE'],
                       RAW_VET_NM=parent['VET_NM'],TARGET_VET_TYPE_NM=target,
                       TARGET_ROW_ID=first._DQ_ROW_ID,ABSORBED_ROW_ID=second._DQ_ROW_ID,
                       SOURCE_ROW_IDS=json_text(list(tokens._DQ_ROW_ID)),SOURCE_VALUES=json_text(list(tokens.VET_TYPE_NM)),
                       INPUT_ITEMS=2,OUTPUT_ITEMS=1,REDUCTION=1)
            self.merges.append(merge)
            for token in tokens.to_dict('records'):
                self.log(name,token,'DQ-S05','MERGE','D-011 의미 병합: 일,열사병을 한 유형으로 집계; 완전 중복 제외가 아님',
                         'VET_TYPE_NM',token['VET_TYPE_NM'],target,related=first._DQ_ROW_ID,evidence=merge)
        self.frames[name]=b.drop(index=absorbed).copy()
        counts=self.frames[name].groupby('VET_SEQ').size()
        self.metrics.update(vet_merge_records=len(self.merges),bridge_rows=len(self.frames[name]),multiple_vet_records=int(counts.gt(1).sum()))

    def decorate(self):
        annotations=defaultdict(list)
        for log in self.logs:
            annotations[log['_DQ_ROW_ID']].append(log)
        for name in self.frames:
            for frame in [self.frames[name],self.excluded.get(name)]:
                if frame is None:
                    continue
                values={c:[] for c in ['TABLE_NM','RULE_ID','DECISION_ID','ACTION','REASON']}
                for rowid in frame._DQ_ROW_ID:
                    rows=annotations.get(rowid,[])
                    values['TABLE_NM'].append(name)
                    values['RULE_ID'].append(';'.join(sorted({r['RULE_ID'] for r in rows})) if rows else 'DQ-R00')
                    values['DECISION_ID'].append(';'.join(sorted({d for r in rows for d in r['DECISION_ID'].split(';')})) if rows else 'D-008;D-009;D-012')
                    values['ACTION'].append(';'.join(sorted({r['ACTION'] for r in rows})) if rows else 'KEEP')
                    values['REASON'].append(' | '.join(sorted({r['REASON'] for r in rows})) if rows else '표준화 입력 행 보존')
                for column,content in values.items():
                    if column in self.original[name].column_names:
                        raise ValueError(f'QC metadata collides: {name}.{column}')
                    frame[column]=pd.Series(content,index=frame.index,dtype=pd.ArrowDtype(pa.string()))
                    self.types[name][column]=pa.string()

    def validate(self,clean,excluded):
        absorbed={m['ABSORBED_ROW_ID'] for m in self.merges}
        corrected={('BET_TICKET','HR_NM'),('HR_VET_TYPE_BRIDGE','VET_TYPE_NM')}
        for name,original in self.original.items():
            kept=self.frames[name];removed=self.excluded.get(name)
            keep_ids=set(kept._DQ_ROW_ID)
            excluded_ids=set() if removed is None else set(removed._DQ_ROW_ID)
            merged=absorbed if name=='HR_VET_TYPE_BRIDGE' else set()
            all_ids={f'{name}:{i:08d}' for i in range(1,original.num_rows+1)}
            self.check(name+' row conservation',original.num_rows,len(kept)+len(excluded_ids)+len(merged))
            self.check(name+' exclusive disposition',True,not bool(keep_ids&excluded_ids or keep_ids&merged or excluded_ids&merged))
            self.check(name+' exact row coverage',True,keep_ids|excluded_ids|merged==all_ids)
            self.check(name+' kept row ids unique',len(kept),len(keep_ids))
            for frame,packed in [(kept,clean[name])]+([] if removed is None else [(removed,excluded[name])]):
                positions=pa.array([int(v)-1 for v in frame._DQ_INPUT_ROW_NO],type=pa.int64())
                expected=original.take(positions)
                same=[c for c in original.column_names if (name,c) not in corrected or frame is removed]
                self.check(name+' unmodified original fields',True,packed.select(same).equals(expected.select(same)))
                self.check(name+' lineage present',True,not any(packed[c].null_count for c in ['_SRC_ROW_NO','_SRC_BRONZE_FILE','RULE_ID','DECISION_ID']))
        t=self.frames['BET_TICKET'];o=self.frames['BET_ORDER'];b=self.frames['HR_VET_TYPE_BRIDGE']
        original_names=self.original['BET_TICKET']['HR_NM'].to_pylist()
        name_changes=0
        valid_repairs=True
        for position,after,filled,status in zip(t._DQ_INPUT_ROW_NO,t.HR_NM,t.HR_NM_FILLED_YN,t.HR_NM_FILL_STATUS_CD):
            before=original_names[int(position)-1]
            after=scalar(after)
            if before!=after:
                name_changes+=1
                valid_repairs=valid_repairs and before is None and filled=='Y' and status=='FILLED_UNIQUE_ENTRY'
        self.check('only approved unique-entry name repairs',True,valid_repairs)
        self.check('name repair counts match actual changed values',self.metrics['filled_names'],name_changes)
        bridge_before=self.original['HR_VET_TYPE_BRIDGE']['VET_TYPE_NM'].to_pylist()
        actual_changes=[row for row in b.to_dict('records') if row['VET_TYPE_NM']!=bridge_before[int(row['_DQ_INPUT_ROW_NO'])-1]]
        self.check('only approved bridge type corrections',True,all(row['VET_TYPE_NM']=='일·열사병' and row['VET_TYPE_NM_BEFORE']=='일' and row['VET_TYPE_CORRECTED_YN']=='Y' for row in actual_changes))
        self.check('bridge correction count equals merged records',len(self.merges),len(actual_changes))
        self.check('ticket business PK after dedup',0,int(t.duplicated(['ORDER_NO','TICKET_SEQ']).sum()))
        self.check('zero tickets retained',self.metrics['zero_tickets'],int(t.INVALID_YN.eq('Y').sum()))
        self.check('business eligibility excludes exactly zero',True,bool(t.BUSINESS_AGG_ELIGIBLE_YN.eq('Y').equals(t.INVALID_YN.eq('N'))))
        self.check('late cancellations retained',self.metrics['late_tickets'],int(t.LATE_CANCEL_YN.eq('Y').sum()))
        self.check('unique late orders',self.metrics['late_orders'],int(o.LATE_CANCEL_YN.eq('Y').sum()))
        self.check('bridge input to output plus semantic reduction',self.original['HR_VET_TYPE_BRIDGE'].num_rows,len(b)+len(self.merges))
        self.check('only full duplicates in excluded',{'BET_TICKET'},set(excluded) if self.metrics['duplicate_excluded'] else {'BET_TICKET'})
        self.check('bridge parent exists',True,set(b.VET_SEQ)<=set(self.frames['HR_VET_HIST'].VET_SEQ))
        self.check('bridge parent/type unique',0,int(b.duplicated(['VET_SEQ','VET_TYPE_NM']).sum()))
        self.check('D-011 one canonical type per record',True,all(list(b.loc[b.VET_SEQ.eq(m['VET_SEQ']),'VET_TYPE_NM'])==['일·열사병'] for m in self.merges))
        self.check('medical rows retained',self.original['HR_VET_HIST'].num_rows,len(self.frames['HR_VET_HIST']))
        for log in self.logs:
            if log['RULE_ID'] not in RULES or any(d not in DECISIONS for d in log['DECISION_ID'].split(';')):
                raise ValueError('Unknown quality rule/decision ID')


def md(headers,rows):
    def escape(v):
        return str(v).replace('|','&#124;').replace('\n','<br>').replace('\r','')
    return '\n'.join(['| '+' | '.join(map(escape,headers))+' |','| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(escape,row))+' |' for row in rows])


def documentation(q,clean,excluded,report,manifest):
    m=q.metrics
    version=manifest['dataset_version']
    reconciliation=[]
    for name,source in q.original.items():
        reduction=len(q.merges) if name=='HR_VET_TYPE_BRIDGE' else 0
        reconciliation.append([name,f'{source.num_rows:,}',f'{clean[name].num_rows:,}',f'{excluded[name].num_rows:,}' if name in excluded else '0',reduction,'일치'])
    summary=defaultdict(int)
    for row in q.logs:
        summary[(row['TABLE_NM'],row['RULE_ID'],row['DECISION_ID'],row['ACTION'])]+=1
    group_rows=[[table,rule,decision,action,f'{count:,}'] for (table,rule,decision,action),count in sorted(summary.items())]
    main=f'''# Silver 품질 관리 작업 기록

[처리 변경·건수](QUALITY_CHANGES.md) · [추가 컬럼](QUALITY_COLUMNS.md) · [사용법](quality_usage.md) · [Gold 입력 계약](GOLD_INPUT_CONTRACT.md) · [결정서](../meta/decision_log.md)

## 적용 범위와 보존

| 항목 | 결과 |
| --- | --- |
| 입력 | data/02_silver/*.parquet 14개; 파일 내용·수정 시각 보존 |
| 유지 결과 | data/02_silver/clean/ 바로 아래 14개 Parquet |
| 완전 중복 제외 | data/02_silver/_excluded/BET_TICKET.parquet, {m['duplicate_excluded']:,}행 |
| 진료명 의미 병합 | 제외 폴더에 넣지 않음; 별도 병합 로그 2건과 원래 4개 토큰의 계보 보존 |
| 버전 | `{version}`; 4명은 같은 dq_manifest.json과 clean 해시를 사용 |
| 이전 작업 | 원천·Bronze·기존 Silver 및 기존 적재/표준화 코드·기록을 수정하지 않음 |
| 새 팀 규칙 중 소급하지 않은 것 | Bronze 전체 문자열/새 추적 컬럼/bronze_load_log.csv와 Silver 이슈 38,305건 기준을 기존 파일에 강제하지 않음 |
| 실행 순서 | D-001: 중복 제외 → 나머지 검사·표시/보정 → 집계별 제외 조건 |
| Gold | 아직 생성하지 않음. 입력 계약만 문서화 |

## 결정별 실제 처리

{md(['결정','문제','실측 건수','처리'],[
['D-002','마권 완전 중복',f"{m['duplicate_excluded']:,}",'업무값 비교; 최소 원천 행 번호·동률 Bronze 경로 순; 나머지 _excluded 보관'],
['D-003','0원 마권',f"{m['zero_tickets']:,}",'clean에 유지; INVALID_YN=Y, BUSINESS_AGG_ELIGIBLE_YN=N'],
['D-004','늦은 취소',f"{m['late_tickets']:,}장 / {m['late_orders']:,}전표",'마권·전표 LATE_CANCEL_YN=Y; 삭제·일괄 제외하지 않음'],
['D-004','0원이며 늦은 취소',f"{m['zero_late_tickets']:,}장 / {m['zero_late_orders']:,}전표",'전체 늦은 취소 검사에는 포함, ZERO_LATE_CANCEL_YN으로 교집합 표시'],
['D-005','빈 마명 보정',f"{m['filled_names']:,}",'출전표의 경주일·경주번호·마번이 정확히 1행 연결될 때만; HR_NM_BEFORE와 근거 보존'],
['D-006','전표·마권 불일치',f"{m['header_mismatch_orders']:,}전표",'HEADER_MISMATCH_YN=Y; 수치 보정 안 함'],
['D-006','원전표 없는 취소',f"{m['orig_missing_orders']:,}전표",'ORIG_MISSING_YN=Y; 원전표 추정 연결 안 함'],
['D-007','진료 조 불일치 / 이전 스냅샷 없음',f"{m['vet_group_mismatch']:,} / {m['vet_no_prior']:,}",'전체 진료 유지; 해당 조·스냅샷 분석에서 확인 필요'],
['D-011','일,열사병 유형 의미 병합',f"{m['vet_merge_records']:,}진료",'parent VET_NM 원문 보존; 브리지 일·열사병 단일 유형'],
['D-011','브리지 / 복수 유형 진료',f"1,664 → {m['bridge_rows']:,}행 / 176 → {m['multiple_vet_records']:,}건",'중복 제외가 아닌 의미 병합; 별도 감소 대사']])}

위 품질 건수는 모두 완전 중복을 먼저 제거한 뒤 측정했습니다. 전표 불일치 검사는 0원 마권을 포함한 전체 중복 제거 상세로 대사했습니다.
전표의 장수는 상세 행 수이며 UNIT_CNT(구좌 수)의 합이 아닙니다. 전표 늦은 취소 건수는 고유 ORDER_NO 수입니다.
늦은 취소 금액의 부호 있는 합은 **{m['late_cancel_amount']:,}원**입니다. 이 금액을 절댓값으로 바꾸거나 원천 거래 금액을 수정하지 않았습니다.

## 테이블별 행 수 대사

{md(['테이블','표준화 입력','clean 유지','_excluded 완전 중복','의미 병합 감소','결과'],reconciliation)}

- 일반 테이블: 표준화 입력 = clean + _excluded. 입력 행은 정확히 한쪽에만 있습니다.
- 진료명 브리지: **1,664 = 1,662 + 의미 병합 감소 2**. 브리지 _excluded는 0입니다.
- 브리지는 clean 행 ID와 병합 흡수 행 ID가 서로 겹치지 않으면서 원래 1,664개 입력 항목을 모두 덮는지 검사했습니다.
- 2개 병합 기록 각각에 원래 두 토큰의 행 ID·값·순번과 결과 행 ID를 남겼습니다. 원래 표준화 파일도 보존됩니다.

## 처리 로그 집계

{md(['테이블','규칙 ID','결정 ID','처리','로그 수'],group_rows)}

총 {len(q.logs):,}줄입니다. 같은 입력 행에 여러 규칙이 적용되거나 전표 플래그를 마권에 전파하면 로그가 여러 줄 생깁니다. 로그 수를 고유 전표 수나 위반 건수 합계로 해석하지 않습니다.

## 보존·측정 기준

| 구분 | 기준 |
| --- | --- |
| 완전 중복 | _로 시작하는 추적 컬럼, SRC_ 컬럼, SOURCE_FILE, INGESTED_AT을 빼고 업무값 전체 비교. TICKET_SEQ는 포함 |
| 선택 순서 | _SRC_ROW_NO 최소 → _SRC_BRONZE_FILE 오름차순 → 표준화 파일 안의 입력 순서 |
| 늦은 취소 | 전표 CANCEL + 마권 CANCEL, 취소 SALE_DTM >= 해당 마권 RC_RACE.START_DTM |
| 빈 마명 | NULL만 대상. 유일한 출전표 연결이 아니면 추측 보정하지 않고 원래 값을 유지 |
| 원전표 없음 | 취소 ORIG_ORDER_NO가 유효한 SALE 전표에 연결되지 않음; NULL 포함 |
| 진료 비교 | 동일 마명의 진료일보다 엄격히 이전인 최신 스냅샷. 동일 날짜도 제외 |
| 말 개체 | 이름 기반 과거 스냅샷 후보 매칭이며 공식 말 ID 확정이 아님. Gold에서 개체 검증 별도 필요 |
| 예전 이슈 로그 | 기존 silver_issue_log.csv는 보존. QC 건수는 dq_log.csv로 분리 |
| 재실행 | 같은 내용은 수정하지 않음. 기존 clean/_excluded와 다른 결과는 덮어쓰지 않고 별도 버전 경로 요구 |

## 검증 결과

{md(['검증','기대','실제','결과'],[[c['check'],c['expected'],c['actual'],'통과' if c['passed'] else '실패'] for c in q.checks])}

## 변경 이력

| 일자 (KST) | 작업 |
| --- | --- |
| 2026-11-20 | D-001~D-012 적용. 기존 Bronze/Silver 보존, 품질 clean·중복 제외·진료명 의미 병합 계보와 대사 구현 |
'''
    aggregates=defaultdict(int)
    for log in q.logs:
        aggregates[(log['TABLE_NM'],log['COLUMN_NM'] or '(업무값 전체)',log['RULE_ID'],log['DECISION_ID'],log['ACTION'],log['OLD_VALUE'],log['NEW_VALUE'])]+=1
    samples=defaultdict(list)
    for key,count in aggregates.items():
        samples[key[:5]].append((key[5],key[6],count))
    rows=[]
    for key,entries in sorted(samples.items()):
        table,column,rule,decision,action=key
        examples='<br>'.join(f'`{old}` → `{new}` ({count:,})' for old,new,count in sorted(entries,key=lambda x:(-x[2],x[0],x[1]))[:5])
        if len(entries)>5:
            examples+=f'<br>그 외 {len(entries)-5:,}개 값은 dq_value_changes.csv에 전체 기록'
        rows.append([table,column,column if action!='EXCLUDE' else '_excluded',action+'<br>'+examples,f'{sum(e[2] for e in entries):,}',rule,decision])
    change_doc='''# 품질 관리 변경 내역과 건수

[작업 기록](QUALITY.md) · [추가 컬럼](QUALITY_COLUMNS.md) · [결정서](../meta/decision_log.md)

행 제외·표시·보정·의미 병합을 구분한 실제 집계입니다. 같은 행은 여러 규칙에 포함될 수 있습니다.
마명별 보정 등 값이 많은 항목은 대표 5개와 전체 건수를 표시하며 [dq_value_changes.csv](../meta/dq_value_changes.csv)에 모든 값별 건수를 기록합니다.
OLD/NEW가 null인 EXCLUDE는 값 삭제가 아니라 원래 행 전체의 별도 보관입니다. MERGE는 완전 중복 제외가 아닌 D-011 의미 병합입니다.

'''+md(['테이블','원천컬럼','처리 후 컬럼/위치','바꾼내용·값별 건수','총 처리 건수','규칙 ID','결정 ID'],rows)+'\n'
    column_doc='''# 품질 관리 추가 컬럼

[작업 기록](QUALITY.md) · [변경 내역](QUALITY_CHANGES.md) · [Gold 입력](GOLD_INPUT_CONTRACT.md)

기존 컬럼 타입은 유지했습니다. 수정 허용한 원천 업무 컬럼은 마권 HR_NM과 브리지 VET_TYPE_NM뿐이며 원래 값은 별도 컬럼과 로그에 보존합니다.
표준화 결과 파일 자체는 수정하지 않았습니다.

'''
    meanings={
      '_DQ_INPUT_ROW_NO':'표준화 입력 파일 내부 1부터 시작하는 행 번호', '_DQ_ROW_ID':'테이블명+표준화 입력 행 번호; 병합 전 항목을 구분',
      '_DQ_DATASET_VERSION':'공통 clean 버전; 입력/결정/실제 결과 내용 기반',
      'TABLE_NM':'해당 테이블명','RULE_ID':'적용 규칙 ID 목록; 미위반 보존은 DQ-R00',
      'DECISION_ID':'근거 결정 ID 목록','ACTION':'KEEP / MARK / CORRECT / EXCLUDE / MERGE; 복수 적용 가능',
      'REASON':'처리 또는 보존 근거', 'INVALID_YN':'0원 마권이면 Y; 오류 집계에는 포함',
      'BUSINESS_AGG_ELIGIBLE_YN':'0원 기준 업무 집계 사용 가능 여부; Gold의 50대·단승 등 적격 조건과는 별개',
      'LATE_CANCEL_YN':'마권은 출발 이상 시각의 취소, 전표는 하나라도 해당하면 Y',
      'ZERO_LATE_CANCEL_YN':'0원이며 늦은 취소인 교집합; 전표는 하나라도 해당하면 Y',
      'HR_NM_BEFORE':'보정 전 마명; 원래 NULL도 보존','HR_NM_FILLED_YN':'출전표 유일 연결로 보정한 경우 Y',
      'HR_NM_FILL_STATUS_CD':'NOT_NEEDED / FILLED_UNIQUE_ENTRY / NO_MATCH / AMBIGUOUS / ENTRY_NAME_MISSING',
      'HEADER_MISMATCH_YN':'전표 장수/금액과 중복 제거 상세가 다름; 마권은 전표 플래그 상속',
      'ORIG_MISSING_YN':'취소가 유효 원구매 SALE 전표에 연결되지 않음; 마권은 전표 플래그 상속',
      'GRP_MISMATCH_YN':'진료 조와 직전 과거 스냅샷 조가 다름; 진료 조는 유지',
      'HORSE_MATCH_STATUS_CD':'PRIOR_NAME_SNAPSHOT_FOUND / UNVERIFIED; 공식 말 ID 검증을 뜻하지 않음',
      'PRIOR_SNAPSHOT_DT':'진료일보다 엄격히 이전인 채택 스냅샷 날짜',
      'SNAPSHOT_TR_GRP_NO':'비교에 사용한 과거 스냅샷 조 번호','MEDICAL_ANALYSIS_REVIEW_YN':'조/스냅샷별 분석 확인 필요. 전체 진료 집계에는 포함',
      'VET_TYPE_NM_BEFORE':'의미 병합 전 진료명 토큰','VET_TYPE_CORRECTED_YN':'일·열사병 단일 유형으로 보정한 결과 행 Y',
    }
    dictionary=[]
    for name,table in clean.items():
        rows=[]
        for field in table.schema:
            if field.name in q.original[name].column_names:
                continue
            values=table[field.name]
            counts=values.value_counts().to_pylist() if field.name.endswith('_YN') or field.name.endswith('_CD') else []
            note=json_text(counts) if counts else ''
            row=dict(TABLE_NM=name,COLUMN_NM=field.name,TYPE=str(field.type),DESCRIPTION=meanings[field.name],NULL_ROWS=values.null_count,COUNTS=note)
            dictionary.append(row)
            rows.append([field.name,field.type,meanings[field.name],values.null_count,note])
        column_doc+=f'## {name}\n\n'+md(['추가 컬럼','타입','의미','NULL 수','상태별 건수'],rows)+'\n\n'
    usage='''# 품질 관리 실행 사용법

[작업 기록](QUALITY.md) · [변경 건수](QUALITY_CHANGES.md) · [Gold 입력 계약](GOLD_INPUT_CONTRACT.md)

## 실행

프로젝트 루트에서 실행합니다. 기존 Bronze/Silver 코드와 입력 파일을 다시 생성하지 않습니다.

```powershell
.\\.venv\\Scripts\\python.exe src/02_quality.py --check-reference
.\\.venv\\Scripts\\python.exe src/02_quality_check.py
```

| 옵션 | 기본값 / 의미 |
| --- | --- |
| --input-root | data/02_silver; 바로 아래 표준화 Parquet 14개만 읽음 |
| --clean-root | data/02_silver/clean; 새 결과 14개 |
| --excluded-root | data/02_silver/_excluded; 완전 중복 제외만 저장 |
| --meta-root | meta; dq_* 로그·검증·manifest와 병합 로그 |
| --docs-root | docs; 품질 관리 결과·컬럼·변경·Gold 계약 |
| --check-reference | 현재 팀 데이터셋의 확정 건수와 비교; 일반 입력에서는 생략 가능 |

기존 clean/_excluded 파일과 결과가 다르면 덮어쓰지 않고 중단합니다. 새 규칙/새 입력은 명시적으로 별도 버전 출력 폴더와 meta/docs 경로를 지정해 검토합니다.
같은 결과는 바이트와 수정 시각을 유지합니다. 실행 시각을 데이터에 넣지 않습니다.
검증을 모두 통과한 결과를 임시 폴더에 저장하고 Parquet 왕복 비교 및 입력 해시·수정 시각을 확인한 뒤 게시합니다.

## 진료명 브리지

| 항목 | 보관·대사 |
| --- | --- |
| 표준화 1,664개 항목 | 기존 HR_VET_TYPE_BRIDGE.parquet에 그대로 보존 |
| 품질 처리 후 1,662개 항목 | clean/HR_VET_TYPE_BRIDGE.parquet |
| 2개 진료별 의미 병합 | meta/vet_type_merge_log.csv; 두 원래 항목 ID·값과 결과 ID 기록 |
| 대사 | 1,664 = 1,662 + 의미 병합 감소 2; _excluded에는 넣지 않음 |

## 검증 범위

새 02_quality_check.py는 표준화 파일 해시와 품질 결과를 함께 읽기만 하여 검사합니다.
기존 표준화 검증기의 하위 폴더 금지 조건은 바꾸지 않았으므로 품질 단계 후에는 이 전용 검증기를 사용합니다.
원래 Silver의 이슈 38,305건 기준이나 새 Bronze 추적 컬럼을 이번 작업에서 소급 적용하지 않습니다.

## 오류

| 상황 | 처리 |
| --- | --- |
| 입력이 14개 공용 테이블과 다름 | 중단; 표준화 입력 버전 확인 |
| 전표/경주 키가 중복되거나 시각 참조 누락 | 늦은 취소를 추정하지 않고 중단 |
| 마명 보정의 출전표 연결이 0개/복수 | 원래 빈값 유지, 근거 없는 보정 금지; 로그 기록 |
| 같은 마명·날짜 스냅샷이 여러 개 | 의료 매칭 미확인으로 보존; 임의 한 행 선택 금지 |
| 기존 품질 결과와 다름 | 덮어쓰지 않음; 별도 버전 경로 사용 |
| 결과 파일 잠김 | 해당 미리보기 핸들을 닫고 재실행 |
'''
    gold=f'''# Gold 입력 계약과 목표 스타 스키마

[품질 관리](QUALITY.md) · [품질 컬럼](QUALITY_COLUMNS.md) · [공통 결정](../meta/decision_log.md)

## 입력 버전

Gold는 **data/02_silver/clean/**만 입력으로 사용합니다. 현재 버전은 `{version}`이며 [dq_manifest.json](../meta/dq_manifest.json)의 clean 파일 SHA-256과 일치해야 합니다.
4명 모두 같은 manifest와 clean 버전을 사용합니다. 기존 표준화 결과를 직접 읽거나 이전 설계의 원천 CSV를 다시 읽어 우회하지 않습니다.

## 사용자 제공 설계의 채택 범위

| 항목 | 목표 |
| --- | --- |
| 분석 질문 | 원구매 당시 만 50~59세 회원이 선택한 말의 구매 전 최근 1년 승률과 단승 고객 취소율의 관계 |
| 팩트 | fct_bet_selection_cancel_50s |
| 한 행 (그레인) | 원구매 전표 × 경주일 × 경주번호 × 단승 × 선택 출주번호의 구매 선택 묶음 |
| 업무키 | 원구매 ORDER_NO + RC_DT + RC_NO + BET_TYPE_CD(WIN) + CHUL_NO |
| 공통 차원 | 회원, 말, 경주, 날짜(역할별 참조), 채널; 업무키/타입/코드를 팀과 먼저 합의 |
| 나이 | 원구매일 기준 생일을 반영한 만 나이; 회원 현재 나이로 대체하지 않음 |
| 승률 | 구매일보다 엄격히 이전인 최신 말 스냅샷의 Y1_1ST_CNT / Y1_RC_CNT; 분모 0은 0%와 구분 |
| 취소 연결 | 원전표번호만으로 확정하지 않고 회원·경주·승식·선택·금액/수량 검증; 취소 순번을 원구매 순번으로 가정하지 않음 |
| 이번 작업 | 품질 관리와 Gold 입력 계약까지만 완료; Gold 파일·차원·팩트는 아직 미생성 |

## 최신 팀 결정이 우선하는 부분

| 대상 | 적용 계약 |
| --- | --- |
| 0원 | INVALID_YN=Y는 업무 집계의 분자·분모 양쪽에서 제외. 오류 건수 집계에는 포함 |
| 늦은 취소 | 최신 D-004에 따라 유지·취소 분석 포함. 과거 설계 예시의 취소<출발 제한을 공통 제외 조건으로 복사하지 않음 |
| 0원 늦은 취소 | 전체 늦은 취소 품질 건수에는 포함. 업무 지표에서는 D-003에 따라 제외; 현재 교집합 0건 |
| 일부 마권만 늦은 전표 | 전표 Y를 이유로 전표 전체 상세를 늦은 취소로 간주하지 않음. 마권 플래그로 집계 |
| 전표 불일치 | HEADER_MISMATCH_YN만으로 임의 삭제/수치 수정 금지; 팩트 금액 기준은 담당자가 정의 |
| 원전표 없음 | 미연결 취소를 임의 원구매에 배정하거나 확인 취소 0으로 단정하지 않음 |
| 진료 문제 | 전체 진료 수 포함, 조·스냅샷 분석에서는 확인 필요; 유형 분석은 D-011 적용한 브리지 사용 |
| 예시 숫자 | 제공 폴더의 41,149행·적격 39,263행·취소 875개는 이전 규칙의 예시 결과이며 새 Gold 기대값으로 강제하지 않음 |

## Gold에서 별도 확정·검증할 것

| 대상 | 검증 |
| --- | --- |
| 공통 차원 | 업무키·컬럼 타입·코드 매핑 합의, PK 유일성 |
| 팩트 FK | 모든 차원 키 존재; 공통 키 변경 시 FK 재연결 |
| 사건 시점 | 구매 전 전적만 사용; 미래 성적 유입 금지 |
| 집계 단위 | 구매 선택 묶음 / 마권 상세 / 고유 전표 / 구좌 수를 구분 |
| 금액·취소율 | 실제 참여 행·건수·금액 대사; 단순 비율 평균 금지 |
| 분석 제외 | 팩트별 제외 사유와 원천 행 계보 기록; 공통 clean 데이터 자체는 변경하지 않음 |

첨부 설계는 참고 자료이며 그 폴더의 생성 코드를 실행하거나 기존 분석 CSV를 이번 품질 결과로 복사하지 않았습니다.
'''
    decision='# 공통 품질 관리 결정 기록\n\n사용자가 확정한 D-001~D-012를 기록합니다. 일자: 2026-11-20 (KST).\n\n'+md(['결정 ID','확정 내용'],sorted(DECISIONS.items()))
    decision+='\n\n## 이번 실행의 적용 경계\n\n기존 Bronze·Silver 파일/적재·표준화 코드는 소급 수정하지 않습니다. 현재는 존재하지 않던 clean·_excluded를 새로 만들며, 이후 동일 결과만 재사용하고 다른 결과로 덮어쓰지 않습니다.\n브리지 의미 병합은 완전 중복 제외와 구분하며 입력 항목 = 유지 항목 + 의미 병합 감소로 별도 대사합니다.\n'
    return {'QUALITY.md':main,'QUALITY_CHANGES.md':change_doc,'QUALITY_COLUMNS.md':column_doc,'quality_usage.md':usage,'GOLD_INPUT_CONTRACT.md':gold},decision,dictionary,aggregates


def csv_write(path,rows,columns=None):
    pd.DataFrame(rows,columns=columns).to_csv(path,index=False,encoding='utf-8-sig',lineterminator='\n')


def run(input_root=ROOT/'data/02_silver',clean_root=None,excluded_root=None,meta_root=ROOT/'meta',docs_root=ROOT/'docs',reference=False):
    input_root=Path(input_root).resolve()
    clean_root=Path(clean_root).resolve() if clean_root else input_root/'clean'
    excluded_root=Path(excluded_root).resolve() if excluded_root else input_root/'_excluded'
    meta_root=Path(meta_root).resolve();docs_root=Path(docs_root).resolve()
    if len({input_root,clean_root,excluded_root,meta_root,docs_root})!=5:
        raise ValueError('All input/output/meta/docs folders must differ.')
    for output in [clean_root,excluded_root,meta_root,docs_root]:
        if output in input_root.parents:
            raise ValueError('Output may not contain the standardized input folder.')
    for a in [clean_root,excluded_root,meta_root,docs_root]:
        for b in [clean_root,excluded_root,meta_root,docs_root]:
            if a!=b and (a in b.parents or b in a.parents):
                raise ValueError('Output/meta/docs folders may not overlap.')
    if input_root in meta_root.parents or input_root in docs_root.parents:
        raise ValueError('meta/docs must be outside standardized input.')
    paths={p.stem:p for p in input_root.glob('*.parquet')}
    if set(paths)!=set(TABLES):
        raise ValueError(f'Expected 14 standard tables, got {sorted(paths)}')
    snapshot={name:dict(path=str(paths[name]),sha256=sha(paths[name]),mtime_ns=paths[name].stat().st_mtime_ns) for name in TABLES}
    original={name:pq.read_table(paths[name]) for name in TABLES}
    q=Quality(original)
    clean,excluded=q.run()
    if reference:
        for key,expected in REFERENCE.items():
            q.check('reference '+key,expected,q.metrics[key])
    failures=[c for c in q.checks if not c['passed']]
    if failures:
        raise RuntimeError('Quality validation failed before saving: '+json_text(failures))
    meta_root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.quality-stage-',dir=meta_root.parent) as temporary:
        stage=Path(temporary)
        payload={}
        for name,table in clean.items():
            path=stage/(name+'.unversioned.parquet')
            pq.write_table(table,path,compression='snappy')
            payload[name]=sha(path)
        version='DQ-'+hashlib.sha256(json_text(dict(inputs={n:x['sha256'] for n,x in snapshot.items()},decisions=DECISIONS,rules=RULES,clean_content=payload)).encode('utf-8')).hexdigest()[:20]
        for container in [clean,excluded]:
            for name,table in list(container.items()):
                container[name]=table.append_column('_DQ_DATASET_VERSION',pa.array([version]*table.num_rows,type=pa.string()))
        output_manifest={}
        publications=[]
        for category,container,directory in [('clean',clean,clean_root),('_excluded',excluded,excluded_root)]:
            existing={p.stem for p in directory.glob('*.parquet')} if directory.exists() else set()
            if existing-set(container):
                raise ValueError(f'Unexpected existing quality files: {directory}: {existing-set(container)}')
            for name,table in container.items():
                path=stage/f'{category}-{name}.parquet'
                pq.write_table(table,path,compression='snappy')
                if not pq.read_table(path).equals(table):
                    raise RuntimeError(f'Parquet roundtrip mismatch: {category}/{name}')
                destination=directory/(name+'.parquet')
                if destination.exists() and sha(destination)!=sha(path):
                    raise RuntimeError(f'Existing quality data is immutable; choose a new output version: {destination}')
                publications.append((path,destination))
                output_manifest[f'{category}/{name}']=dict(path=str(destination),rows=table.num_rows,columns=table.column_names,sha256=sha(path))
        for name,info in snapshot.items():
            q.check(name+' source hash preserved',info['sha256'],sha(info['path']))
            q.check(name+' source mtime preserved',info['mtime_ns'],Path(info['path']).stat().st_mtime_ns)
        if not all(c['passed'] for c in q.checks):
            raise RuntimeError('Source changed while processing; nothing saved.')
        manifest=dict(dataset_version=version,code_sha256=sha(__file__),decisions=DECISIONS,rules=RULES,
                      sources=snapshot,outputs=output_manifest,gold_input=str(clean_root),excluded_input=str(excluded_root))
        report=dict(status='passed',dataset_version=version,metrics=q.metrics,checks=q.checks,
                    input_rows=sum(t.num_rows for t in original.values()),clean_rows=sum(t.num_rows for t in clean.values()),
                    excluded_rows=sum(t.num_rows for t in excluded.values()),semantic_merge_reduction=len(q.merges),log_rows=len(q.logs))
        docs,decision_doc,dictionary,changes=documentation(q,clean,excluded,report,manifest)
        csv_write(stage/'dq_log.csv',q.logs,LOG_FIELDS)
        csv_write(stage/'dq_rules.csv',[dict(RULE_ID=k,DECISION_ID=v[0],DESCRIPTION=v[1]) for k,v in sorted(RULES.items())])
        summary=defaultdict(int)
        for log in q.logs:
            summary[(log['TABLE_NM'],log['RULE_ID'],log['DECISION_ID'],log['ACTION'])]+=1
        csv_write(stage/'dq_summary.csv',[dict(TABLE_NM=k[0],RULE_ID=k[1],DECISION_ID=k[2],ACTION=k[3],LOG_ROWS=v) for k,v in sorted(summary.items())])
        csv_write(stage/'dq_value_changes.csv',[dict(TABLE_NM=k[0],COLUMN_NM=k[1],RULE_ID=k[2],DECISION_ID=k[3],ACTION=k[4],OLD_VALUE=k[5],NEW_VALUE=k[6],COUNT=v) for k,v in sorted(changes.items())])
        csv_write(stage/'vet_type_merge_log.csv',q.merges,['RULE_ID','DECISION_ID','VET_SEQ','_SRC_ROW_NO','_SRC_BRONZE_FILE','RAW_VET_NM','TARGET_VET_TYPE_NM','TARGET_ROW_ID','ABSORBED_ROW_ID','SOURCE_ROW_IDS','SOURCE_VALUES','INPUT_ITEMS','OUTPUT_ITEMS','REDUCTION'])
        csv_write(stage/'dq_column_dictionary.csv',dictionary)
        for name,value in [('dq_manifest.json',manifest),('dq_validation.json',report)]:
            (stage/name).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        (stage/'decision_log.md').write_text(decision_doc.rstrip()+'\n',encoding='utf-8')
        for name,text in docs.items():
            path=stage/name
            path.write_text(text.rstrip()+'\n',encoding='utf-8')
            publications.append((path,docs_root/name))
        publications.extend((stage/name,meta_root/name) for name in ['dq_log.csv','dq_rules.csv','dq_summary.csv','dq_value_changes.csv','vet_type_merge_log.csv','dq_column_dictionary.csv','dq_manifest.json','dq_validation.json','decision_log.md'])
        # No previous-stage files are publication targets. Existing QC data was checked above.
        for source,destination in publications:
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and sha(source)==sha(destination):
                status='unchanged'
            else:
                source.replace(destination)
                status='written'
            print(f'{status}: {destination}',flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,default=ROOT/'data/02_silver')
    parser.add_argument('--clean-root',type=Path)
    parser.add_argument('--excluded-root',type=Path)
    parser.add_argument('--meta-root',type=Path,default=ROOT/'meta')
    parser.add_argument('--docs-root',type=Path,default=ROOT/'docs')
    parser.add_argument('--check-reference',action='store_true')
    args=parser.parse_args()
    result=run(args.input_root,args.clean_root,args.excluded_root,args.meta_root,args.docs_root,args.check_reference)
    print(f"Passed {len(result['checks'])} checks; clean {result['clean_rows']:,}, duplicate excluded {result['excluded_rows']:,}, semantic merge reduction {result['semantic_merge_reduction']}.")


if __name__=='__main__':
    main()
