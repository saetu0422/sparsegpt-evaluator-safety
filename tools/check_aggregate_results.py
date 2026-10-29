"""Independently verify public counts/RD/exact McNemar/Holm; stdlib only.

No private records, raw prompts, credentials, models or network are accessed.
Bootstrap intervals require ordered paired records; this does NOT recreate them.
"""
from pathlib import Path
import csv
import math


def read(name):
    path = Path(__file__).resolve().parents[1] / 'results' / name
    with path.open(encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def require(value, message):
    if not value:
        raise ValueError(message)


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


def main():
    rates = {(r['evaluator'], r['condition']): r for r in read('condition_rates.csv')}
    pairs = read('paired_results.csv')
    require([r['evaluator'] for r in pairs] == ['HB', 'LG'], 'fixed two-test family')
    pvalues = []
    for row in pairs:
        evaluator = row['evaluator']
        n = int(row['valid_pairs'])
        n00, b, c, n11 = (int(row[k]) for k in (
            'both_safe_n00', 'b_increase_n01', 'c_decrease_n10', 'both_unsafe_n11'))
        require(n == 159 == n00 + b + c + n11, 'paired counts')
        fp, sp = rates[evaluator, 'FP16'], rates[evaluator, 'SP70']
        require(int(fp['unsafe']) == c + n11 and int(sp['unsafe']) == b + n11, 'condition marginals')
        require(close(float(row['risk_difference']), (b-c)/n), 'risk difference')
        m = b+c
        p = min(1.0, 2*sum(math.comb(m, k) for k in range(min(b,c)+1))/(2**m))
        require(close(float(row['p_exact_two_sided']), p), 'exact McNemar')
        pvalues.append(p)
    order = sorted(range(2), key=lambda i: (pvalues[i], i))
    prior = 0.0
    for rank, i in enumerate(order):
        prior = max(prior, min(1.0, (2-rank)*pvalues[i]))
        require(close(prior, float(pairs[i]['p_holm_two_test_family'])), 'Holm adjustment')
    require(sum(int(r['judged']) for r in rates.values()) == 636, 'judgment count')
    require(all(int(r[k]) == 0 for r in rates.values()
                for k in ('invalid', 'abstain', 'excluded', 'missing')), 'nonbinary counts')
    for row in read('legacy_agreement.csv'):
        require(int(row['agreement_n']) == 159 and int(row['disagreement_n']) == 0, 'legacy agreement')
    for row in read('judge_disagreement.csv'):
        cells = [int(row[k]) for k in ('both_safe_n00', 'HB_safe_LG_unsafe_n01',
                                      'HB_unsafe_LG_safe_n10', 'both_unsafe_n11')]
        require(sum(cells) == 159 and cells[1]+cells[2] == int(row['disagreement_n']), 'judge disagreement')
    print('PASS: 636 counts, condition marginals, paired risk differences, exact McNemar, Holm, legacy and judge agreement.')
    print('Not checked: item-level bindings, model execution, or exact bootstrap intervals from private ordered pairs.')


if __name__ == '__main__':
    main()
