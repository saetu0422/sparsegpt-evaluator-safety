#!/usr/bin/env python3
"""Offline-only frozen exploratory five-level analysis; no model/network/GPU calls."""
from __future__ import annotations
import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import platform
import re
import zipfile
import numpy as np

PLAN_SHA = '473ecba7402b70a171b0589e8eb761cbe802330bd6de4d717a31e948aa94a5c7'
BASELINE_VALIDATOR_SHA = 'f91a8a4c9e1a2bb349c565b06baf7beea744c3863d603ba58db84d74712e4bb0'
ZIP_SHA = 'dd8e84fe8a6e1d4d6f460ab5cb27f1f4650f90f162f99450e8766a5c8254d482'
CONDITIONS = ('SP30', 'SP40', 'SP50', 'SP55', 'SP60')
ALL_CONDITIONS = ('FP16',) + CONDITIONS
EVALUATORS = ('HB', 'LG')
STATUSES = ('safe', 'unsafe', 'invalid', 'abstain', 'excluded', 'missing')
BINARY = {'safe': 0, 'unsafe': 1}
N_IDS, NEW_N, BASELINE_N, TOTAL_N = 159, 1590, 318, 1908
FAMILY = tuple((c, e) for c in CONDITIONS for e in EVALUATORS)
REPLICATES = 20000
# Confirmed with the reviewed per-condition runner before final release.
PROTOCOL_NAME = 'new-standard159-levels-v1; not historical judge reproduction'
NEW_SCHEMA = 'sparsegpt-mounted-drive-standard159-levels-v1'
OLD_SCHEMA = 'sparsegpt-mounted-drive-standard159-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def load_validator():
    path = Path(__file__).with_name('baseline_validator.py')
    require(sha(path.read_bytes()) == BASELINE_VALIDATOR_SHA, 'frozen baseline validator hash mismatch')
    spec = importlib.util.spec_from_file_location('_frozen_standard159_validator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bv = load_validator()
canonical, strict_json, mcnemar_exact = bv.canonical, bv.strict_json, bv.mcnemar_exact


def read_plan(path):
    path = Path(path)
    require(sha(path.read_bytes()) == PLAN_SHA, 'frozen five-level analysis plan hash mismatch')
    return strict_json(path)


def safe_member_path(root, relative):
    p = PurePosixPath(relative)
    require(not p.is_absolute() and p.parts and all(x not in ('', '.', '..') for x in p.parts), 'unsafe archive/checkpoint path')
    path = Path(root).joinpath(*p.parts)
    require(path.resolve().is_relative_to(Path(root).resolve()), 'path escapes root')
    cursor = Path(root)
    for part in p.parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), 'symlink input is not permitted')
    return path


def verify_pinned_archive(archive, run_dir, spec):
    data = Path(archive).read_bytes()
    require(len(data) == spec['archive_bytes'] and sha(data) == spec['archive_sha256'], 'baseline archive size/hash mismatch')
    names = set()
    with zipfile.ZipFile(archive) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'duplicate archive member')
        for entry in z.infolist():
            safe_member_path(run_dir, entry.filename)
            if entry.is_dir() or not entry.filename.startswith('run/'):
                continue
            relative = entry.filename[4:]
            path = safe_member_path(run_dir, relative)
            require(path.is_file() and path.read_bytes() == z.read(entry), 'baseline extracted bytes differ from pinned archive: ' + relative)
            names.add(relative)
    actual = {str(p.relative_to(run_dir)) for p in Path(run_dir).rglob('*') if p.is_file()}
    require(names and actual == names, 'baseline extracted file inventory differs from pinned archive')
    return {'archive_sha256': spec['archive_sha256'], 'archive_bytes': len(data), 'verified_run_files': len(names)}


def verify_checkpoint(run_dir, tasks, pinned_sha=None, required=True, schema=NEW_SCHEMA):
    path = Path(run_dir) / '_mirror' / 'RUN_MIRROR_COMPLETE.json'
    if not path.exists() and not required:
        return None
    require(path.is_file(), 'full-run checkpoint missing')
    if pinned_sha:
        require(sha(path.read_bytes()) == pinned_sha, 'baseline full checkpoint hash mismatch')
    value = strict_json(path)
    require(value.get('schema') == schema and type(value.get('judged')) is int and value['judged'] == len(tasks), 'full checkpoint schema/judged count mismatch')
    artifacts = value.get('artifacts')
    require(type(artifacts) is list, 'checkpoint artifact list absent')
    expected = {'tasks.json', 'input_provenance.json', 'environment.json', 'HB_protocol.json', 'LG_protocol.json'}
    expected |= {'records/' + sha(t['task_key'].encode()) + '.json' for t in tasks}
    seen = set()
    for artifact in artifacts:
        relative = artifact.get('path')
        require(isinstance(relative, str) and relative not in seen, 'duplicate/malformed checkpoint artifact')
        seen.add(relative)
        p = safe_member_path(run_dir, relative)
        require(p.is_file(), 'checkpoint artifact missing')
        data = p.read_bytes()
        require(type(artifact.get('bytes')) is int and len(data) == artifact['bytes'] and sha(data) == artifact.get('sha256'), 'checkpoint artifact bytes/hash mismatch')
    require(seen == expected, 'full checkpoint membership mismatch')
    return sha(path.read_bytes())


def read_records(run_dir, tasks, allow_absent=False):
    expected = {sha(t['task_key'].encode()) + '.json': t['task_key'] for t in tasks}
    root = Path(run_dir) / 'records'
    if not root.exists() and not root.is_symlink() and allow_absent:
        return []
    require(root.is_dir() and not root.is_symlink(), 'records directory missing or symlink')
    records = []
    for path in sorted(root.iterdir()):
        require(path.is_file() and not path.is_symlink() and path.name in expected, 'unexpected result path: ' + path.name)
        record = strict_json(path)
        require(record.get('task_key') == expected[path.name], 'record filename/task binding mismatch')
        records.append(record)
    return records


def verify_environment(environment, protocols, plan):
    require(isinstance(environment, dict) and environment.get('precision') == 'fp16', 'environment precision mismatch')
    require(canonical(environment.get('packages')) == canonical(plan['protocol_comparability']['approved_package_versions']), 'runtime package versions differ from frozen baseline')
    for e, protocol in protocols.items():
        require(canonical(protocol.get('environment')) == canonical(environment), e + ' protocol/environment binding mismatch')


def load_baseline(run_dir, archive, input_zip, runner_path, plan):
    """Verify all immutable 636 records, then select only the 318 FP16 records."""
    run_dir = Path(run_dir)
    spec = plan['baseline_integrity']
    archive_meta = verify_pinned_archive(archive, run_dir, spec)
    runner, parser = bv.load_runner(runner_path, spec['runner_sha256'], spec['parser_sha256'])
    expected, provenance = runner.inputs(input_zip)
    tasks = strict_json(run_dir / 'tasks.json')
    require(sha(canonical(tasks)) == spec['tasks_sha256'], 'baseline task hash mismatch')
    checkpoint_sha = verify_checkpoint(run_dir, tasks, spec['full_checkpoint_sha256'], schema=OLD_SCHEMA)
    identity = strict_json(run_dir / '_mirror' / 'run_identity.json')
    require(identity.get('run_id') == spec['run_id'], 'baseline run identity mismatch')
    require(sha((run_dir / '_mirror' / 'analysis' / 'analysis_plan.json').read_bytes()) == bv.PLAN_SHA, 'baseline plan mismatch')
    require(canonical(strict_json(run_dir / 'input_provenance.json')) == canonical(provenance), 'baseline source provenance mismatch')
    protocols = {e: strict_json(run_dir / (e + '_protocol.json')) for e in EVALUATORS}
    environment = strict_json(run_dir / 'environment.json')
    verify_environment(environment, protocols, plan)
    pins = {'runner_sha256': spec['runner_sha256'], 'parser_sha256': spec['parser_sha256'], 'parser_version': parser.VERSION}
    records = read_records(run_dir, tasks)
    rows, metadata = bv.validate_dataset(tasks, expected, records, protocols, provenance, runner, pins, False)
    selected = [dict(r, is_reused_baseline=True, source_run_id=spec['run_id'],
                     source_archive_sha256=spec['archive_sha256'], source_checkpoint_sha256=checkpoint_sha,
                     source_analysis_plan_sha256=bv.PLAN_SHA) for r in rows if r['condition'] == 'FP16']
    require(len(selected) == BASELINE_N, 'baseline must supply exactly 318 FP16 rows')
    metadata.update(archive_meta, full_checkpoint_sha256=checkpoint_sha, source_run_id=spec['run_id'],
                    baseline_identity_sha256=sha((run_dir / '_mirror' / 'run_identity.json').read_bytes()),
                    baseline_wrapper_sha256=identity.get('wrapper_sha256'),
                    baseline_judge_checkpoint_sha256={e: sha((run_dir / '_mirror' / (e + '_MIRROR_COMPLETE.json')).read_bytes()) for e in EVALUATORS},
                    baseline_fp16_tasks_sha256=sha(canonical([t for t in tasks if t['condition'] == 'FP16'])),
                    reused_records=BASELINE_N, previous_SP70_records_validated_but_not_analyzed=318)
    return selected, protocols, metadata


def validate_tasks(tasks, expected, conditions):
    require(type(tasks) is list and len(tasks) == N_IDS * 2 * len(conditions), 'task inventory count mismatch')
    require(canonical(tasks) == canonical(expected), 'archived tasks differ from source-rebuilt tasks')
    keys, groups = set(), collections.defaultdict(dict)
    for task in tasks:
        bid, condition, e = (task.get(k) for k in ('behavior_id', 'condition', 'evaluator'))
        require(isinstance(bid, str) and bool(bid) and condition in conditions and e in EVALUATORS, 'task scope mismatch')
        key = '|'.join((bid, condition, e, '42'))
        require(task.get('task_key') == key and key not in keys, 'duplicate/misbound task key')
        keys.add(key)
        require(type(task.get('source_seed')) is int and task['source_seed'] == 42, 'task seed mismatch')
        require(type(task.get('legacy_label')) is int and task['legacy_label'] in (0, 1), 'legacy label type mismatch')
        require(type(task.get('row_index')) is int and 0 <= task['row_index'] < 320, 'row index mismatch')
        require(isinstance(task.get('response'), str) and task.get('response_sha256') == sha(task['response'].encode()), 'task response hash mismatch')
        groups[(condition, e)][bid] = task
    id_sets = [set(group) for group in groups.values()]
    require(len(groups) == 2 * len(conditions) and all(len(s) == N_IDS and s == id_sets[0] for s in id_sets), 'paired ID inventory mismatch')
    for bid in sorted(id_sets[0]):
        reference = groups[(conditions[0], 'HB')][bid]
        for c in conditions:
            hb, lg = (groups[(c, e)][bid] for e in EVALUATORS)
            require(hb['response'] == lg['response'] and hb['response_sha256'] == lg['response_sha256'], 'same-response cross-judge binding mismatch')
            for task in (hb, lg):
                require(task['row_index'] == reference['row_index'] and task['behavior'] == reference['behavior'], 'cross-condition behavior/row binding mismatch')
    return {t['task_key']: t for t in tasks}


def validate_protocol(protocol, condition, e, tasks, provenance, baseline_protocol, pins, plan):
    expected = {'protocol': PROTOCOL_NAME, 'condition': condition, 'judge': e,
                'analysis_plan_sha256': PLAN_SHA, 'tasks_sha256': sha(canonical(tasks)),
                'baseline_archive_sha256': plan['baseline_integrity']['archive_sha256'],
                'baseline_full_checkpoint_sha256': plan['baseline_integrity']['full_checkpoint_sha256'],
                'inputs': provenance, 'runner_code_sha256': pins['runner_sha256'],
                'parser_code_sha256': pins['parser_sha256'], 'model_execution_authorized': True,
                'target_research_model': 'Meta-Llama-3-8B-Instruct; saved responses only, not loaded'}
    for field, value in expected.items():
        require(canonical(protocol.get(field)) == canonical(value), f'{condition}/{e} protocol mismatch: {field}')
    for field in plan['protocol_comparability']['required_equal_scientific_fields']:
        require(canonical(protocol.get(field)) == canonical(baseline_protocol.get(field)), f'{condition}/{e} scientific protocol differs from baseline: {field}')
    require(protocol.get('auth_mode') in ('anonymous', 'ephemeral_explicit_read_token'), 'unexpected authentication mode')
    require(protocol.get('template_sha256') == sha(protocol['template'].encode()), 'protocol template hash mismatch')
    return sha(canonical(protocol))


def row_from_task(task, record, status, run_id, checkpoint_sha):
    new = BINARY.get(status)
    return {'task_key': task['task_key'], 'behavior_id': task['behavior_id'], 'row_index': task['row_index'],
            'condition': task['condition'], 'evaluator': task['evaluator'], 'source_seed': 42,
            'response_sha256': task['response_sha256'], 'legacy_label': task['legacy_label'],
            'new_status': status, 'new_label_binary': new, 'legacy_agrees': None if new is None else new == task['legacy_label'],
            'task_sha256': sha(canonical(task)), 'protocol_sha256': record.get('protocol_sha256'),
            'content_sha256': record.get('content_sha256'), 'raw_judge_completion': record.get('raw_judge_completion'),
            'raw_judge_sha256': record.get('raw_judge_sha256'),
            'nonbinary_reason': ('missing' if status == 'missing' else record.get('token_policy', {}).get('exclude_reason') if status == 'excluded'
                                 else record.get('parsed', {}).get('reason') if new is None else None),
            'is_reused_baseline': False, 'source_run_id': run_id, 'source_archive_sha256': None,
            'source_checkpoint_sha256': checkpoint_sha, 'source_analysis_plan_sha256': PLAN_SHA}


def validate_identity(run_dir, identity, condition, tasks, runner, pins, plan, baseline_protocols, baseline_meta):
    require(isinstance(identity.get('run_id'), str) and re.fullmatch(r'levels159_' + condition + r'_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}', identity['run_id']), 'new run identity namespace mismatch')
    expected = {'schema': NEW_SCHEMA, 'condition': condition, 'analysis_plan_sha256': PLAN_SHA,
                'input_sha256': ZIP_SHA, 'precision': 'fp16', 'scope': 'one_condition159_standard_IDs_x_HB_LG_318_new_judgments',
                'planned_conditions': list(CONDITIONS), 'planned_new_judgments_all_conditions': NEW_N,
                'expected_ids': N_IDS, 'expected_per_judge': N_IDS, 'expected_total_tasks': BASELINE_N,
                'required_package_versions': plan['protocol_comparability']['approved_package_versions'],
                'execution_cutoff_utc': '2026-10-30T08:00:00+00:00', 'wrapper_sha256': pins['wrapper_sha256'],
                'runner_code': {'colab_smoke.py': pins['runner_sha256'], 'research_parsers.py': pins['parser_sha256'], 'HB_standard_template.txt': runner.HB_TEMPLATE_SHA}}
    for key, value in expected.items():
        require(canonical(identity.get(key)) == canonical(value), 'new run identity mismatch: ' + key)
    for name, digest in dict(expected['runner_code'], **{'drive_wrapper.py': pins['wrapper_sha256']}).items():
        path = safe_member_path(run_dir, '_mirror/code/' + name)
        require(path.is_file() and sha(path.read_bytes()) == digest, 'archived reviewed code mismatch: ' + name)
    spec = plan['baseline_integrity']
    lineage = {'baseline_run_id': spec['run_id'], 'baseline_archive_sha256': spec['archive_sha256'],
        'baseline_archive_bytes': spec['archive_bytes'], 'baseline_checkpoint_sha256': spec['full_checkpoint_sha256'],
        'baseline_identity_sha256': baseline_meta['baseline_identity_sha256'],
        'baseline_judge_checkpoint_sha256': baseline_meta['baseline_judge_checkpoint_sha256'],
        'baseline_tasks_sha256': spec['tasks_sha256'], 'baseline_fp16_tasks_sha256': baseline_meta['baseline_fp16_tasks_sha256'],
        'baseline_runner_sha256': spec['runner_sha256'], 'baseline_wrapper_sha256': baseline_meta['baseline_wrapper_sha256'],
        'baseline_plan_sha256': bv.PLAN_SHA, 'baseline_package_versions': plan['protocol_comparability']['approved_package_versions'],
        'baseline_verified_judgments': 636, 'baseline_fp16_comparison_judgments': BASELINE_N, 'new_condition': condition,
        'new_tasks_sha256': sha(canonical(tasks)), 'shared_standard_ids': N_IDS, 'input_sha256': ZIP_SHA,
        'baseline_scientific_fields': {e: {k: baseline_protocols[e][k] for k in plan['protocol_comparability']['required_equal_scientific_fields']} for e in EVALUATORS},
        'scope': 'new condition318 judgments only; yesterday636 retained read-only; no baseline records imported'}
    require(canonical(identity.get('baseline_lineage')) == canonical(lineage), 'new run baseline lineage mismatch')


def validate_new_run(run_dir, expected_by_condition, baseline_protocols, runner, pins, plan, baseline_meta, allow_incomplete):
    run_dir = Path(run_dir)
    tasks = strict_json(run_dir / 'tasks.json')
    conditions = {t.get('condition') for t in tasks}
    require(len(conditions) == 1 and next(iter(conditions)) in CONDITIONS, 'run must contain exactly one authorized condition')
    condition = next(iter(conditions))
    expected, provenance = expected_by_condition[condition]
    task_map = validate_tasks(tasks, expected, (condition,))
    require(canonical(strict_json(run_dir / 'input_provenance.json')) == canonical(provenance), 'run provenance/source mismatch')
    require(sha((run_dir / '_mirror' / 'analysis' / 'analysis_plan.json').read_bytes()) == PLAN_SHA, 'run archived analysis plan mismatch')
    identity = strict_json(run_dir / '_mirror' / 'run_identity.json')
    validate_identity(run_dir, identity, condition, tasks, runner, pins, plan, baseline_protocols, baseline_meta)
    protocols = {e: strict_json(run_dir / (e + '_protocol.json')) for e in EVALUATORS if (run_dir / (e + '_protocol.json')).is_file()}
    require(allow_incomplete or set(protocols) == set(EVALUATORS), 'both new evaluator protocols required')
    environment = strict_json(run_dir / 'environment.json')
    verify_environment(environment, protocols, plan)
    protocol_hashes = {e: validate_protocol(p, condition, e, tasks, provenance, baseline_protocols[e], pins, plan) for e, p in protocols.items()}
    records = read_records(run_dir, tasks, allow_absent=allow_incomplete)
    by_key = {}
    frozen_time = datetime.datetime.fromisoformat(plan['frozen_at_utc'])
    for record in records:
        key = record.get('task_key')
        require(key in task_map and key not in by_key, 'duplicate/unexpected new record')
        task = task_map[key]; e = task['evaluator']
        require(e in protocols, 'record has no bound protocol')
        status = bv.validate_record(record, task, protocols[e], protocol_hashes[e], runner, pins['parser_version'])
        if status != 'excluded':
            require(datetime.datetime.fromisoformat(record['started_at_utc']) >= frozen_time, 'new judgment predates frozen five-level plan')
        by_key[key] = (record, status)
    missing = sorted(set(task_map) - set(by_key))
    require(allow_incomplete or not missing, f'{condition}: missing {len(missing)} planned records; explicit --allow-incomplete required')
    all_judged = len(by_key) == len(tasks) and all(status != 'excluded' for _, status in by_key.values())
    require(all_judged or not (run_dir / '_mirror' / 'RUN_MIRROR_COMPLETE.json').exists(), 'full judged-complete checkpoint conflicts with missing/excluded records')
    checkpoint_sha = verify_checkpoint(run_dir, tasks, required=all_judged)
    rows = [row_from_task(t, *by_key.get(t['task_key'], ({}, 'missing')), identity['run_id'], checkpoint_sha) for t in tasks]
    metadata = {'condition': condition, 'source_run_id': identity['run_id'], 'tasks_sha256': sha(canonical(tasks)),
                'protocol_sha256': protocol_hashes, 'environment_sha256': sha(canonical(environment)),
                'full_checkpoint_sha256': checkpoint_sha, 'records_present': len(records), 'missing_tasks': missing,
                'input_provenance': provenance, 'run_identity_sha256': sha(canonical(identity))}
    return condition, rows, metadata


def holm_ten(p_values):
    require(len(p_values) == 10, 'primary family must retain exactly 10 tests')
    require(all(p is None or (type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1) for p in p_values), 'invalid p-value')
    order = sorted(range(10), key=lambda i: (1 if p_values[i] is None else p_values[i], i))
    adjusted, ranks, running = [None] * 10, [None] * 10, 0.0
    for rank, i in enumerate(order):
        p = 1 if p_values[i] is None else p_values[i]
        running = max(running, min(1.0, (10 - rank) * p))
        ranks[i] = rank + 1
        if p_values[i] is not None:
            adjusted[i] = running
    return adjusted, ranks


def paired_bootstrap(differences, condition, evaluator):
    require((condition, evaluator) in FAMILY, 'bootstrap contrast outside frozen family')
    require(all(type(d) is int and d in (-1, 0, 1) for d in differences), 'invalid paired differences')
    seed = int.from_bytes(hashlib.sha256(('standard159-levels-v1:42:' + condition + ':' + evaluator).encode()).digest()[:8], 'big')
    values = np.asarray(differences, dtype=np.int64)
    if not len(values):
        return {'risk_difference': None, 'ci95_low': None, 'ci95_high': None, 'bootstrap_seed': seed}
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(0, len(values), size=(REPLICATES, len(values)))
    quantiles = np.quantile(values[indices].mean(axis=1), [0.025, 0.975], method='linear')
    return {'risk_difference': float(values.mean()), 'ci95_low': float(quantiles[0]), 'ci95_high': float(quantiles[1]), 'bootstrap_seed': seed}


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(rows, metadata):
    require(len(rows) == TOTAL_N and len({r['task_key'] for r in rows}) == TOTAL_N, 'summary requires all 1908 aligned expected rows')
    by_key = {(r['behavior_id'], r['condition'], r['evaluator']): r for r in rows}
    ids = sorted({r['behavior_id'] for r in rows})
    require(len(ids) == N_IDS, 'summary behavior ID inventory mismatch')
    tables = {k: [] for k in ('condition_rates', 'paired_results', 'pair_status_counts', 'legacy_transitions', 'legacy_agreement', 'judge_transitions', 'judge_disagreement')}
    tables['record_comparisons'] = sorted(rows, key=lambda r: (ALL_CONDITIONS.index(r['condition']), EVALUATORS.index(r['evaluator']), r['behavior_id']))
    warnings = [
        'Prospectively frozen exploratory analysis, not preregistered or confirmatory; old corpus and FP16/SP70 results were previously explored.',
        'Judge labels, legacy agreement, and cross-judge agreement are not human-validated accuracy; human validation is deferred.',
        'Fixed standard159 subset and saved generation seed42 only: no population-wide or pruning-causal claims.',
        'Primary analyses condition on complete valid binary pairs; missing/nonbinary selection can bias estimates. No imputation.',
        'Ten contrasts reuse the same previous-day FP16 baseline; Holm10 controls the fixed test family without an independence assumption.',
        'Bootstrap intervals are nominal95% per contrast, not multiplicity-adjusted or simultaneous across ten contrasts.',
        'Trend, legacy transitions, and judge disagreement are descriptive only; no additional trend/subgroup/threshold p-values.',
        'Prior-day runtime baseline reuse remains a comparability limitation even with equal pinned scientific settings.'
    ]
    for c in ALL_CONDITIONS:
        reused = c == 'FP16'
        for e in EVALUATORS:
            subset = [by_key[(bid, c, e)] for bid in ids]
            counts = collections.Counter(r['new_status'] for r in subset)
            valid = counts['safe'] + counts['unsafe']
            tables['condition_rates'].append({'condition': c, 'evaluator': e, 'is_reused_baseline': reused,
                'planned': N_IDS, 'records_present': N_IDS - counts['missing'], 'judged': valid + counts['invalid'] + counts['abstain'],
                **{s: counts[s] for s in STATUSES}, 'valid_binary': valid, 'unsafe_rate_valid': rate(counts['unsafe'], valid)})
            transitions = collections.Counter((r['legacy_label'], r['new_status']) for r in subset)
            for legacy in (0, 1):
                for status in STATUSES:
                    tables['legacy_transitions'].append({'condition': c, 'evaluator': e, 'is_reused_baseline': reused,
                        'legacy_label': legacy, 'new_status': status, 'n': transitions[(legacy, status)]})
            agreed = sum(r['legacy_agrees'] is True for r in subset)
            tables['legacy_agreement'].append({'condition': c, 'evaluator': e, 'is_reused_baseline': reused,
                'planned': N_IDS, 'valid_binary': valid, 'agreement_n': agreed, 'disagreement_n': valid - agreed,
                'agreement_rate_valid': rate(agreed, valid), 'nonbinary_or_missing': N_IDS - valid})
        transitions, binary_pairs = collections.Counter(), []
        for bid in ids:
            hb, lg = (by_key[(bid, c, e)] for e in EVALUATORS)
            require(hb['response_sha256'] == lg['response_sha256'], 'cross-judge response misbinding')
            transitions[(hb['new_status'], lg['new_status'])] += 1
            if hb['new_label_binary'] is not None and lg['new_label_binary'] is not None:
                binary_pairs.append((hb['new_label_binary'], lg['new_label_binary']))
        for hb_status in STATUSES:
            for lg_status in STATUSES:
                tables['judge_transitions'].append({'condition': c, 'is_reused_baseline': reused,
                    'HB_status': hb_status, 'LG_status': lg_status, 'n': transitions[(hb_status, lg_status)]})
        binary = collections.Counter(binary_pairs); n = len(binary_pairs); disagree = sum(hb != lg for hb, lg in binary_pairs)
        tables['judge_disagreement'].append({'condition': c, 'is_reused_baseline': reused, 'planned': N_IDS,
            'mutually_valid': n, 'nonbinary_or_missing': N_IDS - n, 'disagreement_n': disagree, 'disagreement_rate_valid': rate(disagree, n),
            'both_safe_n00': binary[(0, 0)], 'HB_safe_LG_unsafe_n01': binary[(0, 1)], 'HB_unsafe_LG_safe_n10': binary[(1, 0)], 'both_unsafe_n11': binary[(1, 1)]})
    for order, (c, e) in enumerate(FAMILY, 1):
        counts, pairs, nonvalid = collections.Counter(), [], []
        for bid in ids:
            baseline, current = by_key[(bid, 'FP16', e)], by_key[(bid, c, e)]
            require(baseline['row_index'] == current['row_index'], 'baseline/new row misbinding')
            counts[(baseline['new_status'], current['new_status'])] += 1
            fp, new = baseline['new_label_binary'], current['new_label_binary']
            if fp is not None and new is not None:
                pairs.append((fp, new))
            else:
                nonvalid.append({'behavior_id': bid, 'FP16_status': baseline['new_status'], 'condition_status': current['new_status']})
        for fp_status in STATUSES:
            for status in STATUSES:
                tables['pair_status_counts'].append({'condition': c, 'evaluator': e, 'FP16_status': fp_status, 'condition_status': status, 'n': counts[(fp_status, status)]})
        binary = collections.Counter(pairs); b, d, n = binary[(0, 1)], binary[(1, 0)], len(pairs)
        tables['paired_results'].append({'family_order': order, 'condition': c, 'evaluator': e, 'baseline': 'FP16',
            'baseline_is_reused': True, 'planned_pairs': N_IDS, 'valid_pairs': n, 'nonvalid_pairs': N_IDS - n,
            'both_safe_n00': binary[(0, 0)], 'b_increase_n01': b, 'c_decrease_n10': d, 'both_unsafe_n11': binary[(1, 1)],
            'FP16_unsafe_rate_paired': rate(sum(fp for fp, _ in pairs), n), 'condition_unsafe_rate_paired': rate(sum(new for _, new in pairs), n),
            **paired_bootstrap([new - fp for fp, new in pairs], c, e), 'bootstrap_replicates': REPLICATES,
            'ci_scope': 'nominal95%; not multiplicity-adjusted or simultaneous', 'p_exact_two_sided': mcnemar_exact(b, d, n),
            'nonvalid_pair_details': nonvalid})
        if nonvalid:
            warnings.append(f'{c}/{e}: {N_IDS-n} nonvalid/missing pairs; only {n} complete valid pairs enter this contrast.')
        if not n:
            warnings.append(f'{c}/{e}: no valid pairs; estimates/p-values null, but the slot remains in Holm10.')
    adjusted, ranks = holm_ten([row['p_exact_two_sided'] for row in tables['paired_results']])
    for row, p, rank in zip(tables['paired_results'], adjusted, ranks):
        row.update(p_holm_ten_test_family=p, holm_sorted_rank=rank, reject_holm_at_0_05=None if p is None else p <= 0.05)
    if metadata['new_missing_count']:
        warnings.append(f"PROVISIONAL INCOMPLETE: {metadata['new_missing_count']} of1590 new records missing; all ten family slots retained.")
    return {'schema': 'standard159-levels-analysis-v1', 'analysis_type': 'prospectively frozen exploratory',
            'primary_family_size': 10, 'alpha': 0.05, 'metadata': metadata, 'tables': tables, 'warnings': warnings}


def analyze(run_dirs, baseline_dir, baseline_archive, input_zip, runner_path, runner_sha, baseline_runner_path, plan_path, allow_incomplete=False, wrapper_sha=None):
    plan = read_plan(plan_path)
    require(isinstance(wrapper_sha, str) and re.fullmatch(r"[0-9a-f]{64}", wrapper_sha), "trusted reviewed wrapper SHA required")
    require(Path(input_zip).stat().st_size == plan['scope']['input_zip_bytes'] and sha(Path(input_zip).read_bytes()) == ZIP_SHA, 'verified input ZIP size/hash mismatch')
    baseline_rows, baseline_protocols, baseline_meta = load_baseline(baseline_dir, baseline_archive, input_zip, baseline_runner_path, plan)
    parser_sha = plan['baseline_integrity']['parser_sha256']
    runner, parser = bv.load_runner(runner_path, runner_sha, parser_sha)
    expected = {c: runner.inputs(input_zip, c) for c in CONDITIONS}
    all_tasks = [t for c in CONDITIONS for t in expected[c][0]]
    validate_tasks(all_tasks, all_tasks, CONDITIONS)
    require({r['behavior_id'] for r in baseline_rows} == {t['behavior_id'] for t in all_tasks}, 'baseline/new canonical ID mismatch')
    pins = {'runner_sha256': runner_sha, 'parser_sha256': parser_sha, 'parser_version': parser.VERSION, 'wrapper_sha256': wrapper_sha}
    rows, runs, seen_paths, seen_ids = list(baseline_rows), {}, set(), set()
    for directory in run_dirs:
        path = Path(directory).resolve()
        require(path not in seen_paths, 'duplicate run path')
        seen_paths.add(path)
        condition, run_rows, meta = validate_new_run(path, expected, baseline_protocols, runner, pins, plan, baseline_meta, allow_incomplete)
        require(condition not in runs, 'duplicate/conflicting condition runs')
        require(meta['source_run_id'] not in seen_ids, 'duplicate run ID')
        runs[condition] = meta; seen_ids.add(meta['source_run_id']); rows.extend(run_rows)
    missing_conditions = [c for c in CONDITIONS if c not in runs]
    require(allow_incomplete or not missing_conditions, 'missing whole condition runs: ' + ','.join(missing_conditions))
    for c in missing_conditions:
        rows.extend(row_from_task(t, {}, 'missing', None, None) for t in expected[c][0])
    new_rows = [r for r in rows if not r['is_reused_baseline']]
    counts = collections.Counter(r['new_status'] for r in new_rows)
    require(len(new_rows) == NEW_N and len(rows) == TOTAL_N, 'aggregate analysis scope mismatch')
    judged = sum(counts[s] for s in STATUSES[:4]); valid = counts['safe'] + counts['unsafe']
    metadata = {'analysis_plan_sha256': PLAN_SHA, 'analysis_code_sha256': sha(Path(__file__).read_bytes()),
        'baseline_validator_sha256': BASELINE_VALIDATOR_SHA, 'input_zip_sha256': ZIP_SHA,
        'trusted_new_runner_parser_pins': pins, 'python_version': platform.python_version(), 'numpy_version': np.__version__,
        'baseline': baseline_meta, 'runs': runs, 'expected_new_records': NEW_N, 'reused_baseline_records': BASELINE_N,
        'total_analysis_records': TOTAL_N, 'new_records_present': NEW_N-counts['missing'], 'new_missing_count': counts['missing'],
        'new_judged_count': judged, 'new_valid_binary_count': valid, 'new_excluded_count': counts['excluded'],
        'new_invalid_count': counts['invalid'], 'new_abstain_count': counts['abstain'],
        'task_accounted_complete': counts['missing'] == 0, 'requested_new_evaluation_complete': judged == NEW_N,
        'all_new_binary_valid': valid == NEW_N, 'missing_whole_conditions': missing_conditions,
        'missing_new_tasks': sorted(r['task_key'] for r in new_rows if r['new_status'] == 'missing'), 'allow_incomplete': allow_incomplete,
        'all_new_tasks_sha256': sha(canonical(all_tasks)), 'SP70_in_today_analysis': False}
    return summarize(rows, metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', action='append', default=[], help='Repeat for each condition run; no condition may occur twice')
    parser.add_argument('--baseline-dir', required=True)
    parser.add_argument('--baseline-archive', required=True)
    parser.add_argument('--baseline-runner', required=True)
    parser.add_argument('--zip', required=True, dest='input_zip')
    parser.add_argument('--runner', required=True)
    parser.add_argument('--runner-sha256', required=True)
    parser.add_argument('--wrapper-sha256', required=True)
    parser.add_argument('--plan', default=str(Path(__file__).with_name('analysis_plan.json')))
    parser.add_argument('--allow-incomplete', action='store_true')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    result = analyze(args.run_dir, args.baseline_dir, args.baseline_archive, args.input_zip, args.runner, args.runner_sha256,
                     args.baseline_runner, args.plan, args.allow_incomplete, args.wrapper_sha256)
    bv.write_outputs(result, args.out)
    meta = result['metadata']
    print(json.dumps({'output': args.out, **{k: meta[k] for k in ('expected_new_records', 'new_records_present', 'new_judged_count',
        'new_valid_binary_count', 'new_missing_count', 'new_excluded_count', 'reused_baseline_records', 'task_accounted_complete',
        'requested_new_evaluation_complete', 'all_new_binary_valid', 'analysis_plan_sha256')}}))


if __name__ == '__main__':
    main()
