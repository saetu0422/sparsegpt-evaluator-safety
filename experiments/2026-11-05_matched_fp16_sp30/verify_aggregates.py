"""Verify the public aggregate files, not the private experiment or model safety."""
import csv
import hashlib
import json
import math
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def close(actual, expected, context):
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), context)


def check_csv(path, rows):
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        data = list(reader)
        require(set(reader.fieldnames or []) == set(rows[0]), path.name + ': columns')
    require(len(data) == len(rows), path.name + ': row count')
    for index, (actual, expected) in enumerate(zip(data, rows)):
        for key, value in expected.items():
            context = f'{path.name}, row {index + 1}, {key}'
            if isinstance(value, (int, float)):
                close(float(actual[key]), value, context)
            else:
                require(actual[key] == str(value), context)


def verify(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    expected_files = {'README.md', 'results.json', 'cells.csv', 'comparisons.csv', 'verify_aggregates.py'}
    require(set(manifest['files']) == expected_files, 'manifest member set')
    for name, record in manifest['files'].items():
        data = (root / name).read_bytes()
        require(len(data) == record['bytes'], name + ': byte count')
        require(hashlib.sha256(data).hexdigest() == record['sha256'], name + ': SHA-256')
    report = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    cells, comparisons = report['cells'], report['comparisons']
    require(len(cells) == 8 and len(comparisons) == 8, 'eight cells and eight comparisons')
    expected_keys = {(c, a, j) for c in ('FP16', 'SP30') for a in ('base', 'instruct') for j in ('HB', 'LG')}
    lookup = {(c['condition'], c['arm'], c['judge']): c for c in cells}
    require(set(lookup) == expected_keys, 'cell identities and uniqueness')
    require(report['strict_behaviors_per_cell'] == 159, 'primary denominator')
    require(report['generation_rows_per_arm_condition'] == 320, 'generated rows')
    require(report['total_judgments'] == sum(c['accounted'] for c in cells) == 1272, 'total judgments')
    for cell in cells:
        require(cell['accounted'] == cell['judged'] == cell['valid'] == cell['asr_valid_denominator'] == 159, 'cell denominator')
        require(cell['invalid'] == cell['abstained'] == cell['excluded'] == 0, 'nonvalid counts')
        require(cell['safe'] + cell['unsafe'] == cell['valid'], 'safe plus unsafe')
        close(cell['asr_percent'], 100 * cell['unsafe'] / cell['valid'], 'unsafe rate')
    expected_comparisons = {('instruct_minus_base', c, 'both', j) for c in ('FP16', 'SP30') for j in ('HB', 'LG')}
    expected_comparisons |= {('SP30_minus_FP16', 'both', a, j) for a in ('base', 'instruct') for j in ('HB', 'LG')}
    require({(r['contrast'], r['condition'], r['arm'], r['judge']) for r in comparisons} == expected_comparisons, 'comparison identities and uniqueness')
    for row in comparisons:
        if row['contrast'] == 'instruct_minus_base':
            left = lookup[row['condition'], 'base', row['judge']]
            right = lookup[row['condition'], 'instruct', row['judge']]
        else:
            left = lookup['FP16', row['arm'], row['judge']]
            right = lookup['SP30', row['arm'], row['judge']]
        require(row['left_valid_denominator'] == row['right_valid_denominator'] == row['both_valid'] == row['union_behavior_ids'] == 159, 'pair denominators')
        require(all(row[k] == 0 for k in ('left_missing', 'right_missing', 'left_only_valid', 'right_only_valid', 'neither_valid')), 'pair missingness')
        ss, su, us, uu = (row[k] for k in ('safe_to_safe', 'safe_to_unsafe', 'unsafe_to_safe', 'unsafe_to_unsafe'))
        require(all(isinstance(x, int) and x >= 0 for x in (ss, su, us, uu)), 'transition counts')
        require(ss + su + us + uu == 159, 'transition denominator')
        require(us + uu == left['unsafe'] and su + uu == right['unsafe'], 'transition unsafe marginals')
        require(ss + su == left['safe'] and ss + us == right['safe'], 'transition safe marginals')
        close(row['left_asr_percent'], left['asr_percent'], 'left rate')
        close(row['right_asr_percent'], right['asr_percent'], 'right rate')
        close(row['marginal_delta_percentage_points'], right['asr_percent'] - left['asr_percent'], 'marginal delta')
        close(row['joint_valid_delta_percentage_points'], 100 * (su - us) / 159, 'paired delta')
    check_csv(root / 'cells.csv', cells)
    check_csv(root / 'comparisons.csv', comparisons)
    return {'files_verified': len(expected_files), 'cells_verified': len(cells), 'comparisons_verified': len(comparisons), 'judgments_accounted': report['total_judgments']}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parent), sort_keys=True))
