"""Deterministic Gold star schema from approved clean Silver; no upstream writes."""
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import timedelta
import hashlib
import json

import pyarrow as pa

FACT = 'fct_bet_selection_cancel_50s'
SOURCES = ('BET_ORDER', 'BET_TICKET', 'MBR_MASTER', 'HR_WEEKLY_SNAPSHOT', 'RC_RACE', 'RC_ENTRY', 'RC_RESULT')
UNKNOWN = 'UNKNOWN'
RULE_VERSION = 'GOLD-50WIN-1'
GOLD_DECISIONS = {
    'G-001': 'Original-purchase-date age 50..59; WIN selection groups; zero details outside both business aggregates',
    'G-002': 'Detailed amounts/units, amount=units*unit_amount; header mismatch is informational',
    'G-003': 'Original order/member/selection/time/sign validation; late cancel allowed; no ticket-seq link',
    'G-004': 'Unresolved same-member earlier selection candidates remain ambiguous; cumulative excess invalid',
    'G-005': 'Unique horse identity and strictly prior-date snapshot; no future performance',
    'G-006': 'Purchase before start; RAN result; observation end max order time; ineligible facts retained',
    'G-007': 'Namespaced deterministic surrogate keys; provisional common dimensions; all input detail dispositions',
}
TYPES = {'s': pa.string(), 'i': pa.int64(), 'd': pa.date32(), 'n': pa.int32(),
         'f': pa.float64(), 't': pa.timestamp('ms', tz='Asia/Seoul')}
DEFINITIONS = {
    'dim_member': 'member_key:s member_no:s birth_date:d join_date:d source_row_id:s',
    'dim_horse': 'horse_key:s horse_name:s birth_date:d sire_name:s dam_name:s identity_status:s',
    'dim_race': 'race_id:s race_date:d race_no:n meet_cd:s race_start_at:t distance_m:n race_grade:s source_row_id:s',
    'dim_date': 'date_key:n calendar_date:d year:n quarter:n month:n day_of_month:n weekday:n year_month:s',
    'dim_channel': 'channel_key:s channel_cd:s channel_group:s branch_no:s channel_name:s',
    FACT: '''fact_id:s original_order_no:s member_key:s horse_key:s race_id:s channel_key:s
        purchase_date_key:n cancel_date_key:n race_date_key:n snapshot_date_key:n bet_type_cd:s chul_no:n
        age_at_purchase:n purchase_at:t horse_age_at_race:n horse_sex_at_race:s
        purchase_detail_count:i purchase_stake_units:i purchase_amount_krw:i
        horse_snapshot_date:d snapshot_age_days:n recent1y_starts:i recent1y_wins:i recent1y_win_rate:f
        recent1y_win_rate_band:s career_starts:i career_wins:i career_win_rate:f
        has_verified_customer_cancel:n cancel_label_status:s cancel_transaction_count:i
        raw_linked_cancel_amount_krw:i verified_cancel_amount_krw:i verified_cancel_stake_units:i
        first_cancel_at:t cancel_delay_seconds:i late_cancel_detail_count:i unresolved_cancel_order_count:i
        header_detail_mismatch:n observation_end_at:t analysis_eligible:n exclusion_reasons:s
        purchase_order_row_id:s entry_row_id:s snapshot_row_id:s dq_dataset_version:s rule_version:s''',
    'ticket_disposition': '''source_row_id:s source_bronze_file:s source_row_no:i order_no:s ticket_seq:n
        bet_amt:i unit_cnt:i disposition:s reason:s fact_id:s rule_id:s decision_id:s''',
    'cancel_link_audit': '''source_row_id:s source_bronze_file:s source_row_no:i cancel_order_no:s
        reference_order_no:s member_no:s race_date:d race_no:n chul_no:n cancel_at:t cancel_amount_krw:i
        cancel_stake_units:i matched_target_fact_id:s plausible_target_group_count:i link_status:s
        reasons:s late_cancel_yn:s rule_id:s decision_id:s''',
    'fact_analysis_exclusions': 'fact_id:s exclusion_reasons:s rule_id:s decision_id:s',
    'win_rate_cancel_summary': '''summary_id:s scope:s win_rate_band:s purchase_selection_groups:i cancelled_groups:i
        observed_cancel_rate:f purchase_amount_krw:i cancel_amount_krw:i amount_cancel_rate:f
        unique_members:i unique_horses:i unique_races:i''',
}
PKS = {n: n.removeprefix('dim_') + '_key' for n in ['dim_member', 'dim_horse', 'dim_channel']}
PKS.update(dim_race='race_id', dim_date='date_key', **{FACT: 'fact_id'}, ticket_disposition='source_row_id',
           cancel_link_audit='source_row_id', fact_analysis_exclusions='fact_id', win_rate_cancel_summary='summary_id')


def stable_key(namespace, values):
    text = json.dumps([namespace, *values], ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]


def age_at(birth, day):
    return None if birth is None or day is None else day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def date_key(day):
    return int(day.strftime('%Y%m%d')) if day else 0


def selection(row):
    return row['RC_DT'], row['RC_NO'], row['CHUL_NO']


def unique_index(rows, fields, name):
    result = {}
    for row in rows:
        key = tuple(row[f] for f in fields)
        if any(x is None for x in key) or key in result:
            raise ValueError(f'{name}: null/duplicate lookup key {key}')
        result[key] = row
    return result


def channel(order):
    group = order.get('CHNL_CD') or UNKNOWN
    branch = order.get('OTB_BRANCH_NO') if group == 'OTB' else None
    code = group + branch if branch else group
    key = UNKNOWN if group == UNKNOWN else stable_key('channel', [group, branch])
    return dict(channel_key=key, channel_cd=code, channel_group=group, branch_no=branch,
                channel_name={'ONSITE': '현장', 'APP': '앱', 'OTB': '장외', UNKNOWN: '미상'}.get(group, group))


def packed(name, rows):
    schema = pa.schema([(x.split(':')[0], TYPES[x.split(':')[1]]) for x in DEFINITIONS[name].split()])
    return pa.Table.from_pylist(rows, schema=schema)


def band(rate):
    if rate is None: return 'UNKNOWN'
    if rate == 0: return '0%'
    if rate <= .05: return '(0,5%]'
    if rate <= .10: return '(5,10%]'
    if rate <= .20: return '(10,20%]'
    return '>20%'


def build(tables, unit_amount=100):
    if not isinstance(unit_amount, int) or unit_amount <= 0:
        raise ValueError('unit_amount must be a positive integer')
    data = {name: tables[name].to_pylist() if isinstance(tables[name], pa.Table) else tables[name] for name in SOURCES}
    for name, rows in data.items():
        if any(not r.get('_DQ_ROW_ID') or not r.get('_SRC_BRONZE_FILE') or r.get('_SRC_ROW_NO') is None for r in rows):
            raise ValueError(f'{name}: clean lineage required')
    orders = {k[0]: v for k, v in unique_index(data['BET_ORDER'], ['ORDER_NO'], 'BET_ORDER').items()}
    members = {k[0]: v for k, v in unique_index(data['MBR_MASTER'], ['MBR_NO'], 'MBR_MASTER').items()}
    races = unique_index(data['RC_RACE'], ['RC_DT', 'RC_NO'], 'RC_RACE')
    entries = unique_index(data['RC_ENTRY'], ['RC_DT', 'RC_NO', 'CHUL_NO'], 'RC_ENTRY')
    results = unique_index(data['RC_RESULT'], ['RC_DT', 'RC_NO', 'CHUL_NO'], 'RC_RESULT')
    unique_index(data['BET_TICKET'], ['ORDER_NO', 'TICKET_SEQ'], 'BET_TICKET')
    if not orders or not any(r['SALE_DTM'] for r in orders.values()):
        raise ValueError('At least one valid order time is required')
    for o in orders.values():
        time = o.get('SALE_DTM')
        if time is not None and (time.tzinfo is None or time.utcoffset() != timedelta(hours=9)):
            raise ValueError('Order times must be timezone-aware KST')
    cutoff = max(o['SALE_DTM'] for o in orders.values() if o['SALE_DTM'])
    versions = {r.get('_DQ_DATASET_VERSION') for rows in data.values() for r in rows}
    if None in versions or len(versions) != 1:
        raise ValueError('All clean inputs must have one common dataset version')
    version = next(iter(versions))
    history = defaultdict(list)
    for row in data['HR_WEEKLY_SNAPSHOT']: history[row['HR_NM']].append(row)
    identities = {}
    histories = {}
    for name, rows in history.items():
        births = {r['HR_BIRTH_DT'] for r in rows}
        sires = {r.get('SIRE_NM') for r in rows if r.get('SIRE_NM')}
        dams = {r.get('DAM_NM') for r in rows if r.get('DAM_NM')}
        if name and len(births) == 1 and None not in births and len(sires) <= 1 and len(dams) <= 1:
            birth = next(iter(births))
            identities[name] = dict(horse_key=stable_key('horse', [name, birth]), horse_name=name,
                                    birth_date=birth, sire_name=next(iter(sires), None), dam_name=next(iter(dams), None),
                                    identity_status='INTERNAL_NAME_BIRTH_CONSISTENT')
        by_date = defaultdict(list)
        for r in rows: by_date[r['SNAPSHOT_DT']].append(r)
        histories[name] = (sorted(d for d in by_date if d is not None), by_date)
    dim_members = [dict(member_key=UNKNOWN, member_no=None, birth_date=None, join_date=None, source_row_id=None)]
    member_keys = {}
    for no, m in sorted(members.items()):
        key = stable_key('member', [no]); member_keys[no] = key
        dim_members.append(dict(member_key=key, member_no=no, birth_date=m['BIRTH_DT'], join_date=m.get('JOIN_DT'), source_row_id=m['_DQ_ROW_ID']))
    dim_races = [dict(race_id=UNKNOWN)]
    race_keys = {}
    for rk, r in sorted(races.items()):
        rid = stable_key('race', [r['MEET_CD'], *rk]); race_keys[rk] = rid
        dim_races.append(dict(race_id=rid, race_date=rk[0], race_no=rk[1], meet_cd=r['MEET_CD'],
                              race_start_at=r['START_DTM'], distance_m=r.get('RC_DIST_M'), race_grade=r.get('RC_GRADE_CD'), source_row_id=r['_DQ_ROW_ID']))
    groups = {}
    dispositions = []
    cancellations = []
    target_detail_amount = target_detail_units = target_detail_count = 0
    for t in sorted(data['BET_TICKET'], key=lambda x: x['_DQ_ROW_ID']):
        o = orders.get(t['ORDER_NO']); reason = ''; disposition = 'OUT_OF_SCOPE'; fid = None
        zero = t['BET_AMT'] == 0
        if (t.get('INVALID_YN') == 'Y') != zero:
            raise ValueError('INVALID_YN differs from zero amount')
        if o is None: reason = 'ORDER_NOT_FOUND'
        elif t['BET_TYPE_CD'] != 'WIN': reason = 'NON_WIN'
        elif o['ORDER_TYPE_CD'] == 'CANCEL':
            cancellations.append((o, t)); disposition = 'CANCEL_AUDIT'; reason = 'ZERO_AMOUNT' if zero else 'WIN_CANCEL'
        elif zero: reason = 'ZERO_AMOUNT'
        elif o['ORDER_TYPE_CD'] != 'SALE': reason = 'NON_SALE'
        else:
            m = members.get(o['MBR_NO']); when = o.get('SALE_DTM')
            age = age_at(m['BIRTH_DT'] if m else None, when.date() if when else None)
            if age is None: reason = 'AGE_UNKNOWN'
            elif not 50 <= age <= 59: reason = 'OUTSIDE_50S'
            else:
                key = (t['ORDER_NO'], *selection(t))
                fid = stable_key('selection', [key[0], key[1], key[2], 'WIN', key[3]])
                if key not in groups:
                    groups[key] = dict(fid=fid, order=o, age=age, details=[], bad=set(),
                                       cancel_raw=0, cancel_amount=0, cancel_units=0, cancel_ids=set(), cancel_times=[],
                                       unresolved=set(), late_count=0, cancel_uncertain=False)
                g = groups[key]; g['details'].append(t)
                if t['BET_AMT'] <= 0 or t['UNIT_CNT'] <= 0 or t['BET_AMT'] != t['UNIT_CNT'] * unit_amount:
                    g['bad'].add('BAD_PURCHASE_AMOUNT')
                if t['TICKET_STAT_CD'] not in ('SOLD', 'VOID'): g['bad'].add('INVALID_PURCHASE_STATUS')
                if t['TICKET_STAT_CD'] == 'VOID': g['bad'].add('VOID_OR_NONSTART_STATUS')
                if t.get('CHUL_NO2') is not None or t.get('HR_NM2'): g['bad'].add('WIN_SECOND_SELECTION')
                e = entries.get(selection(t))
                if e and t.get('HR_NM') and t['HR_NM'] != e['HR_NM']: g['bad'].add('HORSE_NAME_CONFLICT')
                disposition = 'FACT_PURCHASE'; reason = 'GROUPED'
                target_detail_amount += t['BET_AMT']; target_detail_units += t['UNIT_CNT']; target_detail_count += 1
        dispositions.append(dict(source_row_id=t['_DQ_ROW_ID'], source_bronze_file=t['_SRC_BRONZE_FILE'],
                                 source_row_no=t['_SRC_ROW_NO'], order_no=t['ORDER_NO'], ticket_seq=t['TICKET_SEQ'],
                                 bet_amt=t['BET_AMT'], unit_cnt=t['UNIT_CNT'], disposition=disposition,
                                 reason=reason, fact_id=fid, rule_id='GOLD-SCOPE', decision_id='G-001;G-007;D-003;D-009;D-012'))
    candidates = defaultdict(list)
    for key, g in groups.items(): candidates[(g['order']['MBR_NO'], *key[1:])].append(key)
    audits = []
    for o, t in cancellations:
        ref = o.get('ORIG_ORDER_NO'); orig = orders.get(ref)
        rk = selection(t); key = (ref, *rk); g = groups.get(key)
        when = o['SALE_DTM']; why = set(); plausible = []
        zero = t['BET_AMT'] == 0
        definite = bool(g and orig and orig['ORDER_TYPE_CD'] == 'SALE' and o['MBR_NO'] and o['MBR_NO'] == orig['MBR_NO'])
        if not ref: why.add('NO_ORIGINAL_REFERENCE')
        elif not orig or orig['ORDER_TYPE_CD'] != 'SALE': why.add('ORIGINAL_NOT_FOUND')
        elif not o['MBR_NO'] or o['MBR_NO'] != orig['MBR_NO']: why.add('MEMBER_CONFLICT')
        elif g is None: why.add('REFERENCE_SELECTION_NOT_IN_TARGET')
        if t['TICKET_STAT_CD'] != 'CANCEL': why.add('INVALID_CANCEL_STATUS')
        if t['BET_AMT'] >= 0 or t['UNIT_CNT'] >= 0 or t['BET_AMT'] != t['UNIT_CNT'] * unit_amount: why.add('BAD_CANCEL_AMOUNT')
        if t.get('CHUL_NO2') is not None or t.get('HR_NM2'): why.add('CANCEL_SECOND_SELECTION')
        e = entries.get(rk)
        if e and t.get('HR_NM') and t['HR_NM'] != e['HR_NM']: why.add('CANCEL_HORSE_CONFLICT')
        if when is None: why.add('CANCEL_TIME_MISSING')
        elif orig and orig.get('SALE_DTM') and when < orig['SALE_DTM']: why.add('CANCEL_BEFORE_PURCHASE')
        r = races.get(rk[:2]); start = r.get('START_DTM') if r else None
        late = bool(when and start and when >= start)
        if zero:
            status = 'ZERO_EXCLUDED'
        elif definite:
            g['cancel_raw'] += abs(t['BET_AMT']); g['cancel_ids'].add(o['ORDER_NO'])
            if why:
                g['bad'].update(why); g['cancel_uncertain'] = True
                status = 'INVALID_TARGET_LINK'
            else:
                g['cancel_amount'] += abs(t['BET_AMT']); g['cancel_units'] += abs(t['UNIT_CNT'])
                g['cancel_times'].append(when); g['late_count'] += int(late)
                status = 'VERIFIED_TARGET_LINK'
        else:
            status = 'NOT_ASSIGNED_TO_TARGET'
            if o['MBR_NO']:
                for k in candidates.get((o['MBR_NO'], *rk), []):
                    ptime = groups[k]['order']['SALE_DTM']
                    if when is None or ptime is None or ptime <= when:
                        plausible.append(k); groups[k]['unresolved'].add(o['ORDER_NO'])
        audits.append(dict(source_row_id=t['_DQ_ROW_ID'], source_bronze_file=t['_SRC_BRONZE_FILE'], source_row_no=t['_SRC_ROW_NO'],
                           cancel_order_no=o['ORDER_NO'], reference_order_no=ref, member_no=o['MBR_NO'], race_date=rk[0], race_no=rk[1],
                           chul_no=rk[2], cancel_at=when, cancel_amount_krw=abs(t['BET_AMT']), cancel_stake_units=abs(t['UNIT_CNT']),
                           matched_target_fact_id=g['fid'] if definite else None, plausible_target_group_count=len(plausible),
                           link_status=status, reasons='ZERO_AMOUNT' if zero else '|'.join(sorted(why)), late_cancel_yn='Y' if late else 'N',
                           rule_id='GOLD-CANCEL', decision_id='G-003;G-004;D-003;D-004;D-006'))
    facts = []; used_channels = {UNKNOWN: channel({})}; used_horses = {}
    for key, g in sorted(groups.items()):
        o = g['order']; rk = key[1:]; e = entries.get(rk); r = races.get(rk[:2]); result = results.get(rk)
        when = o['SALE_DTM']; day = when.date(); bad = set(g['bad'])
        amount = sum(t['BET_AMT'] for t in g['details']); units = sum(t['UNIT_CNT'] for t in g['details'])
        if not e: bad.add('ENTRY_NOT_FOUND')
        start = r['START_DTM'] if r else None
        if not start: bad.add('RACE_START_MISSING')
        elif when >= start: bad.add('PURCHASE_AT_OR_AFTER_START')
        if start and start > cutoff: bad.add('FOLLOWUP_NOT_CLOSED')
        if result is None: bad.add('RESULT_NOT_FOUND')
        elif result['ENTRY_STAT_CD'] != 'RAN': bad.add('VOID_OR_NONSTART_STATUS')
        if g['unresolved']: bad.add('UNRESOLVED_CANCEL_CONTEXT')
        if g['cancel_raw'] > amount or g['cancel_units'] > units:
            bad.add('CANCEL_EXCEEDS_PURCHASE'); g['cancel_uncertain'] = True
        name = e.get('HR_NM') if e else None
        identity = identities.get(name)
        if not identity: bad.add('AMBIGUOUS_HORSE_IDENTITY')
        else: used_horses[identity['horse_key']] = identity
        snapshot = None
        dates, by_date = histories.get(name, ([], {})); position = bisect_left(dates, day) - 1
        if position >= 0:
            chosen = by_date[dates[position]]
            if len(chosen) == 1: snapshot = chosen[0]
            else: bad.add('AMBIGUOUS_PRIOR_SNAPSHOT')
        if snapshot is None: bad.add('NO_PRIOR_SNAPSHOT')
        recent = snapshot.get('Y1_RC_CNT') if snapshot else None; wins = snapshot.get('Y1_1ST_CNT') if snapshot else None
        career = snapshot.get('TOT_RC_CNT') if snapshot else None; careerwins = snapshot.get('TOT_1ST_CNT') if snapshot else None
        valid = all(v is not None for v in [recent, wins, career, careerwins]) and 0 <= wins <= recent and 0 <= careerwins <= career
        if snapshot and not valid: bad.add('INVALID_PRIOR_RECORD')
        if recent == 0: bad.add('ZERO_RECENT_STARTS')
        rate = wins / recent if valid and recent else None
        cr = careerwins / career if valid and career else None
        label = None if g['cancel_uncertain'] or g['unresolved'] else int(bool(g['cancel_times']))
        first = min(g['cancel_times']) if g['cancel_times'] else None
        ch = channel(o); used_channels[ch['channel_key']] = ch
        facts.append(dict(fact_id=g['fid'], original_order_no=key[0], member_key=member_keys.get(o['MBR_NO'], UNKNOWN),
                          horse_key=identity['horse_key'] if identity else UNKNOWN, race_id=race_keys.get(rk[:2], UNKNOWN), channel_key=ch['channel_key'],
                          purchase_date_key=date_key(day), cancel_date_key=date_key(first.date()) if first else 0,
                          race_date_key=date_key(rk[0]), snapshot_date_key=date_key(snapshot['SNAPSHOT_DT']) if snapshot else 0,
                          bet_type_cd='WIN', chul_no=rk[2], age_at_purchase=g['age'], purchase_at=when,
                          horse_age_at_race=e.get('HR_AGE') if e else None, horse_sex_at_race=e.get('HR_SEX_CD') if e else None,
                          purchase_detail_count=len(g['details']), purchase_stake_units=units, purchase_amount_krw=amount,
                          horse_snapshot_date=snapshot['SNAPSHOT_DT'] if snapshot else None,
                          snapshot_age_days=(day - snapshot['SNAPSHOT_DT']).days if snapshot else None,
                          recent1y_starts=recent, recent1y_wins=wins, recent1y_win_rate=rate, recent1y_win_rate_band=band(rate),
                          career_starts=career, career_wins=careerwins, career_win_rate=cr,
                          has_verified_customer_cancel=label, cancel_label_status='AMBIGUOUS' if label is None else 'VERIFIED_CANCEL' if label else 'NO_CANCEL_OBSERVED',
                          cancel_transaction_count=len(g['cancel_ids']), raw_linked_cancel_amount_krw=g['cancel_raw'],
                          verified_cancel_amount_krw=g['cancel_amount'], verified_cancel_stake_units=g['cancel_units'],
                          first_cancel_at=first, cancel_delay_seconds=int((first - when).total_seconds()) if first else None,
                          late_cancel_detail_count=g['late_count'], unresolved_cancel_order_count=len(g['unresolved']),
                          header_detail_mismatch=int(o.get('HEADER_MISMATCH_YN') == 'Y'), observation_end_at=cutoff,
                          analysis_eligible=int(not bad), exclusion_reasons='|'.join(sorted(bad)), purchase_order_row_id=o['_DQ_ROW_ID'],
                          entry_row_id=e['_DQ_ROW_ID'] if e else None, snapshot_row_id=snapshot['_DQ_ROW_ID'] if snapshot else None,
                          dq_dataset_version=version, rule_version=RULE_VERSION))
    all_days = {r['race_date'] for r in dim_races if r.get('race_date')}
    for f in facts:
        all_days.add(f['purchase_at'].date())
        if f['first_cancel_at']: all_days.add(f['first_cancel_at'].date())
        if f['horse_snapshot_date']: all_days.add(f['horse_snapshot_date'])
    dim_dates = [dict(date_key=0)]
    if all_days:
        day, end = min(all_days), max(all_days)
        while day <= end:
            dim_dates.append(dict(date_key=date_key(day), calendar_date=day, year=day.year, quarter=(day.month-1)//3+1,
                                  month=day.month, day_of_month=day.day, weekday=day.isoweekday(), year_month=day.strftime('%Y-%m')))
            day += timedelta(days=1)
    eligible = [f for f in facts if f['analysis_eligible']]
    summaries = []
    for scope, minimum in [('all_positive_starts', 1), ('min_10_recent_starts', 10)]:
        for bucket in ['0%', '(0,5%]', '(5,10%]', '(10,20%]', '>20%']:
            rows = [f for f in eligible if f['recent1y_starts'] >= minimum and f['recent1y_win_rate_band'] == bucket]
            count = len(rows); cancels = sum(f['has_verified_customer_cancel'] for f in rows)
            amt = sum(f['purchase_amount_krw'] for f in rows); camt = sum(f['verified_cancel_amount_krw'] for f in rows)
            summaries.append(dict(summary_id=scope + ':' + bucket, scope=scope, win_rate_band=bucket, purchase_selection_groups=count,
                                  cancelled_groups=cancels, observed_cancel_rate=cancels/count if count else None,
                                  purchase_amount_krw=amt, cancel_amount_krw=camt, amount_cancel_rate=camt/amt if amt else None,
                                  unique_members=len({f['member_key'] for f in rows}), unique_horses=len({f['horse_key'] for f in rows}),
                                  unique_races=len({f['race_id'] for f in rows})))
    output_rows = dict(dim_member=dim_members, dim_horse=[dict(horse_key=UNKNOWN, identity_status='UNVERIFIED')] + sorted(used_horses.values(), key=lambda r:r['horse_key']),
                       dim_race=dim_races, dim_date=dim_dates,
                       dim_channel=[used_channels[UNKNOWN]] + sorted([v for k,v in used_channels.items() if k != UNKNOWN], key=lambda r:r['channel_cd']),
                       **{FACT:facts}, ticket_disposition=dispositions, cancel_link_audit=audits,
                       fact_analysis_exclusions=[dict(fact_id=f['fact_id'], exclusion_reasons=f['exclusion_reasons'], rule_id='GOLD-ELIGIBLE',
                                                      decision_id='G-001;G-002;G-003;G-004;G-005;G-006') for f in facts if not f['analysis_eligible']],
                       win_rate_cancel_summary=summaries)
    checks = []
    def check(name, expected, actual):
        checks.append(dict(check=name, expected=expected, actual=actual, passed=expected == actual))
    for name, rows in output_rows.items():
        check(name + ' PK duplicates', 0, len(rows) - len({r[PKS[name]] for r in rows}))
        check(name + ' PK nulls', 0, sum(r.get(PKS[name]) is None for r in rows))
    check('fact business key duplicates', 0, len(facts) - len({(f['original_order_no'], f['race_id'], f['bet_type_cd'], f['chul_no']) for f in facts}))
    for dim, field in [('dim_member','member_key'),('dim_horse','horse_key'),('dim_race','race_id'),('dim_channel','channel_key'),
                       *[('dim_date', c) for c in ['purchase_date_key','cancel_date_key','race_date_key','snapshot_date_key']]]:
        keys = {r[PKS[dim]] for r in output_rows[dim]}
        check(field + ' missing FK', 0, sum(f[field] not in keys for f in facts))
    check('input ticket row coverage', len(data['BET_TICKET']), len(dispositions))
    check('input ticket id coverage', sorted(t['_DQ_ROW_ID'] for t in data['BET_TICKET']), sorted(d['source_row_id'] for d in dispositions))
    # Keep full ID lists out of metadata after proving exact coverage.
    coverage = checks[-1]; coverage['expected'] = len(data['BET_TICKET']); coverage['actual'] = len(dispositions)
    check('target purchase details', target_detail_count, sum(f['purchase_detail_count'] for f in facts))
    check('target purchase amount', target_detail_amount, sum(f['purchase_amount_krw'] for f in facts))
    check('target purchase units', target_detail_units, sum(f['purchase_stake_units'] for f in facts))
    check('all input signed amount', sum(t['BET_AMT'] for t in data['BET_TICKET']), sum(d['bet_amt'] for d in dispositions))
    check('all WIN cancel details audited', len(cancellations), len(audits))
    check('verified cancel amount audit', sum(a['cancel_amount_krw'] for a in audits if a['link_status']=='VERIFIED_TARGET_LINK'), sum(f['verified_cancel_amount_krw'] for f in facts))
    check('eligible plus excluded facts', len(facts), len(eligible) + len(output_rows['fact_analysis_exclusions']))
    check('eligible cohort/prior/time/amount bounds', True, all(50 <= f['age_at_purchase'] <= 59 and f['bet_type_cd']=='WIN'
          and f['horse_snapshot_date'] < f['purchase_at'].date() and 0 <= f['recent1y_win_rate'] <= 1
          and f['has_verified_customer_cancel'] in (0,1) and 0 <= f['verified_cancel_amount_krw'] <= f['purchase_amount_krw']
          and (not f['first_cancel_at'] or f['first_cancel_at'] >= f['purchase_at']) for f in eligible))
    base_summary = [r for r in summaries if r['scope']=='all_positive_starts']
    for label, field in [('purchase_selection_groups', None), ('cancelled_groups','has_verified_customer_cancel'),
                         ('purchase_amount_krw','purchase_amount_krw'), ('cancel_amount_krw','verified_cancel_amount_krw')]:
        check('base summary ' + label, len(eligible) if field is None else sum(f[field] for f in eligible), sum(r[label] for r in base_summary))
    if not all(c['passed'] for c in checks):
        raise ValueError('Gold checks failed: ' + str([c for c in checks if not c['passed']]))
    report = dict(status='passed', rule_version=RULE_VERSION, dq_dataset_version=version, unit_amount=unit_amount,
                  counts={name:len(rows) for name,rows in output_rows.items()}, checks=checks,
                  metrics=dict(eligible_facts=len(eligible), excluded_facts=len(facts)-len(eligible),
                               eligible_cancel_groups=sum(f['has_verified_customer_cancel'] for f in eligible),
                               eligible_purchase_amount=sum(f['purchase_amount_krw'] for f in eligible),
                               eligible_cancel_amount=sum(f['verified_cancel_amount_krw'] for f in eligible),
                               eligible_late_cancel_details=sum(f['late_cancel_detail_count'] for f in eligible)),
                  dispositions=dict(sorted(Counter(d['reason'] for d in dispositions).items())),
                  exclusions_nonexclusive=dict(sorted(Counter(reason for f in facts for reason in f['exclusion_reasons'].split('|') if reason).items())))
    return {name:packed(name, rows) for name,rows in output_rows.items()}, report
