"""Synthetic-only tests. No new judgments, models, network, or GPU involved."""
import copy
import contextlib
import io
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import analysis as a

RUNNER_PATH = Path(__file__).with_name('colab_smoke.py')


def fixture(source_tasks=None, source_provenance=None):
    runner_sha = a.sha(RUNNER_PATH.read_bytes())
    parser_sha = a.sha(RUNNER_PATH.with_name('research_parsers.py').read_bytes())
    runner, parser = a.load_runner(RUNNER_PATH, runner_sha, parser_sha)
    pins = {'runner_sha256': runner_sha, 'parser_sha256': parser_sha, 'parser_version': parser.VERSION}
    tasks = []
    for i in range(a.N_IDS):
        bid = f'SYNTHETIC_{i:03d}'
        for condition in a.CONDITIONS:
            response = f'synthetic response {i} {condition}'
            for evaluator in a.EVALUATORS:
                tasks.append({'task_key': '|'.join((bid, condition, evaluator, '42')), 'behavior_id': bid,
                    'row_index': i, 'condition': condition, 'evaluator': evaluator, 'source_seed': 42,
                    'behavior': f'synthetic behavior {i}', 'response': response,
                    'response_sha256': a.sha(response.encode()), 'legacy_label': i % 2,
                    'legacy_source_sha256': '0' * 64, 'response_source_sha256': '1' * 64})
    if source_tasks is not None:
        tasks = source_tasks
    provenance = source_provenance if source_provenance is not None else {'zip_sha256': a.ZIP_SHA, 'synthetic_fixture': True}
    protocols = {}
    for e in a.EVALUATORS:
        name, revision = runner.MODELS[e]
        template = runner.HB_TEMPLATE if e == 'HB' else 'synthetic LG template'
        protocols[e] = {'protocol': a.PROTOCOL_NAME, 'auth_mode': 'anonymous',
            'target_research_model': 'Meta-Llama-3-8B-Instruct; saved responses only, not loaded',
            'model_execution_authorized': True, 'judge': e, 'model_id': name, 'model_revision': revision,
            'tokenizer_revision': revision, 'template': template, 'template_sha256': a.sha(template.encode()),
            'environment': {'synthetic': True, 'precision': 'fp16'}, 'settings': {'seed': 42, 'do_sample': False,
                'temperature_inactive': 0, 'top_p_inactive': 1, 'max_new_tokens': 1 if e == 'HB' else 128,
                'dtype': 'float16', 'quantization': 'none'}, 'token_policy': a.TOKEN_POLICY,
            'parser_version': parser.VERSION, 'parser_code_sha256': parser_sha, 'runner_code_sha256': runner_sha,
            'inputs': provenance, 'tasks_sha256': a.sha(a.canonical(tasks)), 'analysis_plan_sha256': a.PLAN_SHA}
    records = []
    for t in tasks:
        e = t['evaluator']
        p = protocols[e]
        # Fixed synthetic pattern, intentionally unrelated to actual results.
        value = int((t['row_index'] % 5 == 0) if t['condition'] == 'FP16' else (t['row_index'] % 3 == 0))
        raw = ('Yes' if value else 'No') if e == 'HB' else ('unsafe\nS1' if value else 'safe')
        prompt = runner.HB_TEMPLATE.format(behavior=t['behavior'], generation='synthetic') if e == 'HB' else 'synthetic'
        policy = {'response_clip_tokens': 1, 'clipped_response_sha256': a.sha(b'synthetic'), 'full_prompt_left_truncated': False} if e == 'HB' else {'truncation': 'none; conversation user behavior then assistant stored response', 'apply_chat_template_return_dict': False, 'input_ids_contract': 'nonempty flat list[int]'}
        record = {'task_key': t['task_key'], 'task_sha256': a.sha(a.canonical(t)),
            'protocol_sha256': a.sha(a.canonical(p)), 'behavior_id': t['behavior_id'], 'condition': t['condition'],
            'evaluator': e, 'source_seed': 42, 'judge_seed': 42, 'response_sha256': t['response_sha256'],
            'legacy_label': t['legacy_label'], 'model_revision': p['model_revision'], 'observed_config_commit': None,
            'tokenizer_revision': p['tokenizer_revision'], 'template_sha256': p['template_sha256'],
            'serialized_input_before_prompt_truncation': prompt, 'serialized_input_sha256': a.sha(prompt.encode()),
            'input_token_ids': [1], 'input_token_ids_sha256': a.sha(a.canonical([1])), 'input_tokens': 1,
            'token_policy': policy, 'parser_version': parser.VERSION, 'status': 'judged',
            'raw_judge_completion': raw, 'raw_judge_sha256': a.sha(raw.encode()),
            'raw_decoded_with_special_tokens': raw, 'raw_decoded_with_special_tokens_sha256': a.sha(raw.encode()),
            'decoder_settings': dict(a.DECODER), 'output_token_ids': [1], 'output_tokens': 1,
            'started_at_utc': '2026-10-29T08:00:00+00:00', 'ended_at_utc': '2026-10-29T08:00:01+00:00',
            'parsed': runner.parser(raw, e), 'new_label_binary': value,
            'legacy_changed': value != t['legacy_label']}
        records.append(rehash(record))
    return tasks, records, protocols, provenance, runner, pins


def rehash(record):
    record['content_sha256'] = a.sha(a.canonical({k: v for k, v in record.items() if k != 'content_sha256'}))
    return record


def replace_raw(record, raw, runner):
    record['raw_judge_completion'] = raw
    record['raw_judge_sha256'] = a.sha(raw.encode())
    record['raw_decoded_with_special_tokens'] = raw
    record['raw_decoded_with_special_tokens_sha256'] = a.sha(raw.encode())
    record['parsed'] = runner.parser(raw, record['evaluator'])
    value = a.BINARY.get(record['parsed']['label'])
    record['new_label_binary'] = value
    record['legacy_changed'] = None if value is None else value != record['legacy_label']
    return rehash(record)


class MathTests(unittest.TestCase):
    def test_known_mcnemar_exact(self):
        self.assertEqual(a.mcnemar_exact(0, 0, 159), 1)
        self.assertEqual(a.mcnemar_exact(1, 0, 1), 1)
        self.assertEqual(a.mcnemar_exact(5, 0, 20), 0.0625)
        self.assertEqual(a.mcnemar_exact(10, 0, 159), 0.001953125)
        self.assertEqual(a.mcnemar_exact(10, 2, 159), 158 / 4096)
        self.assertEqual(a.mcnemar_exact(2, 10, 159), 158 / 4096)
        self.assertIsNone(a.mcnemar_exact(0, 0, 0))
        with self.assertRaises(ValueError): a.mcnemar_exact(1, 1, 1)
        with self.assertRaises(ValueError): a.mcnemar_exact(True, 0, 1)

    def test_holm_fixed_family(self):
        self.assertEqual(a.holm_two([0.01, 0.04]), [0.02, 0.04])
        self.assertEqual(a.holm_two([0.04, 0.01]), [0.04, 0.02])
        self.assertEqual(a.holm_two([0.03, 0.04]), [0.06, 0.06])
        self.assertEqual(a.holm_two([0.8, 0.9]), [1.0, 1.0])
        self.assertEqual(a.holm_two([None, 0.01]), [None, 0.02])
        self.assertEqual(a.holm_two([None, None]), [None, None])
        with self.assertRaises(ValueError): a.holm_two([0.01])
        with self.assertRaises(ValueError): a.holm_two([float('nan'), 0.1])

    def test_bootstrap_determinism_and_paired_effect(self):
        diffs = [-1, 0, 1] * 20 + [1] * 10
        for e in a.EVALUATORS:
            first = a.paired_bootstrap(diffs, e)
            self.assertEqual(first, a.paired_bootstrap(diffs, e))
            self.assertAlmostEqual(first['risk_difference'], 1 / 7)
            self.assertEqual(first['bootstrap_seed'], {'HB': 17581938970599810153, 'LG': 2879546160238122080}[e])
            self.assertEqual((first['ci95_low'], first['ci95_high']), (-4 / 70, 24 / 70))
            self.assertLessEqual(first['ci95_low'], first['risk_difference'])
            self.assertGreaterEqual(first['ci95_high'], first['risk_difference'])
        self.assertNotEqual(a.paired_bootstrap(diffs, 'HB')['bootstrap_seed'], a.paired_bootstrap(diffs, 'LG')['bootstrap_seed'])
        degenerate = a.paired_bootstrap([0] * 159, 'HB')
        self.assertEqual([degenerate[k] for k in ('risk_difference', 'ci95_low', 'ci95_high')], [0, 0, 0])
        one = a.paired_bootstrap([-1], 'LG')
        self.assertEqual([one[k] for k in ('risk_difference', 'ci95_low', 'ci95_high')], [-1, -1, -1])
        empty = a.paired_bootstrap([], 'HB')
        self.assertTrue(all(empty[k] is None for k in ('risk_difference', 'ci95_low', 'ci95_high')))


class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fixture()

    def setUp(self):
        tasks, records, protocols, provenance, runner, pins = self.base
        self.tasks, self.records, self.protocols, self.provenance, self.pins = copy.deepcopy((tasks, records, protocols, provenance, pins))
        self.runner = runner

    def validate(self, **kwargs):
        return a.validate_dataset(self.tasks, self.base[0], self.records, self.protocols,
                                  self.provenance, self.runner, self.pins, **kwargs)

    def test_complete_636_and_all_output_tables(self):
        rows, meta = self.validate()
        self.assertEqual(len(rows), 636)
        self.assertTrue(meta['task_accounted_complete'])
        result = a.summarize(rows, meta)
        self.assertEqual(len(result['tables']['paired_results']), 2)
        for row in result['tables']['paired_results']:
            self.assertEqual(row['valid_pairs'], 159)
            self.assertEqual(row['b_increase_n01'], 42)
            self.assertEqual(row['c_decrease_n10'], 21)
            self.assertAlmostEqual(row['risk_difference'], 21 / 159)
        self.assertEqual(sum(r['n'] for r in result['tables']['legacy_transitions']), 636)
        self.assertEqual(sum(r['n'] for r in result['tables']['judge_transitions']), 318)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'report'
            a.write_outputs(result, target)
            with (target / 'record_comparisons.csv').open(newline='') as f:
                self.assertEqual(len(list(csv.DictReader(f))), 636)
            self.assertEqual(len(list(target.iterdir())), 10)
            with self.assertRaises(ValueError): a.write_outputs(result, target)

    def test_missing_fail_closed_and_explicit_provisional(self):
        self.records.pop(0)
        with self.assertRaisesRegex(ValueError, 'missing 1'): self.validate()
        rows, meta = self.validate(allow_incomplete=True)
        self.assertEqual(len(rows), 636)
        self.assertEqual(sum(r['new_status'] == 'missing' for r in rows), 1)
        result = a.summarize(rows, meta)
        self.assertTrue(any('PROVISIONAL INCOMPLETE' in warning for warning in result['warnings']))
        self.assertEqual(result['tables']['paired_results'][0]['valid_pairs'], 158)

    def test_duplicate_and_conflict(self):
        self.records.append(copy.deepcopy(self.records[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.validate()
        self.records[-1]['new_label_binary'] = 1 - self.records[-1]['new_label_binary']
        rehash(self.records[-1])
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.validate()

    def test_unexpected_record(self):
        self.records[0]['task_key'] = 'OUTSIDE|FP16|HB|42'
        rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'unexpected'): self.validate()

    def test_behavior_and_response_misbinding(self):
        self.records[0]['behavior_id'] = self.records[4]['behavior_id']
        rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'binding'): self.validate()
        self.setUp()
        self.records[0]['response_sha256'] = '9' * 64
        rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'binding'): self.validate()

    def test_changed_archived_task(self):
        self.tasks[0]['legacy_label'] ^= 1
        with self.assertRaisesRegex(ValueError, 'source-rebuilt'): self.validate()

    def test_duplicate_tasks_and_crossjudge_id_binding(self):
        duplicate = copy.deepcopy(self.tasks)
        duplicate[0] = duplicate[1]
        with self.assertRaises(ValueError): a.validate_task_scope(duplicate, duplicate)
        bad = copy.deepcopy(self.tasks)
        bad[1]['response'] = 'changed'; bad[1]['response_sha256'] = a.sha(b'changed')
        with self.assertRaisesRegex(ValueError, 'cross-judge'): a.validate_task_scope(bad, bad)
        bad = copy.deepcopy(self.tasks); bad[2]['row_index'] = 200
        with self.assertRaisesRegex(ValueError, 'paired behavior/row'): a.validate_task_scope(bad, bad)

    def test_binary_flip_rejected_even_with_fresh_content_hash(self):
        self.records[0]['new_label_binary'] ^= 1
        rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'binary label'): self.validate()
        self.setUp(); self.records[0]['new_label_binary'] = True; rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'binary label'): self.validate()

    def test_content_raw_parser_and_label_tampering(self):
        self.records[0]['new_label_binary'] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'): self.validate()
        self.setUp(); self.records[0]['parsed']['label'] = 'safe'; rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'raw/parser'): self.validate()
        self.setUp(); self.records[0]['raw_judge_completion'] = 'No'; rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'raw/parser'): self.validate()

    def test_protocol_mismatch_and_code_plan_pin(self):
        for key, value in [('tasks_sha256', 'f'*64), ('analysis_plan_sha256', 'f'*64),
                           ('runner_code_sha256', 'f'*64), ('model_revision', 'wrong')]:
            self.setUp(); self.protocols['HB'][key] = value
            with self.assertRaisesRegex(ValueError, 'protocol mismatch'): self.validate()
        self.setUp(); self.protocols['LG']['settings']['quantization'] = 'nf4'
        with self.assertRaisesRegex(ValueError, 'settings'): self.validate()
        self.setUp(); self.records[0]['protocol_sha256'] = 'f' * 64; rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'task/protocol'): self.validate()

    def test_model_seed_token_and_legacy_flag_mismatches(self):
        for field, value in [('source_seed', 43), ('judge_seed', 43), ('model_revision', 'wrong'),
                             ('input_token_ids_sha256', 'f'*64), ('input_tokens', 2),
                             ('legacy_changed', not self.records[0]['legacy_changed'])]:
            self.setUp(); self.records[0][field] = value; rehash(self.records[0])
            with self.assertRaises(ValueError): self.validate()

    def test_separate_invalid_abstain_excluded_and_zero_valid(self):
        for record in self.records:
            replace_raw(record, 'not-a-valid-output', self.runner)
        # HB becomes abstain; LG becomes invalid under the actual pinned parser.
        lg = next(r for r in self.records if r['evaluator'] == 'LG')
        for key in ('parsed', 'new_label_binary', 'legacy_changed', 'raw_decoded_with_special_tokens',
                    'raw_decoded_with_special_tokens_sha256', 'decoder_settings', 'output_token_ids'):
            lg.pop(key)
        lg.update(status='excluded', raw_judge_completion=None, raw_judge_sha256=None,
                  output_tokens=0, started_at_utc=None, ended_at_utc=None,
                  input_token_ids=[1]*8193, input_tokens=8193,
                  input_token_ids_sha256=a.sha(a.canonical([1]*8193)),
                  token_policy={'exclude_reason': 'LG_input_over_8192_no_truncation', 'apply_chat_template_return_dict': False, 'input_ids_contract': 'nonempty flat list[int]'})
        rehash(lg)
        rows, meta = self.validate()
        result = a.summarize(rows, meta)
        self.assertEqual(sum(r['new_status'] == 'abstain' for r in rows), 318)
        self.assertEqual(sum(r['new_status'] == 'invalid' for r in rows), 317)
        self.assertEqual(sum(r['new_status'] == 'excluded' for r in rows), 1)
        for row in result['tables']['paired_results']:
            self.assertEqual(row['valid_pairs'], 0)
            self.assertIsNone(row['risk_difference'])
            self.assertIsNone(row['p_exact_two_sided'])
            self.assertIsNone(row['p_holm_two_test_family'])
        for row in result['tables']['condition_rates']:
            self.assertIsNone(row['unsafe_rate_valid'])
        self.assertEqual(meta['judged_count'], 635)
        self.assertEqual(meta['valid_binary_count'], 0)
        self.assertFalse(meta['requested_evaluation_complete'])
        self.assertFalse(meta['all_binary_valid'])
        lg['output_token_ids'] = [1]; rehash(lg)
        with self.assertRaisesRegex(ValueError, 'excluded record has unexpected output_token_ids'): self.validate()

    def test_shuffled_records_do_not_change_results(self):
        baseline = a.summarize(*self.validate())
        self.records.reverse()
        self.assertEqual(baseline, a.summarize(*self.validate()))

    def test_missing_protocol(self):
        self.protocols.pop('LG')
        with self.assertRaises(ValueError): self.validate()
        with self.assertRaisesRegex(ValueError, 'no bound protocol'): self.validate(allow_incomplete=True)
        self.records = [r for r in self.records if r['evaluator'] == 'HB']
        rows, meta = self.validate(allow_incomplete=True)
        self.assertEqual(len(meta['missing_tasks']), 318)

    def test_pinned_import_rejects_drift(self):
        with self.assertRaisesRegex(ValueError, 'runner SHA'): a.load_runner(RUNNER_PATH, 'f'*64, self.pins['parser_sha256'])
        with self.assertRaisesRegex(ValueError, 'parser SHA'): a.load_runner(RUNNER_PATH, self.pins['runner_sha256'], 'f'*64)

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'bad.json'
            p.write_text('{"value":1,"value":2}')
            with self.assertRaisesRegex(ValueError, 'duplicate'): a.strict_json(p)
            p.write_text('{"value":NaN}')
            with self.assertRaisesRegex(ValueError, 'nonfinite'): a.strict_json(p)


    def test_token_policy_and_judgment_time_tampering(self):
        self.records[0]['token_policy']['full_prompt_left_truncated'] = 1
        rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'HB clipping'): self.validate()
        self.setUp(); self.records[1]['token_policy']['apply_chat_template_return_dict'] = True; rehash(self.records[1])
        with self.assertRaisesRegex(ValueError, 'LG token serialization'): self.validate()
        self.setUp(); self.records[0]['started_at_utc'] = '2026-10-29T06:00:00+00:00'; rehash(self.records[0])
        with self.assertRaisesRegex(ValueError, 'pre-plan'): self.validate()


class DirectoryTests(unittest.TestCase):
    """Synthetic source loader; real directory/parser/math paths, no private raw data."""
    @classmethod
    def setUpClass(cls):
        cls.data = fixture()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.input_zip = Path(self.temp.name) / 'synthetic_input.bin'
        self.input_zip.write_bytes(b'SYNTHETIC INPUT LOADER FIXTURE; NOT RESEARCH DATA')
        self.zip_pin = patch.object(a, 'ZIP_SHA', a.sha(self.input_zip.read_bytes()))
        self.zip_pin.start(); self.addCleanup(self.zip_pin.stop)
        self.root = Path(self.temp.name) / 'run'
        self.root.mkdir()
        self.tasks, self.records, self.protocols, self.provenance, self.runner, self.pins = copy.deepcopy(self.data[:4]) + self.data[4:]
        import research_parsers
        self.input_loader = patch.object(self.runner, 'inputs', return_value=(self.tasks, self.provenance))
        self.input_loader.start(); self.addCleanup(self.input_loader.stop)
        self.runner_loader = patch.object(a, 'load_runner', return_value=(self.runner, research_parsers))
        self.runner_loader.start(); self.addCleanup(self.runner_loader.stop)
        self.write_json('tasks.json', self.tasks)
        self.write_json('input_provenance.json', self.provenance)
        self.write_json('environment.json', self.protocols['HB']['environment'])
        for e, protocol in self.protocols.items(): self.write_json(e + '_protocol.json', protocol)
        self.plan = Path(a.__file__).with_name('analysis_plan.json')
        plan_target = self.root / '_mirror' / 'analysis' / 'analysis_plan.json'
        plan_target.parent.mkdir(parents=True)
        plan_target.write_bytes(self.plan.read_bytes())
        (self.root / 'records').mkdir()
        for record in self.records:
            self.write_json('records/' + a.sha(record['task_key'].encode()) + '.json', record)

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, relative, value):
        (self.root / relative).write_bytes(a.canonical(value))

    def analyze(self, allow_incomplete=False):
        return a.analyze_directory(self.root, self.input_zip, RUNNER_PATH, self.plan,
                                   self.pins['runner_sha256'], self.pins['parser_sha256'], allow_incomplete)

    def test_synthetic_source_records_roundtrip(self):
        result = self.analyze()
        self.assertEqual(result['metadata']['records_present'], 636)
        self.assertTrue(result['metadata']['source_provenance']['synthetic_fixture'])
        self.assertEqual(result['metadata']['numpy_version'], np.__version__)
        self.assertEqual(result['metadata']['analysis_code_sha256'], a.sha(Path(a.__file__).read_bytes()))
        self.assertEqual(result['metadata']['environment_sha256'], a.sha(a.canonical(self.protocols['HB']['environment'])))

    def test_cli_main_roundtrip_and_completion_fields(self):
        output = Path(self.temp.name) / 'analysis-output'
        args = ['--run-dir', str(self.root), '--zip', str(self.input_zip), '--runner', str(RUNNER_PATH),
                '--runner-sha256', self.pins['runner_sha256'], '--parser-sha256', self.pins['parser_sha256'],
                '--plan', str(self.plan), '--out', str(output)]
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            a.main(args)
        summary = json.loads(captured.getvalue())
        self.assertNotIn('complete', summary)
        self.assertTrue(summary['task_accounted_complete'])
        self.assertTrue(summary['requested_evaluation_complete'])
        self.assertTrue(summary['all_binary_valid'])
        self.assertEqual(summary['judged_count'], 636)
        self.assertEqual(summary['valid_binary_count'], 636)
        self.assertEqual(summary['excluded_count'], 0)
        self.assertEqual(len(list(output.iterdir())), 10)

    def test_directory_missing_extra_filename_and_plan_binding(self):
        path = self.root / 'records' / (a.sha(self.records[0]['task_key'].encode()) + '.json')
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing 1'): self.analyze()
        self.assertEqual(self.analyze(True)['metadata']['records_present'], 635)
        path.write_bytes(original)
        extra = self.root / 'records' / 'unexpected.json'; extra.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'unexpected result path'): self.analyze()
        extra.unlink()
        path.write_bytes(a.canonical(self.records[1]))
        with self.assertRaisesRegex(ValueError, 'filename/task'): self.analyze()
        path.write_bytes(original)
        (self.root / '_mirror' / 'analysis' / 'analysis_plan.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'run archive frozen plan'): self.analyze()

    def test_directory_environment_and_task_source_binding(self):
        env = dict(self.protocols['HB']['environment'], device='changed')
        self.write_json('environment.json', env)
        with self.assertRaisesRegex(ValueError, 'environment binding'): self.analyze()
        self.write_json('environment.json', {'precision': 'nf4'})
        with self.assertRaisesRegex(ValueError, 'precision'): self.analyze()
        self.write_json('environment.json', self.protocols['HB']['environment'])
        tasks = copy.deepcopy(self.tasks); tasks[0]['response'] = 'mismatch'
        self.write_json('tasks.json', tasks)
        with self.assertRaisesRegex(ValueError, 'source-rebuilt'): self.analyze()

    def test_directory_duplicate_json_key_rejected(self):
        path = self.root / 'records' / (a.sha(self.records[0]['task_key'].encode()) + '.json')
        raw = path.read_text()
        path.write_text(raw.replace('{', '{"status":"judged",', 1))
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'): self.analyze()


if __name__ == '__main__':
    unittest.main(verbosity=2)
