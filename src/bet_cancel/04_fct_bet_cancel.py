"""Build the 50s WIN cancellation fact and five dimensions from develop clean Silver."""
from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

FACT = 'fct_bet_selection_cancel_50s'
SOURCES = ('BET_ORDER', 'BET_TICKET', 'MBR_MASTER', 'HR_WEEKLY_SNAPSHOT', 'RC_RACE', 'RC_ENTRY', 'RC_RESULT')
UNKNOWN = 'UNKNOWN'
KST = timezone(timedelta(hours=9), 'KST')
RULE_VERSION = 'GOLD-50WIN-1'
UNIT_AMOUNT = 100
ROOT = Path(__file__).resolve().parents[2]
CLEAN_ROOT = ROOT / 'data/02_silver/clean'
GOLD_ROOT = ROOT / 'data/03_gold/bet_cancel'
TYPES = {'s': pa.string(), 'i': pa.int64(), 'd': pa.date32(), 'n': pa.int32(),
         'f': pa.float64(), 't': pa.timestamp('ms')}
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
}
PKS = {
    'dim_member': 'member_key',
    'dim_horse': 'horse_key',
    'dim_channel': 'channel_key',
    'dim_race': 'race_id',
    'dim_date': 'date_key',
    FACT: 'fact_id',
}
FACT_FKS = {
    'member_key': 'dim_member',
    'horse_key': 'dim_horse',
    'race_id': 'dim_race',
    'channel_key': 'dim_channel',
    'purchase_date_key': 'dim_date',
    'cancel_date_key': 'dim_date',
    'race_date_key': 'dim_date',
    'snapshot_date_key': 'dim_date',
}


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_inputs():
    manifest = json.loads((CLEAN_ROOT / '_manifest.json').read_text(encoding='utf-8'))
    version = manifest['CLEAN_VERSION']
    if not isinstance(version, str) or not version:
        raise ValueError('Missing clean dataset version')

    data = {}
    for name in SOURCES:
        path = CLEAN_ROOT / f'{name}.parquet'
        approved_hash = manifest['CLEAN_SHA256'][path.name]
        if file_hash(path) != approved_hash:
            raise ValueError(f'Unapproved clean input: {name}')
        rows = pq.ParquetFile(path).read().to_pylist()
        row_numbers = {row['_SRC_ROW_NO'] for row in rows}
        if len(row_numbers) != len(rows) or any(type(n) is not int or n < 1 for n in row_numbers):
            raise ValueError(f'{name}: expected unique positive Bronze row numbers')
        for row in rows:
            row['_DQ_ROW_ID'] = f"{name}:{row['_SRC_ROW_NO']:08d}"
        data[name] = rows
    return data, version


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


def kst_wall_time(value):
    """Develop uses local KST. Convert aware inputs to the same clock before stripping the zone."""
    if value is None or value.utcoffset() is None:
        return value
    return value.astimezone(KST).replace(tzinfo=None)


def build(data, version):
    data = dict(data)
    for name, field in [('BET_ORDER', 'SALE_DTM'), ('RC_RACE', 'START_DTM')]:
        data[name] = [dict(row, **{field: kst_wall_time(row[field])}) for row in data[name]]
    orders = {k[0]: v for k, v in unique_index(data['BET_ORDER'], ['ORDER_NO'], 'BET_ORDER').items()}
    members = {k[0]: v for k, v in unique_index(data['MBR_MASTER'], ['MBR_NO'], 'MBR_MASTER').items()}
    races = unique_index(data['RC_RACE'], ['RC_DT', 'RC_NO'], 'RC_RACE')
    entries = unique_index(data['RC_ENTRY'], ['RC_DT', 'RC_NO', 'CHUL_NO'], 'RC_ENTRY')
    results = unique_index(data['RC_RESULT'], ['RC_DT', 'RC_NO', 'CHUL_NO'], 'RC_RESULT')
    unique_index(data['BET_TICKET'], ['ORDER_NO', 'TICKET_SEQ'], 'BET_TICKET')
    if not orders or not any(r['SALE_DTM'] for r in orders.values()):
        raise ValueError('At least one valid order time is required')
    cutoff = max(o['SALE_DTM'] for o in orders.values() if o['SALE_DTM'])
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
    cancellations = []
    for ticket in data['BET_TICKET']:
        zero = ticket['BET_AMT'] == 0
        if (ticket.get('INVALID_YN') == 'Y') != zero:
            raise ValueError('INVALID_YN differs from zero amount')
        order = orders.get(ticket['ORDER_NO'])
        if zero or order is None or ticket['BET_TYPE_CD'] != 'WIN':
            continue
        if order['ORDER_TYPE_CD'] == 'CANCEL':
            cancellations.append((order, ticket))
            continue
        if order['ORDER_TYPE_CD'] != 'SALE':
            continue

        member = members.get(order['MBR_NO'])
        when = order['SALE_DTM']
        age = age_at(member['BIRTH_DT'] if member else None, when.date() if when else None)
        if age is None or not 50 <= age <= 59:
            continue

        selected = selection(ticket)
        key = (ticket['ORDER_NO'], *selected)
        if key not in groups:
            fid = stable_key('selection', [key[0], key[1], key[2], 'WIN', key[3]])
            groups[key] = dict(
                fid=fid, order=order, age=age, details=[], bad=set(),
                cancel_raw=0, cancel_amount=0, cancel_units=0, cancel_ids=set(), cancel_times=[],
                unresolved=set(), late_count=0, cancel_uncertain=False,
            )
        group = groups[key]
        group['details'].append(ticket)
        amount = ticket['BET_AMT']
        units = ticket['UNIT_CNT']
        if amount <= 0 or units <= 0 or amount != units * UNIT_AMOUNT:
            group['bad'].add('BAD_PURCHASE_AMOUNT')
        if ticket['TICKET_STAT_CD'] not in ('SOLD', 'VOID'):
            group['bad'].add('INVALID_PURCHASE_STATUS')
        if ticket['TICKET_STAT_CD'] == 'VOID':
            group['bad'].add('VOID_OR_NONSTART_STATUS')
        if ticket.get('CHUL_NO2') is not None or ticket.get('HR_NM2'):
            group['bad'].add('WIN_SECOND_SELECTION')
        entry = entries.get(selected)
        if entry and ticket.get('HR_NM') and ticket['HR_NM'] != entry['HR_NM']:
            group['bad'].add('HORSE_NAME_CONFLICT')

    candidates = defaultdict(list)
    for key, group in groups.items():
        candidates[(group['order']['MBR_NO'], *key[1:])].append(group)
    for order, ticket in cancellations:
        reference = order.get('ORIG_ORDER_NO')
        selected = selection(ticket)
        group = groups.get((reference, *selected))
        original = orders.get(reference)
        member_no = order['MBR_NO']
        when = order['SALE_DTM']
        if not (group and original and original['ORDER_TYPE_CD'] == 'SALE'
                and member_no and member_no == original['MBR_NO']):
            if member_no:
                for candidate in candidates.get((member_no, *selected), []):
                    purchase_time = candidate['order']['SALE_DTM']
                    if when is None or purchase_time is None or purchase_time <= when:
                        candidate['unresolved'].add(order['ORDER_NO'])
            continue

        amount = ticket['BET_AMT']
        units = ticket['UNIT_CNT']
        group['cancel_raw'] += abs(amount)
        group['cancel_ids'].add(order['ORDER_NO'])
        reasons = set()
        if ticket['TICKET_STAT_CD'] != 'CANCEL':
            reasons.add('INVALID_CANCEL_STATUS')
        if amount >= 0 or units >= 0 or amount != units * UNIT_AMOUNT:
            reasons.add('BAD_CANCEL_AMOUNT')
        if ticket.get('CHUL_NO2') is not None or ticket.get('HR_NM2'):
            reasons.add('CANCEL_SECOND_SELECTION')
        entry = entries.get(selected)
        if entry and ticket.get('HR_NM') and ticket['HR_NM'] != entry['HR_NM']:
            reasons.add('CANCEL_HORSE_CONFLICT')
        if when is None:
            reasons.add('CANCEL_TIME_MISSING')
        elif original['SALE_DTM'] and when < original['SALE_DTM']:
            reasons.add('CANCEL_BEFORE_PURCHASE')
        if reasons:
            group['bad'].update(reasons)
            group['cancel_uncertain'] = True
            continue

        race = races.get(selected[:2])
        start = race['START_DTM'] if race else None
        group['cancel_amount'] += abs(amount)
        group['cancel_units'] += abs(units)
        group['cancel_times'].append(when)
        group['late_count'] += int(start is not None and when >= start)

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
    output_rows = {
        'dim_member': dim_members,
        'dim_horse': [dict(horse_key=UNKNOWN, identity_status='UNVERIFIED')]
                    + sorted(used_horses.values(), key=lambda row: row['horse_key']),
        'dim_race': dim_races,
        'dim_date': dim_dates,
        'dim_channel': [used_channels[UNKNOWN]]
                      + sorted((row for key, row in used_channels.items() if key != UNKNOWN),
                               key=lambda row: row['channel_cd']),
        FACT: facts,
    }
    primary_keys = {}
    for name, rows in output_rows.items():
        keys = {row[PKS[name]] for row in rows}
        if None in keys or len(keys) != len(rows):
            raise ValueError(f'{name}: null or duplicate primary key')
        primary_keys[name] = keys
    for field, dimension in FACT_FKS.items():
        if any(fact[field] not in primary_keys[dimension] for fact in facts):
            raise ValueError(f'{FACT}: {field} contains a missing dimension key')
    return {name: packed(name, rows) for name, rows in output_rows.items()}


def main():
    tables = build(*load_inputs())
    GOLD_ROOT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.bet-cancel-', dir=GOLD_ROOT.parent) as staging:
        files = []
        for name, table in tables.items():
            filename = f'{name.upper()}.parquet'
            staged = Path(staging) / filename
            pq.write_table(table, staged, compression='snappy')
            files.append((staged, GOLD_ROOT / filename))
        for staged, destination in files:
            if not destination.is_file() or file_hash(destination) != file_hash(staged):
                staged.replace(destination)
    print(f'Gold bet_cancel: {tables[FACT].num_rows:,} fact rows and {len(tables) - 1} dimensions.')


if __name__ == '__main__':
    main()
