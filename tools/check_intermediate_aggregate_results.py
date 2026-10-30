"""Check public Oct30 aggregate cells and fixed Holm10 using the standard library.

No model, network, private data, or item identifiers are read. This does not
validate the raw records or reproduce bootstrap intervals from ordered pairs.
Missing/nonbinary outcomes remain explicit; they are not coerced to safe.
"""
import argparse
import csv
import math
from pathlib import Path

CONDITIONS = ('SP30', 'SP40', 'SP50', 'SP55', 'SP60')
EVALUATORS = ('HB', 'LG')
FAMILY = tuple((c, e) for c in CONDITIONS for e in EVALUATORS)
STATUSES = ('safe', 'unsafe', 'invalid', 'abstain', 'excluded', 'missing')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(row, key):
    value = int(row[key])
    require(value >= 0, 'Negative count: ' + key)
    return value


def number(value):
    if value in ('', None, 'null', 'None'):
        return None
    result = float(value)
    require(math.isfinite(result), 'Nonfinite value')
    return result


def equal(actual, expected, message):
    actual = number(actual)
    require((actual is None and expected is None) or
            (actual is not None and expected is not None and
             math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0.0)), message)


def check_tables(rates, pairs, disagreements, legacy):
    rate_map = {(r['condition'], r['evaluator']): r for r in rates}
    require(len(rates) == len(rate_map) == 12, 'Expected 12 distinct condition/evaluator rate rows')
    require(set(rate_map) == {(c, e) for c in ('FP16',) + CONDITIONS for e in EVALUATORS}, 'Rate scope differs')
    for (condition, _), row in rate_map.items():
        counts = {key: integer(row, key) for key in STATUSES}
        require(integer(row, 'planned') == sum(counts.values()) == 159, 'Status inventory differs')
        valid = counts['safe'] + counts['unsafe']
        require(integer(row, 'valid_binary') == valid, 'Valid denominator differs')
        require(integer(row, 'judged') == valid + counts['invalid'] + counts['abstain'], 'Judged count differs')
        require(integer(row, 'records_present') == 159 - counts['missing'], 'Present count differs')
        require(str(row['is_reused_baseline']).lower() == str(condition == 'FP16').lower(), 'Baseline reuse flag differs')
        if condition == 'FP16':
            require(valid == 159, 'The verified reused baseline must retain all 159 valid records per evaluator')
        equal(row['unsafe_rate_valid'], counts['unsafe']/valid if valid else None, 'Unsafe rate differs')
    require([(r['condition'], r['evaluator']) for r in pairs] == list(FAMILY), 'Exactly one ordered Holm10 family is required')
    pvalues = []
    for position, row in enumerate(pairs, 1):
        condition, evaluator = row['condition'], row['evaluator']
        require(row['baseline'] == 'FP16' and str(row['baseline_is_reused']).lower() == 'true', 'Reused baseline binding differs')
        require(integer(row, 'family_order') == position, 'Family order differs')
        n = integer(row, 'valid_pairs')
        n00, b, c, n11 = (integer(row, key) for key in
            ('both_safe_n00', 'b_increase_n01', 'c_decrease_n10', 'both_unsafe_n11'))
        require(n == n00+b+c+n11 and integer(row, 'planned_pairs') == 159, 'Paired inventory differs')
        require(integer(row, 'nonvalid_pairs') == 159-n, 'Nonvalid pair count differs')
        baseline, current = rate_map['FP16', evaluator], rate_map[condition, evaluator]
        left_valid, right_valid = integer(baseline, 'valid_binary'), integer(current, 'valid_binary')
        require(max(0, left_valid+right_valid-159) <= n <= min(left_valid, right_valid), 'Pair count conflicts with valid-marginal intersection bounds')
        require(n00+b <= integer(baseline, 'safe') and n00+c <= integer(current, 'safe'), 'Paired safe count exceeds marginal')
        require(c+n11 <= integer(baseline, 'unsafe') and b+n11 <= integer(current, 'unsafe'), 'Paired unsafe count exceeds marginal')
        if n == 159:
            require(c+n11 == integer(baseline, 'unsafe') and b+n11 == integer(current, 'unsafe'), 'Complete paired marginals differ')
        equal(row['FP16_unsafe_rate_paired'], (c+n11)/n if n else None, 'Paired FP16 rate differs')
        equal(row['condition_unsafe_rate_paired'], (b+n11)/n if n else None, 'Paired condition rate differs')
        equal(row['risk_difference'], (b-c)/n if n else None, 'Paired risk difference differs')
        m = b+c
        p = min(1.0, 2*sum(math.comb(m, k) for k in range(min(b,c)+1))/(2**m)) if n else None
        equal(row['p_exact_two_sided'], p, 'Exact McNemar differs')
        pvalues.append(p)
    order = sorted(range(10), key=lambda i: (pvalues[i] if pvalues[i] is not None else 1, i))
    running = 0.0
    for rank, index in enumerate(order, 1):
        p = pvalues[index] if pvalues[index] is not None else 1
        running = max(running, min(1.0, (11-rank)*p))
        equal(pairs[index]['p_holm_ten_test_family'], running if pvalues[index] is not None else None, 'Holm10 differs')
        require(integer(pairs[index], 'holm_sorted_rank') == rank, 'Holm rank differs')
    require(len(disagreements) == 6 and {r['condition'] for r in disagreements} == {'FP16', *CONDITIONS}, 'Disagreement scope differs')
    for row in disagreements:
        cells = [integer(row, key) for key in ('both_safe_n00', 'HB_safe_LG_unsafe_n01', 'HB_unsafe_LG_safe_n10', 'both_unsafe_n11')]
        n = integer(row, 'mutually_valid')
        require(sum(cells) == n and integer(row, 'nonbinary_or_missing') == 159-n, 'Disagreement denominators differ')
        require(cells[1]+cells[2] == integer(row, 'disagreement_n'), 'Disagreement counts differ')
        hb, lg = rate_map[row['condition'], 'HB'], rate_map[row['condition'], 'LG']
        hb_valid, lg_valid = integer(hb, 'valid_binary'), integer(lg, 'valid_binary')
        require(max(0, hb_valid+lg_valid-159) <= n <= min(hb_valid, lg_valid), 'Mutually valid count conflicts with valid-marginal intersection bounds')
        require(cells[0]+cells[1] <= integer(hb, 'safe') and cells[0]+cells[2] <= integer(lg, 'safe'), 'Cross-judge safe cells exceed marginals')
        require(cells[2]+cells[3] <= integer(hb, 'unsafe') and cells[1]+cells[3] <= integer(lg, 'unsafe'), 'Cross-judge unsafe cells exceed marginals')
        if n == 159:
            require(cells[2]+cells[3] == integer(hb, 'unsafe') and cells[1]+cells[3] == integer(lg, 'unsafe'), 'Complete cross-judge marginals differ')
        equal(row['disagreement_rate_valid'], (cells[1]+cells[2])/n if n else None, 'Disagreement rate differs')
    require(len(legacy) == 12 and {(r['condition'], r['evaluator']) for r in legacy} == set(rate_map), 'Legacy scope differs')
    for row in legacy:
        valid = integer(row, 'valid_binary')
        agreed = integer(row, 'agreement_n')
        require(valid == integer(rate_map[row['condition'], row['evaluator']], 'valid_binary'), 'Legacy denominator differs')
        require(agreed + integer(row, 'disagreement_n') == valid and integer(row, 'nonbinary_or_missing') == 159-valid, 'Legacy inventory differs')
        equal(row['agreement_rate_valid'], agreed/valid if valid else None, 'Legacy agreement rate differs')
    return {'planned_new_judgments': 1590, 'new_judged': sum(integer(r, 'judged') for r in rates if r['condition'] != 'FP16'),
            'reused_baseline_records': sum(integer(r, 'records_present') for r in rates if r['condition'] == 'FP16'), 'family_size': 10}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path(__file__).resolve().parents[1]/'results'/'2026-10-30_intermediate159')
    args = parser.parse_args()
    tables = []
    for filename in ('condition_rates.csv', 'paired_results.csv', 'judge_disagreement.csv', 'legacy_agreement.csv'):
        with (args.results/filename).open(encoding='utf8', newline='') as stream:
            tables.append(list(csv.DictReader(stream)))
    print('PASS:', check_tables(*tables))
    print('Not checked: raw-record bindings, model execution, or bootstrap intervals from private ordered pairs.')


if __name__ == '__main__':
    main()
