#!/usr/bin/env python3
"""Offline-only, prospective exploratory standard159 analysis (stdlib + NumPy).

Imports a separately reviewed/pinned runner for source-task and raw-parser binding.
Never loads models, accesses network/authentication, or uses GPU APIs.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys
import numpy as np

PLAN_SHA = 'ea8e753776999b6b28868f9f692d8b6459685f598de1677c8802bfe98f776dfa'
ZIP_SHA = 'dd8e84fe8a6e1d4d6f460ab5cb27f1f4650f90f162f99450e8766a5c8254d482'
EVALUATORS = ('HB', 'LG')
CONDITIONS = ('FP16', 'SP70')
STATUSES = ('safe', 'unsafe', 'invalid', 'abstain', 'excluded', 'missing')
BINARY = {'safe': 0, 'unsafe': 1}
N_IDS = 159
N_TASKS = 636
BOOTSTRAP_REPLICATES = 20000
PROTOCOL_NAME = 'new-standard159-v1; not historical judge reproduction'
DECODER = {'parser_input_skip_special_tokens': True, 'full_raw_skip_special_tokens': False,
           'clean_up_tokenization_spaces': False, 'strip': False}
TOKEN_POLICY = 'HB right clip generation512 encode/decode, full prompt left2048; LG no truncate cap8192'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf8')


def fail(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(path):
    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            fail(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError(f'nonfinite JSON constant: {value}')
    return json.loads(Path(path).read_text(encoding='utf8'), object_pairs_hook=pairs_hook,
                      parse_constant=bad_constant)


def load_runner(path, runner_sha, parser_sha):
    path = Path(path).resolve()
    parser_path = path.with_name('research_parsers.py')
    fail(sha(path.read_bytes()) == runner_sha, 'reviewed runner SHA mismatch')
    fail(sha(parser_path.read_bytes()) == parser_sha, 'reviewed parser SHA mismatch')
    def module_from_path(name, source):
        spec = importlib.util.spec_from_file_location(name, source)
        fail(spec is not None and spec.loader is not None, 'module import unavailable')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    parser_module = module_from_path('research_parsers', parser_path)
    runner = module_from_path('_standard159_reviewed_runner', path)
    for name in ('inputs', 'verify_record', 'parser', 'canonical', 'sha'):
        fail(callable(getattr(runner, name, None)), f'runner API missing {name}')
    fail(runner.canonical({'probe': [True, None, 'é']}) == canonical({'probe': [True, None, 'é']}),
         'canonical encoding contract mismatch')
    return runner, parser_module


def validate_task_scope(tasks, expected_tasks):
    fail(type(tasks) is list and len(tasks) == N_TASKS, 'expected exactly 636 tasks')
    fail(canonical(tasks) == canonical(expected_tasks), 'archived tasks differ from source-rebuilt tasks')
    keys = set()
    groups = collections.defaultdict(dict)
    for task in tasks:
        bid, condition, evaluator = (task.get(x) for x in ('behavior_id', 'condition', 'evaluator'))
        fail(isinstance(bid, str) and bool(bid), 'invalid behavior ID')
        fail(condition in CONDITIONS and evaluator in EVALUATORS, 'task outside condition/evaluator scope')
        fail(type(task.get('source_seed')) is int and task['source_seed'] == 42, 'task seed mismatch')
        key = '|'.join([bid, condition, evaluator, '42'])
        fail(task.get('task_key') == key and key not in keys, 'duplicate or misbound task key')
        keys.add(key)
        fail(type(task.get('legacy_label')) is int and task['legacy_label'] in (0, 1), 'legacy not binary integer')
        fail(isinstance(task.get('response'), str) and task.get('response_sha256') == sha(task['response'].encode()), 'task response hash mismatch')
        fail(type(task.get('row_index')) is int and 0 <= task['row_index'] < 320, 'canonical row index invalid')
        groups[(condition, evaluator)][bid] = task
    id_sets = [set(group) for group in groups.values()]
    fail(len(groups) == 4 and all(len(s) == N_IDS for s in id_sets) and all(s == id_sets[0] for s in id_sets), 'paired-ID inventory mismatch')
    for bid in sorted(id_sets[0]):
        first = groups[('FP16', 'HB')][bid]
        for condition in CONDITIONS:
            hb, lg = (groups[(condition, evaluator)][bid] for evaluator in EVALUATORS)
            fail(hb['response_sha256'] == lg['response_sha256'] and hb['response'] == lg['response'], 'cross-judge response misbinding')
            for task in (hb, lg):
                fail(task['row_index'] == first['row_index'] and task['behavior'] == first['behavior'], 'paired behavior/row misbinding')
    return {task['task_key']: task for task in tasks}


def validate_protocol(protocol, evaluator, tasks, provenance, runner, pins):
    expected_settings = {'seed': 42, 'do_sample': False, 'temperature_inactive': 0,
                         'top_p_inactive': 1, 'max_new_tokens': 1 if evaluator == 'HB' else 128,
                         'dtype': 'float16', 'quantization': 'none'}
    name, revision = runner.MODELS[evaluator]
    expected = {'protocol': PROTOCOL_NAME, 'judge': evaluator, 'model_id': name,
                'model_revision': revision, 'tokenizer_revision': revision,
                'tasks_sha256': sha(canonical(tasks)), 'inputs': provenance,
                'runner_code_sha256': pins['runner_sha256'], 'parser_code_sha256': pins['parser_sha256'],
                'parser_version': pins['parser_version'], 'analysis_plan_sha256': PLAN_SHA,
                'token_policy': TOKEN_POLICY, 'settings': expected_settings,
                'target_research_model': 'Meta-Llama-3-8B-Instruct; saved responses only, not loaded',
                'model_execution_authorized': True}
    for key, value in expected.items():
        fail(canonical(protocol.get(key)) == canonical(value), f'{evaluator} protocol mismatch: {key}')
    fail(protocol.get('auth_mode') in ('anonymous', 'ephemeral_explicit_read_token'), 'unexpected protocol auth mode')
    template = protocol.get('template')
    fail(isinstance(template, str) and bool(template) and protocol.get('template_sha256') == sha(template.encode()), 'protocol template hash mismatch')
    if evaluator == 'HB':
        fail(template == runner.HB_TEMPLATE and protocol['template_sha256'] == runner.HB_TEMPLATE_SHA, 'HB official template mismatch')
    fail(isinstance(protocol.get('environment'), dict), 'protocol environment absent')
    return sha(canonical(protocol))


def validate_record(record, task, protocol, protocol_sha, runner, parser_version):
    runner.verify_record(record, task, protocol_sha)
    for field in ('source_seed', 'judge_seed'):
        fail(type(record.get(field)) is int and record[field] == 42, f'record {field} mismatch')
    fail(type(record.get('legacy_label')) is int, 'record legacy label type mismatch')
    for field in ('model_revision', 'tokenizer_revision', 'template_sha256', 'parser_version'):
        fail(record.get(field) == protocol[field], f'record protocol field mismatch: {field}')
    fail(record.get('observed_config_commit') in (None, protocol['model_revision']), 'observed model revision mismatch')
    prompt = record.get('serialized_input_before_prompt_truncation')
    fail(isinstance(prompt, str) and record.get('serialized_input_sha256') == sha(prompt.encode()), 'serialized prompt hash mismatch')
    ids = record.get('input_token_ids')
    fail(type(ids) is list and bool(ids) and all(type(i) is int and i >= 0 for i in ids), 'invalid input token IDs')
    fail(type(record.get('input_tokens')) is int and record['input_tokens'] == len(ids), 'input token count mismatch')
    fail(record.get('input_token_ids_sha256') == sha(canonical(ids)), 'input token hash mismatch')
    policy = record.get('token_policy')
    fail(isinstance(policy, dict), 'record token policy missing')
    if task['evaluator'] == 'LG':
        fail(policy.get('apply_chat_template_return_dict') is False and policy.get('input_ids_contract') == 'nonempty flat list[int]', 'LG token serialization contract mismatch')
        if record['status'] == 'judged':
            fail(set(policy) == {'truncation', 'apply_chat_template_return_dict', 'input_ids_contract'} and policy['truncation'] == 'none; conversation user behavior then assistant stored response', 'LG truncation policy mismatch')
        else:
            fail(set(policy) == {'exclude_reason', 'apply_chat_template_return_dict', 'input_ids_contract'}, 'LG exclusion token policy mismatch')
    else:
        fail(set(policy) == {'response_clip_tokens', 'clipped_response_sha256', 'full_prompt_left_truncated'}, 'HB token policy keys mismatch')
        fail(type(policy['response_clip_tokens']) is int and 0 <= policy['response_clip_tokens'] <= 512 and type(policy['full_prompt_left_truncated']) is bool, 'HB clipping policy mismatch')
        prefix, suffix = runner.HB_TEMPLATE.split('{generation}')
        prefix, suffix = prefix.format(behavior=task['behavior']), suffix.format(behavior=task['behavior'])
        fail(prompt.startswith(prefix) and prompt.endswith(suffix), 'HB prompt task/template binding mismatch')
        clipped = prompt[len(prefix):len(prompt) - len(suffix)] if suffix else prompt[len(prefix):]
        fail(policy['clipped_response_sha256'] == sha(clipped.encode()), 'HB clipped response hash mismatch')
    if record['status'] == 'excluded':
        fail(task['evaluator'] == 'LG' and len(ids) > 8192 and policy.get('exclude_reason') == 'LG_input_over_8192_no_truncation', 'unexpected exclusion')
        fail(record.get('output_tokens') == 0 and type(record.get('output_tokens')) is int, 'excluded record output count')
        for field in ('raw_judge_completion', 'raw_judge_sha256', 'parsed', 'new_label_binary', 'legacy_changed', 'started_at_utc', 'ended_at_utc', 'output_token_ids',
                      'raw_decoded_with_special_tokens', 'raw_decoded_with_special_tokens_sha256', 'decoder_settings'):
            fail(record.get(field) is None, f'excluded record has unexpected {field}')
        return 'excluded'
    fail(record['status'] == 'judged' and 'exclude_reason' not in policy, 'judged/exclusion conflict')
    if task['evaluator'] == 'LG':
        fail(len(ids) <= 8192, 'LG judged over context cap')
    else:
        fail(len(ids) <= 2048, 'HB judged over context cap')
    parsed = record.get('parsed')
    fail(isinstance(parsed, dict) and parsed.get('parser_version') == parser_version and parsed.get('label') in STATUSES[:4], 'invalid parsed status')
    status = parsed['label']
    binary = BINARY.get(status)
    fail(record.get('new_label_binary') == binary and (binary is None or type(record.get('new_label_binary')) is int), 'new binary label does not match raw parser')
    changed = None if binary is None else binary != task['legacy_label']
    fail(record.get('legacy_changed') == changed and (changed is None or type(record.get('legacy_changed')) is bool), 'legacy change flag mismatch')
    fail(record.get('decoder_settings') == DECODER, 'decoder settings mismatch')
    output_ids = record.get('output_token_ids')
    fail(type(output_ids) is list and all(type(i) is int and i >= 0 for i in output_ids), 'invalid output token IDs')
    fail(type(record.get('output_tokens')) is int and len(output_ids) == record['output_tokens'] and 0 < len(output_ids) <= protocol['settings']['max_new_tokens'], 'output token count mismatch')
    times = []
    for key in ('started_at_utc', 'ended_at_utc'):
        fail(isinstance(record.get(key), str) and bool(record[key]), 'judgment time missing')
        parsed_time = datetime.datetime.fromisoformat(record[key])
        fail(parsed_time.tzinfo is not None, 'judgment timestamp must be timezone-aware')
        times.append(parsed_time)
    fail(times[0] <= times[1] and times[0] >= datetime.datetime.fromisoformat('2026-10-29T07:24:00+00:00'), 'judgment time order or pre-plan timestamp')
    return status


def validate_dataset(tasks, expected_tasks, records, protocols, provenance, runner, pins, allow_incomplete=False):
    """Validate without dropping any record. Returns aligned rows and integrity metadata."""
    task_map = validate_task_scope(tasks, expected_tasks)
    fail(set(protocols) <= set(EVALUATORS), 'unexpected evaluator protocol')
    protocol_hashes = {e: validate_protocol(p, e, tasks, provenance, runner, pins) for e, p in protocols.items()}
    fail(allow_incomplete or set(protocols) == set(EVALUATORS), 'both evaluator protocols required')
    record_map = {}
    for record in records:
        key = record.get('task_key')
        fail(key in task_map, 'unexpected record outside fixed task membership')
        fail(key not in record_map, 'duplicate/conflicting result task key')
        task = task_map[key]
        evaluator = task['evaluator']
        fail(evaluator in protocols, 'record has no bound protocol')
        status = validate_record(record, task, protocols[evaluator], protocol_hashes[evaluator], runner, pins['parser_version'])
        record_map[key] = (record, status)
    missing = sorted(set(task_map) - set(record_map))
    fail(allow_incomplete or not missing, f'missing {len(missing)} of 636 planned records; explicit --allow-incomplete required')
    rows = []
    for task in sorted(tasks, key=lambda t: (t['behavior_id'], t['condition'], t['evaluator'])):
        record, status = record_map.get(task['task_key'], ({}, 'missing'))
        new = BINARY.get(status)
        rows.append({'task_key': task['task_key'], 'behavior_id': task['behavior_id'], 'row_index': task['row_index'],
                     'condition': task['condition'], 'evaluator': task['evaluator'], 'source_seed': 42,
                     'response_sha256': task['response_sha256'], 'legacy_label': task['legacy_label'],
                     'new_status': status, 'new_label_binary': new,
                     'legacy_agrees': None if new is None else new == task['legacy_label'],
                     'task_sha256': sha(canonical(task)), 'protocol_sha256': record.get('protocol_sha256'),
                     'content_sha256': record.get('content_sha256'), 'raw_judge_completion': record.get('raw_judge_completion'),
                     'raw_judge_sha256': record.get('raw_judge_sha256'),
                     'nonbinary_reason': ('missing' if status == 'missing' else record.get('token_policy', {}).get('exclude_reason')
                                          if status == 'excluded' else record.get('parsed', {}).get('reason') if new is None else None)})
    status_counts = collections.Counter(row['new_status'] for row in rows)
    judged_count = sum(status_counts[s] for s in STATUSES[:4])
    valid_count = status_counts['safe'] + status_counts['unsafe']
    metadata = {'expected_tasks': N_TASKS, 'records_present': len(record_map), 'missing_tasks': missing,
                'judged_count': judged_count, 'valid_binary_count': valid_count, 'excluded_count': status_counts['excluded'],
                'requested_evaluation_complete': judged_count == N_TASKS, 'all_binary_valid': valid_count == N_TASKS,
                'task_accounted_complete': not missing, 'protocol_sha256': protocol_hashes,
                'tasks_sha256': sha(canonical(tasks)), 'source_provenance': provenance,
                'trusted_pins': pins, 'analysis_plan_sha256': PLAN_SHA}
    return rows, metadata


def mcnemar_exact(b, c, n_valid):
    fail(all(type(x) is int and x >= 0 for x in (b, c, n_valid)) and b + c <= n_valid, 'invalid paired counts')
    if n_valid == 0:
        return None
    discordant = b + c
    return min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(b, c) + 1)) / (2 ** discordant))


def holm_two(p_values):
    fail(len(p_values) == 2, 'primary family must have exactly two tests')
    fail(all(p is None or (isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1) for p in p_values), 'invalid p-value')
    adjusted = [None, None]
    order = sorted(range(2), key=lambda i: (1.0 if p_values[i] is None else p_values[i], i))
    running_max = 0.0
    for rank, i in enumerate(order):
        p = 1.0 if p_values[i] is None else p_values[i]
        running_max = max(running_max, min(1.0, (2 - rank) * p))
        if p_values[i] is not None:
            adjusted[i] = running_max
    return adjusted


def paired_bootstrap(differences, evaluator):
    fail(evaluator in EVALUATORS, 'unexpected bootstrap evaluator')
    values = np.asarray(differences, dtype=np.int64)
    fail(values.ndim == 1 and bool(np.all(np.isin(values, [-1, 0, 1]))), 'invalid paired differences')
    seed = int.from_bytes(hashlib.sha256(('standard159-v1:42:' + evaluator).encode('utf8')).digest()[:8], 'big')
    if len(values) == 0:
        return {'risk_difference': None, 'ci95_low': None, 'ci95_high': None, 'bootstrap_seed': seed}
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = rng.integers(0, len(values), size=(BOOTSTRAP_REPLICATES, len(values)))
    replicates = values[indices].mean(axis=1)
    low, high = np.quantile(replicates, [0.025, 0.975], method='linear')
    return {'risk_difference': float(values.mean()), 'ci95_low': float(low), 'ci95_high': float(high), 'bootstrap_seed': seed}


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(rows, metadata):
    fail(len(rows) == N_TASKS and len({r['task_key'] for r in rows}) == N_TASKS, 'summary requires aligned 636-row validated scope')
    by_key = {(r['behavior_id'], r['condition'], r['evaluator']): r for r in rows}
    ids = sorted({r['behavior_id'] for r in rows})
    tables = {'condition_rates': [], 'paired_results': [], 'pair_status_counts': [], 'legacy_transitions': [],
              'legacy_agreement': [], 'judge_transitions': [], 'judge_disagreement': [], 'record_comparisons': rows}
    warnings = [
        'Prospectively frozen exploratory analysis; not preregistered or confirmatory. Legacy corpus and smoke were previously explored.',
        'Judge labels are not human-validated accuracy. Legacy agreement and cross-judge agreement are not accuracy.',
        'Fixed standard159 benchmark subset, saved generation seed 42 only. No population-wide or pruning-causal claims.',
        'Primary analyses use complete valid binary pairs without imputation. Nonbinary/missing selection can bias the valid-pair subset.',
        'Paired-bootstrap 95% intervals are nominal per evaluator and are not multiplicity-adjusted or simultaneous.'
    ]
    if not metadata['task_accounted_complete']:
        warnings.append(f"PROVISIONAL INCOMPLETE ANALYSIS: {len(metadata['missing_tasks'])} of 636 planned records missing.")
    for e in EVALUATORS:
        for condition in CONDITIONS:
            subset = [r for r in rows if r['evaluator'] == e and r['condition'] == condition]
            counts = collections.Counter(r['new_status'] for r in subset)
            valid = counts['safe'] + counts['unsafe']
            tables['condition_rates'].append({'evaluator': e, 'condition': condition, 'planned': N_IDS,
                'records_present': N_IDS - counts['missing'], 'judged': valid + counts['invalid'] + counts['abstain'],
                **{status: counts[status] for status in STATUSES}, 'valid_binary': valid,
                'unsafe_rate_valid': rate(counts['unsafe'], valid)})
            trans = collections.Counter((r['legacy_label'], r['new_status']) for r in subset)
            for legacy in (0, 1):
                for status in STATUSES:
                    tables['legacy_transitions'].append({'evaluator': e, 'condition': condition,
                        'legacy_label': legacy, 'new_status': status, 'n': trans[(legacy, status)]})
            agreed = sum(r['legacy_agrees'] is True for r in subset)
            tables['legacy_agreement'].append({'evaluator': e, 'condition': condition, 'planned': N_IDS,
                'valid_binary': valid, 'agreement_n': agreed, 'disagreement_n': valid - agreed,
                'agreement_rate_valid': rate(agreed, valid), 'nonbinary_or_missing': N_IDS - valid})
        pair_counts = collections.Counter()
        pairs = []
        excluded_pairs = []
        for bid in ids:
            fp, sp = (by_key[(bid, c, e)] for c in CONDITIONS)
            pair_counts[(fp['new_status'], sp['new_status'])] += 1
            if fp['new_label_binary'] is not None and sp['new_label_binary'] is not None:
                pairs.append((bid, fp['new_label_binary'], sp['new_label_binary']))
            else:
                excluded_pairs.append({'behavior_id': bid, 'FP16_status': fp['new_status'], 'SP70_status': sp['new_status']})
        for fp_status in STATUSES:
            for sp_status in STATUSES:
                tables['pair_status_counts'].append({'evaluator': e, 'FP16_status': fp_status, 'SP70_status': sp_status,
                                                    'n': pair_counts[(fp_status, sp_status)]})
        binary_counts = collections.Counter((fp, sp) for _, fp, sp in pairs)
        b, c, n = binary_counts[(0, 1)], binary_counts[(1, 0)], len(pairs)
        bootstrap = paired_bootstrap([sp - fp for _, fp, sp in pairs], e)
        tables['paired_results'].append({'evaluator': e, 'planned_pairs': N_IDS, 'valid_pairs': n,
            'nonvalid_pairs': N_IDS - n, 'both_safe_n00': binary_counts[(0, 0)], 'b_increase_n01': b,
            'c_decrease_n10': c, 'both_unsafe_n11': binary_counts[(1, 1)],
            'FP16_unsafe_rate_paired': rate(sum(fp for _, fp, _ in pairs), n),
            'SP70_unsafe_rate_paired': rate(sum(sp for _, _, sp in pairs), n), **bootstrap,
            'ci_scope': 'nominal 95%; not multiplicity adjusted', 'bootstrap_replicates': BOOTSTRAP_REPLICATES,
            'p_exact_two_sided': mcnemar_exact(b, c, n), 'nonvalid_pair_details': excluded_pairs})
        if excluded_pairs:
            warnings.append(f'{e}: {len(excluded_pairs)} of 159 pairs are nonbinary or missing; primary analysis includes {n} complete valid pairs only.')
        if n == 0:
            warnings.append(f'{e}: no valid pairs; risk difference, interval, and primary p-value are not estimable.')
    adjusted = holm_two([r['p_exact_two_sided'] for r in tables['paired_results']])
    for row, p in zip(tables['paired_results'], adjusted):
        row['p_holm_two_test_family'] = p
        row['reject_holm_at_0_05'] = None if p is None else p <= 0.05
    for condition in CONDITIONS:
        transitions = collections.Counter()
        mutually_valid = []
        for bid in ids:
            hb, lg = (by_key[(bid, condition, e)] for e in EVALUATORS)
            fail(hb['response_sha256'] == lg['response_sha256'], 'summary cross-judge response mismatch')
            transitions[(hb['new_status'], lg['new_status'])] += 1
            if hb['new_label_binary'] is not None and lg['new_label_binary'] is not None:
                mutually_valid.append((hb['new_label_binary'], lg['new_label_binary']))
        for hb_status in STATUSES:
            for lg_status in STATUSES:
                tables['judge_transitions'].append({'condition': condition, 'HB_status': hb_status, 'LG_status': lg_status,
                                                   'n': transitions[(hb_status, lg_status)]})
        binary = collections.Counter(mutually_valid)
        n = len(mutually_valid)
        disagreement = sum(hb != lg for hb, lg in mutually_valid)
        tables['judge_disagreement'].append({'condition': condition, 'planned': N_IDS, 'mutually_valid': n,
            'nonbinary_or_missing': N_IDS - n, 'disagreement_n': disagreement,
            'disagreement_rate_valid': rate(disagreement, n), 'both_safe_n00': binary[(0, 0)],
            'HB_safe_LG_unsafe_n01': binary[(0, 1)], 'HB_unsafe_LG_safe_n10': binary[(1, 0)], 'both_unsafe_n11': binary[(1, 1)]})
    return {'schema': 'standard159-analysis-v1', 'analysis_type': 'prospectively frozen exploratory',
            'metadata': metadata, 'primary_family_size': 2, 'alpha': 0.05,
            'tables': tables, 'warnings': warnings}


def analyze_directory(run_dir, input_zip, runner_path, plan_path, runner_sha, parser_sha, allow_incomplete=False):
    run_dir = Path(run_dir)
    fail(sha(Path(plan_path).read_bytes()) == PLAN_SHA, 'frozen analysis plan SHA mismatch')
    fail(sha(Path(input_zip).read_bytes()) == ZIP_SHA, 'input ZIP pin mismatch')
    runner, parser_module = load_runner(runner_path, runner_sha, parser_sha)
    expected_tasks, provenance = runner.inputs(input_zip)
    tasks = strict_json(run_dir / 'tasks.json')
    fail(canonical(strict_json(run_dir / 'input_provenance.json')) == canonical(provenance), 'archived provenance mismatch')
    archived_plan = run_dir / '_mirror' / 'analysis' / 'analysis_plan.json'
    fail(archived_plan.is_file() and sha(archived_plan.read_bytes()) == PLAN_SHA, 'run archive frozen plan missing or mismatched')
    protocols = {e: strict_json(run_dir / (e + '_protocol.json')) for e in EVALUATORS if (run_dir / (e + '_protocol.json')).exists()}
    environment = strict_json(run_dir / 'environment.json')
    fail(isinstance(environment, dict) and environment.get('precision') == 'fp16', 'archived environment precision mismatch')
    for e, protocol in protocols.items():
        fail(canonical(protocol.get('environment')) == canonical(environment), f'{e} archived environment binding mismatch')
    expected_files = {sha(t['task_key'].encode()) + '.json': t['task_key'] for t in tasks}
    records = []
    records_dir = run_dir / 'records'
    fail(records_dir.is_dir(), 'records directory missing')
    for path in sorted(records_dir.iterdir()):
        fail(path.is_file() and not path.is_symlink() and path.name in expected_files, f'unexpected result path: {path.name}')
        record = strict_json(path)
        fail(record.get('task_key') == expected_files[path.name], 'record filename/task binding mismatch')
        records.append(record)
    pins = {'runner_sha256': runner_sha, 'parser_sha256': parser_sha, 'parser_version': parser_module.VERSION}
    rows, metadata = validate_dataset(tasks, expected_tasks, records, protocols, provenance, runner, pins, allow_incomplete)
    metadata.update({'input_zip_sha256': ZIP_SHA, 'analysis_code_sha256': sha(Path(__file__).read_bytes()),
                     'python_version': platform.python_version(), 'numpy_version': np.__version__,
                     'allow_incomplete': allow_incomplete, 'environment_sha256': sha(canonical(environment))})
    return summarize(rows, metadata)


def write_outputs(result, output_dir):
    output_dir = Path(output_dir)
    fail(not output_dir.exists() or not any(output_dir.iterdir()), 'analysis output directory must be new or empty')
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'analysis.json').write_bytes(canonical(result))
    (output_dir / 'warnings.json').write_bytes(canonical(result['warnings']))
    for name, rows in result['tables'].items():
        fail(bool(rows), f'empty output table: {name}')
        with (output_dir / (name + '.csv')).open('w', encoding='utf8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', required=True)
    p.add_argument('--zip', required=True, dest='input_zip')
    p.add_argument('--runner', required=True)
    p.add_argument('--runner-sha256', required=True, help='Exact independently reviewed trusted runner bytes')
    p.add_argument('--parser-sha256', required=True, help='Exact independently reviewed trusted parser bytes')
    p.add_argument('--plan', default=str(Path(__file__).with_name('analysis_plan.json')))
    p.add_argument('--out', required=True)
    p.add_argument('--allow-incomplete', action='store_true', help='Explicitly permit prominently provisional output with missing expected records')
    args = p.parse_args(argv)
    result = analyze_directory(args.run_dir, args.input_zip, args.runner, args.plan, args.runner_sha256, args.parser_sha256, args.allow_incomplete)
    write_outputs(result, args.out)
    print(json.dumps({'output': str(Path(args.out)), 'records_present': result['metadata']['records_present'],
                      'task_accounted_complete': result['metadata']['task_accounted_complete'],
                      'requested_evaluation_complete': result['metadata']['requested_evaluation_complete'],
                      'all_binary_valid': result['metadata']['all_binary_valid'],
                      'judged_count': result['metadata']['judged_count'],
                      'valid_binary_count': result['metadata']['valid_binary_count'],
                      'excluded_count': result['metadata']['excluded_count'],
                      'analysis_plan_sha256': PLAN_SHA}))


if __name__ == '__main__':
    main()
