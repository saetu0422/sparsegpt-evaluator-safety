"""Neutral synthetic fixtures only; source loaders/plan are mocked in tests.

Production code remains hash-pinned to the separately retained private plan.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import analysis as a

ROOT = Path(__file__).parent
INPUT_ZIP = None  # Assigned a generated neutral fixture in class setup.
NEW_RUNNER = ROOT / 'colab_smoke.py'
OLD_RUNNER = ROOT.parents[1] / 'code' / 'colab_smoke.py'
OLD_PLAN = OLD_RUNNER.with_name('analysis_plan.json')
from synthetic_fixtures import bound_tasks
SYNTHETIC_PLAN_BYTES = b'SYNTHETIC TEST PLAN MARKER; NOT THE FROZEN RESEARCH PLAN'
SYNTHETIC_INPUT_BYTES = b'NEUTRAL SYNTHETIC SOURCE LOADER FIXTURE; NOT RESEARCH DATA'
ENV = {'packages': {'torch': '2.11.0+cu130', 'transformers': '5.20.2', 'accelerate': '1.15.0'},
       'cuda': '13.0', 'device': 'SYNTHETIC', 'total_memory': 1, 'precision': 'fp16'}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(a.canonical(value))


def rehash(record):
    record['content_sha256'] = a.sha(a.canonical({k: v for k, v in record.items() if k != 'content_sha256'}))
    return record


def protocol(tasks, provenance, runner, e, runner_sha, plan, condition=None):
    model_id, revision = runner.MODELS[e]
    template = runner.HB_TEMPLATE if e == 'HB' else 'SYNTHETIC LG TEMPLATE'
    value = {'protocol': a.PROTOCOL_NAME if condition else a.bv.PROTOCOL_NAME, 'judge': e,
        'auth_mode': 'anonymous', 'target_research_model': 'Meta-Llama-3-8B-Instruct; saved responses only, not loaded',
        'model_execution_authorized': True, 'model_id': model_id, 'model_revision': revision, 'tokenizer_revision': revision,
        'template': template, 'template_sha256': a.sha(template.encode()), 'environment': copy.deepcopy(ENV),
        'settings': {'seed': 42, 'do_sample': False, 'temperature_inactive': 0, 'top_p_inactive': 1,
                     'max_new_tokens': 1 if e == 'HB' else 128, 'dtype': 'float16', 'quantization': 'none'},
        'token_policy': a.bv.TOKEN_POLICY, 'parser_version': 'judge-schema-1',
        'parser_code_sha256': plan['baseline_integrity']['parser_sha256'], 'runner_code_sha256': runner_sha,
        'inputs': provenance, 'tasks_sha256': a.sha(a.canonical(tasks)),
        'analysis_plan_sha256': a.PLAN_SHA if condition else a.bv.PLAN_SHA}
    if condition:
        value.update(condition=condition, baseline_archive_sha256=plan['baseline_integrity']['archive_sha256'],
                     baseline_full_checkpoint_sha256=plan['baseline_integrity']['full_checkpoint_sha256'])
    return value


def record(task, proto, runner, new):
    e = task['evaluator']
    # Artificial fixed pattern, not chosen using either old or new real labels.
    value = int(task['row_index'] % 5 == 0) if not new else int((task['row_index'] + int(task['condition'][2:])) % 7 < 2)
    raw = ('Yes' if value else 'No') if e == 'HB' else ('unsafe\nS1' if value else 'safe')
    prompt = runner.HB_TEMPLATE.format(behavior=task['behavior'], generation='synthetic') if e == 'HB' else 'synthetic'
    policy = {'response_clip_tokens': 1, 'clipped_response_sha256': a.sha(b'synthetic'), 'full_prompt_left_truncated': False} if e == 'HB' else {
        'truncation': 'none; conversation user behavior then assistant stored response', 'apply_chat_template_return_dict': False, 'input_ids_contract': 'nonempty flat list[int]'}
    date = '2026-10-30T04:00:' if new else '2026-10-29T08:00:'
    return rehash({'task_key': task['task_key'], 'task_sha256': a.sha(a.canonical(task)), 'protocol_sha256': a.sha(a.canonical(proto)),
        'behavior_id': task['behavior_id'], 'condition': task['condition'], 'evaluator': e,
        'source_seed': 42, 'judge_seed': 42, 'response_sha256': task['response_sha256'], 'legacy_label': task['legacy_label'],
        'model_revision': proto['model_revision'], 'observed_config_commit': None, 'tokenizer_revision': proto['tokenizer_revision'],
        'template_sha256': proto['template_sha256'], 'parser_version': proto['parser_version'],
        'serialized_input_before_prompt_truncation': prompt, 'serialized_input_sha256': a.sha(prompt.encode()),
        'input_token_ids': [1], 'input_token_ids_sha256': a.sha(a.canonical([1])), 'input_tokens': 1, 'token_policy': policy,
        'status': 'judged', 'raw_judge_completion': raw, 'raw_judge_sha256': a.sha(raw.encode()),
        'raw_decoded_with_special_tokens': raw, 'raw_decoded_with_special_tokens_sha256': a.sha(raw.encode()),
        'decoder_settings': dict(a.bv.DECODER), 'output_token_ids': [1], 'output_tokens': 1,
        'started_at_utc': date + '00+00:00', 'ended_at_utc': date + '01+00:00',
        'parsed': runner.parser(raw, e), 'new_label_binary': value, 'legacy_changed': value != task['legacy_label']})


def write_checkpoint(directory, tasks):
    names = ['tasks.json', 'input_provenance.json', 'environment.json', 'HB_protocol.json', 'LG_protocol.json']
    names += ['records/' + a.sha(t['task_key'].encode()) + '.json' for t in tasks]
    entries = [{'path': name, 'bytes': (directory / name).stat().st_size, 'sha256': a.sha((directory / name).read_bytes())} for name in sorted(names)]
    path = directory / '_mirror' / 'RUN_MIRROR_COMPLETE.json'
    save(path, {'artifacts': entries, 'judged': len(tasks), 'schema': a.OLD_SCHEMA if len(tasks)==636 else a.NEW_SCHEMA})
    return a.sha(path.read_bytes())


def make_run(directory, tasks, provenance, runner, runner_sha, plan, condition=None, baseline_context=None):
    save(directory / 'tasks.json', tasks); save(directory / 'input_provenance.json', provenance); save(directory / 'environment.json', ENV)
    archived_plan = directory / '_mirror' / 'analysis' / 'analysis_plan.json'
    archived_plan.parent.mkdir(parents=True, exist_ok=True)
    archived_plan.write_bytes(SYNTHETIC_PLAN_BYTES if condition else OLD_PLAN.read_bytes())
    identity = {'run_id': plan['baseline_integrity']['run_id'], 'wrapper_sha256': a.sha(OLD_RUNNER.with_name('drive_wrapper.py').read_bytes())}
    if condition:
        meta, baseline_protocols = baseline_context
        spec = plan['baseline_integrity']; wrapper_sha = a.sha(NEW_RUNNER.with_name('drive_wrapper.py').read_bytes())
        pins = {'colab_smoke.py': runner_sha, 'research_parsers.py': spec['parser_sha256'], 'HB_standard_template.txt': runner.HB_TEMPLATE_SHA}
        identity = {'run_id': 'levels159_' + condition + '_20261030T040000Z_aaaaaaaaaaaa', 'condition': condition,
            'analysis_plan_sha256': a.PLAN_SHA, 'schema': a.NEW_SCHEMA, 'input_sha256': a.ZIP_SHA,
            'precision': 'fp16', 'scope': 'one_condition159_standard_IDs_x_HB_LG_318_new_judgments',
            'planned_conditions': list(a.CONDITIONS), 'planned_new_judgments_all_conditions':1590,
            'expected_ids':159, 'expected_per_judge':159, 'expected_total_tasks':318,
            'required_package_versions': ENV['packages'], 'execution_cutoff_utc':'2026-10-30T08:00:00+00:00',
            'wrapper_sha256':wrapper_sha, 'runner_code':pins,
            'baseline_lineage':{'baseline_run_id':spec['run_id'], 'baseline_archive_sha256':spec['archive_sha256'],
              'baseline_archive_bytes':spec['archive_bytes'], 'baseline_checkpoint_sha256':spec['full_checkpoint_sha256'],
              'baseline_identity_sha256':meta['baseline_identity_sha256'], 'baseline_judge_checkpoint_sha256':meta['baseline_judge_checkpoint_sha256'],
              'baseline_tasks_sha256':spec['tasks_sha256'], 'baseline_fp16_tasks_sha256':meta['baseline_fp16_tasks_sha256'],
              'baseline_runner_sha256':spec['runner_sha256'], 'baseline_wrapper_sha256':meta['baseline_wrapper_sha256'],
              'baseline_plan_sha256':a.bv.PLAN_SHA, 'baseline_package_versions':ENV['packages'], 'baseline_verified_judgments':636,
              'baseline_fp16_comparison_judgments':318, 'new_condition':condition, 'new_tasks_sha256':a.sha(a.canonical(tasks)),
              'shared_standard_ids':159, 'input_sha256':a.ZIP_SHA,
              'baseline_scientific_fields':{e:{k:baseline_protocols[e][k] for k in plan['protocol_comparability']['required_equal_scientific_fields']} for e in a.EVALUATORS},
              'scope':'new condition318 judgments only; yesterday636 retained read-only; no baseline records imported'}}
        code_dir = directory / '_mirror' / 'code'; code_dir.mkdir(parents=True)
        for name in (*pins, 'drive_wrapper.py'):
            (code_dir / name).write_bytes(NEW_RUNNER.with_name(name).read_bytes())
    save(directory / '_mirror' / 'run_identity.json', identity)
    protocols = {e: protocol(tasks, provenance, runner, e, runner_sha, plan, condition) for e in a.EVALUATORS}
    for e, p in protocols.items(): save(directory / (e + '_protocol.json'), p)
    for task in tasks:
        value = record(task, protocols[task['evaluator']], runner, condition is not None)
        save(directory / 'records' / (a.sha(task['task_key'].encode()) + '.json'), value)
    checkpoint = write_checkpoint(directory, tasks)
    if condition is None:
        for e in a.EVALUATORS: save(directory / '_mirror' / (e + '_MIRROR_COMPLETE.json'), {'schema': a.OLD_SCHEMA, 'judge': e, 'judged':318})
    return checkpoint


class MathTests(unittest.TestCase):
    def test_mcnemar_known(self):
        self.assertEqual(a.mcnemar_exact(10, 2, 159), 158 / 4096)
        self.assertEqual(a.mcnemar_exact(5, 0, 159), 0.0625)
        self.assertEqual(a.mcnemar_exact(0, 0, 159), 1)
        self.assertIsNone(a.mcnemar_exact(0, 0, 0))

    def test_holm_ten_known_zero_ties_and_missing(self):
        p = [0.001, 0.004, 0.01, 0.02, 0.03, 0.04, 0.2, 0.4, 0.8, 1]
        adjusted, ranks = a.holm_ten(p)
        self.assertEqual(adjusted, [0.01, 0.036000000000000004, 0.08, 0.14, 0.18, 0.2, 0.8, 1, 1, 1])
        self.assertEqual(ranks, list(range(1, 11)))
        self.assertEqual(a.holm_ten([0] * 10), ([0] * 10, list(range(1, 11))))
        values = [None] * 10; values[5] = 0.004
        adj, ranks = a.holm_ten(values)
        self.assertEqual(adj[5], 0.04); self.assertEqual(ranks[5], 1)
        self.assertEqual(sum(x is None for x in adj), 9)
        self.assertEqual(a.holm_ten([None] * 10)[0], [None] * 10)
        for bad in ([0.1] * 9, [float('nan')] + [0.1] * 9, [True] * 10):
            with self.assertRaises(ValueError): a.holm_ten(bad)

    def test_bootstrap_independent_reconstruction_all_ten(self):
        differences = [-1, 0, 1] * 20 + [1] * 10
        seeds = []
        for c, e in a.FAMILY:
            seed = int.from_bytes(hashlib.sha256(f'standard159-levels-v1:42:{c}:{e}'.encode()).digest()[:8], 'big')
            indices = np.random.Generator(np.random.PCG64(seed)).integers(0, len(differences), size=(20000, len(differences)))
            values = np.array(differences)[indices].mean(axis=1)
            bounds = np.quantile(values, [0.025, 0.975], method='linear')
            actual = a.paired_bootstrap(differences, c, e)
            self.assertEqual(actual['bootstrap_seed'], seed)
            self.assertEqual((actual['ci95_low'], actual['ci95_high']), tuple(bounds))
            self.assertEqual(actual, a.paired_bootstrap(differences, c, e)); seeds.append(seed)
        self.assertEqual(len(set(seeds)), 10)
        self.assertIsNone(a.paired_bootstrap([], 'SP30', 'HB')['risk_difference'])
        self.assertEqual(a.paired_bootstrap([0] * 159, 'SP50', 'LG')['ci95_high'], 0)
        self.assertEqual(a.paired_bootstrap([1], 'SP60', 'HB')['ci95_low'], 1)
        with self.assertRaises(ValueError): a.paired_bootstrap([0.5], 'SP30', 'HB')


class IntegratedSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = tempfile.TemporaryDirectory()
        cls.master_root = Path(cls.master.name)
        global INPUT_ZIP
        INPUT_ZIP = cls.master_root / 'synthetic_input.bin'
        INPUT_ZIP.write_bytes(SYNTHETIC_INPUT_BYTES)
        # Only tests may substitute a synthetic plan and neutral input loader.
        cls.plan = copy.deepcopy(json.loads((ROOT/'analysis_plan.public.json').read_text())['plan'])
        cls.plan['scope']['input_zip_bytes'] = len(SYNTHETIC_INPUT_BYTES)
        cls.plan['baseline_integrity']['run_id'] = 'full159_20000101T000000Z_000000000001'
        cls.plan_pin = patch.object(a,'PLAN_SHA',a.sha(SYNTHETIC_PLAN_BYTES))
        cls.plan_pin.start(); cls.addClassCleanup(cls.plan_pin.stop)
        cls.zip_pin = patch.object(a,'ZIP_SHA',a.sha(SYNTHETIC_INPUT_BYTES))
        cls.zip_pin.start(); cls.addClassCleanup(cls.zip_pin.stop)
        original_loader = a.bv.load_runner
        def synthetic_loader(path, runner_sha, parser_sha):
            runner, parser = original_loader(path, runner_sha, parser_sha)
            runner.inputs = lambda _path, condition=None: bound_tasks(runner,condition)
            return runner, parser
        cls.loader = patch.object(a.bv,'load_runner',side_effect=synthetic_loader)
        cls.loader.start(); cls.addClassCleanup(cls.loader.stop)
        cls.new_sha = a.sha(NEW_RUNNER.read_bytes())
        cls.wrapper_sha = a.sha(NEW_RUNNER.with_name('drive_wrapper.py').read_bytes())
        cls.new_runner, cls.parser = a.bv.load_runner(NEW_RUNNER, cls.new_sha, cls.plan['baseline_integrity']['parser_sha256'])
        cls.old_runner, _ = a.bv.load_runner(OLD_RUNNER, cls.plan['baseline_integrity']['runner_sha256'], cls.plan['baseline_integrity']['parser_sha256'])
        cls.baseline_tasks, old_prov = cls.old_runner.inputs(INPUT_ZIP)
        cls.plan['baseline_integrity']['tasks_sha256'] = a.sha(a.canonical(cls.baseline_tasks))
        baseline = cls.master_root / 'baseline'
        checkpoint = make_run(baseline, cls.baseline_tasks, old_prov, cls.old_runner, cls.plan['baseline_integrity']['runner_sha256'], cls.plan)
        archive = cls.master_root / 'baseline.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for path in sorted(baseline.rglob('*')):
                if path.is_file(): z.write(path, 'run/' + str(path.relative_to(baseline)))
        cls.plan['baseline_integrity'].update(archive_sha256=a.sha(archive.read_bytes()), archive_bytes=archive.stat().st_size,
                                              full_checkpoint_sha256=checkpoint)
        _, baseline_protocols, baseline_meta = a.load_baseline(baseline, archive, INPUT_ZIP, OLD_RUNNER, cls.plan)
        cls.expected = {}
        for condition in a.CONDITIONS:
            tasks, provenance = cls.new_runner.inputs(INPUT_ZIP, condition)
            cls.expected[condition] = (tasks, provenance)
            make_run(cls.master_root / condition, tasks, provenance, cls.new_runner, cls.new_sha, cls.plan, condition, (baseline_meta, baseline_protocols))

    @classmethod
    def tearDownClass(cls): cls.master.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        shutil.copytree(self.master_root, self.root, dirs_exist_ok=True)
        self.plan = copy.deepcopy(type(self).plan)
        self.dirs = [self.root / c for c in a.CONDITIONS]

    def tearDown(self): self.temp.cleanup()

    def analyze(self, dirs=None, allow_incomplete=False):
        with patch.object(a, 'read_plan', return_value=self.plan):
            return a.analyze(self.dirs if dirs is None else dirs, self.root / 'baseline', self.root / 'baseline.zip', INPUT_ZIP,
                             NEW_RUNNER, self.new_sha, OLD_RUNNER, ROOT / 'analysis_plan.json', allow_incomplete, self.wrapper_sha)

    def mutate_record(self, condition, mutate):
        task = self.expected[condition][0][0]
        path = self.root / condition / 'records' / (a.sha(task['task_key'].encode()) + '.json')
        value = a.strict_json(path); mutate(value); save(path, rehash(value))
        return path

    def test_full_1590_plus318_roundtrip_tables_and_family(self):
        result = self.analyze(); meta = result['metadata']; tables = result['tables']
        self.assertEqual(meta['new_records_present'], 1590); self.assertEqual(meta['reused_baseline_records'], 318)
        self.assertTrue(meta['all_new_binary_valid']); self.assertFalse(meta['SP70_in_today_analysis'])
        self.assertEqual(len(tables['record_comparisons']), 1908)
        self.assertEqual(sum(r['is_reused_baseline'] for r in tables['record_comparisons']), 318)
        self.assertEqual([(r['condition'], r['evaluator']) for r in tables['paired_results']], list(a.FAMILY))
        self.assertEqual([r['family_order'] for r in tables['paired_results']], list(range(1, 11)))
        self.assertTrue(all(r['valid_pairs'] == 159 for r in tables['paired_results']))
        self.assertEqual(len(tables['condition_rates']), 12)
        self.assertEqual(sum(r['n'] for r in tables['legacy_transitions']), 1908)
        self.assertEqual(sum(r['n'] for r in tables['pair_status_counts']), 1590)
        self.assertEqual(sum(r['n'] for r in tables['judge_transitions']), 954)
        self.assertTrue(all(r['source_archive_sha256'] == self.plan['baseline_integrity']['archive_sha256'] for r in tables['record_comparisons'] if r['is_reused_baseline']))

    def test_whole_condition_missing_fixed_family(self):
        dirs = self.dirs[:-1]
        with self.assertRaisesRegex(ValueError, 'missing whole condition'): self.analyze(dirs)
        result = self.analyze(dirs, True)
        self.assertEqual(result['metadata']['new_missing_count'], 318)
        self.assertEqual(result['metadata']['missing_whole_conditions'], ['SP60'])
        self.assertEqual(len(result['tables']['paired_results']), 10)
        self.assertTrue(all(r['valid_pairs'] == 0 and r['p_holm_ten_test_family'] is None for r in result['tables']['paired_results'][-2:]))
        self.assertEqual(len(result['tables']['record_comparisons']), 1908)
        self.assertTrue(any('PROVISIONAL INCOMPLETE' in w for w in result['warnings']))

    def test_all_conditions_missing_still_ten_tests(self):
        result = self.analyze([], True)
        self.assertEqual(result['metadata']['new_missing_count'], 1590)
        self.assertTrue(all(r['p_exact_two_sided'] is None for r in result['tables']['paired_results']))

    def test_one_invalid_pair_preserved(self):
        def invalid(r):
            raw = 'invalid synthetic'; r.update(raw_judge_completion=raw, raw_judge_sha256=a.sha(raw.encode()),
                raw_decoded_with_special_tokens=raw, raw_decoded_with_special_tokens_sha256=a.sha(raw.encode()),
                parsed=self.new_runner.parser(raw, r['evaluator']), new_label_binary=None, legacy_changed=None)
        path = self.mutate_record('SP30', invalid)
        write_checkpoint(self.root / 'SP30', self.expected['SP30'][0])
        result = self.analyze()
        affected = next(r for r in result['tables']['paired_results'] if r['condition'] == 'SP30' and r['evaluator'] == a.strict_json(path)['evaluator'])
        self.assertEqual(affected['valid_pairs'], 158); self.assertEqual(len(affected['nonvalid_pair_details']), 1)
        self.assertEqual(result['metadata']['new_invalid_count'] + result['metadata']['new_abstain_count'], 1)
        self.assertEqual(result['metadata']['new_records_present'], 1590)
        self.assertFalse(result['metadata']['all_new_binary_valid'])

    def test_all_nonbinary_condition_and_exclusion_retained(self):
        condition = 'SP40'
        paths = sorted((self.root / condition / 'records').iterdir())
        excluded_once = False
        for path in paths:
            value = a.strict_json(path); raw = 'synthetic unrecognized output'
            value.update(raw_judge_completion=raw, raw_judge_sha256=a.sha(raw.encode()),
                         raw_decoded_with_special_tokens=raw, raw_decoded_with_special_tokens_sha256=a.sha(raw.encode()),
                         parsed=self.new_runner.parser(raw, value['evaluator']), new_label_binary=None, legacy_changed=None)
            if value['evaluator'] == 'LG' and not excluded_once:
                excluded_once = True
                for key in ('parsed', 'new_label_binary', 'legacy_changed', 'raw_decoded_with_special_tokens',
                            'raw_decoded_with_special_tokens_sha256', 'decoder_settings', 'output_token_ids'):
                    value.pop(key)
                value.update(status='excluded', raw_judge_completion=None, raw_judge_sha256=None,
                             output_tokens=0, started_at_utc=None, ended_at_utc=None,
                             input_token_ids=[1]*8193, input_tokens=8193,
                             input_token_ids_sha256=a.sha(a.canonical([1]*8193)),
                             token_policy={'exclude_reason':'LG_input_over_8192_no_truncation',
                                           'apply_chat_template_return_dict':False, 'input_ids_contract':'nonempty flat list[int]'})
            save(path, rehash(value))
        (self.root / condition / '_mirror' / 'RUN_MIRROR_COMPLETE.json').unlink()
        result = self.analyze(); meta = result['metadata']
        self.assertEqual((meta['new_invalid_count'],meta['new_abstain_count'],meta['new_excluded_count']), (158,159,1))
        self.assertTrue(meta['task_accounted_complete']); self.assertFalse(meta['requested_new_evaluation_complete'])
        for row in result['tables']['paired_results'][2:4]:
            self.assertEqual(row['valid_pairs'], 0); self.assertIsNone(row['risk_difference']); self.assertIsNone(row['p_holm_ten_test_family'])
        self.assertEqual(len(result['tables']['paired_results']), 10)
        self.assertEqual(len(result['tables']['record_comparisons']), 1908)

    def test_missing_one_record_requires_explicit_mode(self):
        path = next((self.root / 'SP40' / 'records').iterdir()); path.unlink()
        # A partial run has no terminal full-checkpoint claim.
        (self.root / 'SP40' / '_mirror' / 'RUN_MIRROR_COMPLETE.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing 1 planned'): self.analyze()
        result = self.analyze(allow_incomplete=True)
        self.assertEqual(result['metadata']['new_missing_count'], 1)
        self.assertEqual(len(result['tables']['paired_results']), 10)

    def test_zero_record_partial_absent_directory_and_marker_count(self):
        root = self.root / 'SP60'; shutil.rmtree(root / 'records')
        (root / '_mirror' / 'RUN_MIRROR_COMPLETE.json').unlink()
        with self.assertRaisesRegex(ValueError, 'records directory'): self.analyze()
        result = self.analyze(allow_incomplete=True)
        self.assertEqual(result['metadata']['new_missing_count'],318)
        self.assertEqual(len(result['tables']['paired_results']),10)
        marker = self.root / 'SP30' / '_mirror' / 'RUN_MIRROR_COMPLETE.json'
        value = a.strict_json(marker); value['judged'] = 317; save(marker,value)
        with self.assertRaisesRegex(ValueError,'schema/judged count'): self.analyze(allow_incomplete=True)

    def test_identity_lineage_code_and_namespace_binding(self):
        path = self.root / 'SP50' / '_mirror' / 'run_identity.json'; original=path.read_bytes()
        for key,value in [('expected_total_tasks',1590),('input_sha256','f'*64),('schema','wrong')]:
            identity=json.loads(original);identity[key]=value;save(path,identity)
            with self.assertRaisesRegex(ValueError,'identity mismatch'):self.analyze()
        identity=json.loads(original);identity['baseline_lineage']['baseline_archive_sha256']='f'*64;save(path,identity)
        with self.assertRaisesRegex(ValueError,'baseline lineage'):self.analyze()
        path.write_bytes(original)
        code=self.root/'SP50'/'_mirror'/'code'/'colab_smoke.py';code.write_bytes(code.read_bytes()+b'\n# tamper')
        with self.assertRaisesRegex(ValueError,'archived reviewed code'):self.analyze()

    def test_duplicate_paths_condition_and_runid_conflicts(self):
        with self.assertRaisesRegex(ValueError, 'duplicate run path'): self.analyze(self.dirs + [self.dirs[0]])
        extra = self.root / 'duplicate'; shutil.copytree(self.dirs[0], extra)
        with self.assertRaisesRegex(ValueError, 'duplicate/conflicting condition'): self.analyze(self.dirs + [extra])
        identity = self.root / 'SP40' / '_mirror' / 'run_identity.json'; value = a.strict_json(identity)
        value['run_id'] = 'levels159_SP30_20261030T040000Z_aaaaaaaaaaaa'; save(identity, value)
        with self.assertRaisesRegex(ValueError, 'namespace mismatch'): self.analyze()

    def test_baseline_archive_and_extracted_bytes_tamper(self):
        archive = self.root / 'baseline.zip'; archive.write_bytes(archive.read_bytes() + b'X')
        with self.assertRaisesRegex(ValueError, 'baseline archive size/hash'): self.analyze()
        shutil.copyfile(self.master_root / 'baseline.zip', archive)
        path = next((self.root / 'baseline' / 'records').iterdir()); value = a.strict_json(path)
        value['new_label_binary'] = 1 - value['new_label_binary']; save(path, rehash(value))
        with self.assertRaisesRegex(ValueError, 'extracted bytes differ'): self.analyze()

    def test_baseline_checkpoint_and_tasks_pins(self):
        self.plan['baseline_integrity']['full_checkpoint_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'full checkpoint hash'): self.analyze()
        self.plan = copy.deepcopy(type(self).plan); self.plan['baseline_integrity']['tasks_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'baseline task hash'): self.analyze()

    def test_bad_new_task_protocol_precision_and_packages(self):
        path = self.root / 'SP50' / 'tasks.json'; value = a.strict_json(path); value[0]['row_index'] = 999; save(path, value)
        with self.assertRaisesRegex(ValueError, 'source-rebuilt'): self.analyze()
        shutil.copyfile(self.master_root / 'SP50' / 'tasks.json', path)
        path = self.root / 'SP50' / 'HB_protocol.json'; value = a.strict_json(path); value['settings']['quantization'] = 'nf4'; save(path, value)
        with self.assertRaisesRegex(ValueError, 'scientific protocol'): self.analyze()
        shutil.copyfile(self.master_root / 'SP50' / 'HB_protocol.json', path)
        path = self.root / 'SP50' / 'environment.json'; value = a.strict_json(path); value['packages']['transformers'] = 'wrong'; save(path, value)
        with self.assertRaisesRegex(ValueError, 'package versions'): self.analyze()

    def test_new_plan_baseline_link_and_template_mismatch(self):
        path = self.root / 'SP55' / 'LG_protocol.json'; original = path.read_bytes()
        for key, value in [('analysis_plan_sha256', a.bv.PLAN_SHA), ('baseline_archive_sha256', 'f'*64), ('template', 'different')]:
            protocol = json.loads(original); protocol[key] = value; save(path, protocol)
            with self.assertRaises(ValueError): self.analyze()
        path.write_bytes(original)
        archive_plan = self.root / 'SP55' / '_mirror' / 'analysis' / 'analysis_plan.json'; archive_plan.write_bytes(OLD_PLAN.read_bytes())
        with self.assertRaisesRegex(ValueError, 'archived analysis plan'): self.analyze()

    def test_binary_flip_id_parser_and_timestamp_binding(self):
        path = self.mutate_record('SP60', lambda r: r.update(new_label_binary=1-r['new_label_binary']))
        with self.assertRaisesRegex(ValueError, 'binary label'): self.analyze()
        shutil.copyfile(self.master_root / 'SP60' / 'records' / path.name, path)
        self.mutate_record('SP60', lambda r: r.update(behavior_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'binding'): self.analyze()
        shutil.copyfile(self.master_root / 'SP60' / 'records' / path.name, path)
        self.mutate_record('SP60', lambda r: r.update(started_at_utc='2026-10-29T08:00:00+00:00'))
        with self.assertRaisesRegex(ValueError, 'predates frozen'): self.analyze()

    def test_unexpected_record_and_checkpoint_conflict(self):
        first = next((self.root / 'SP30' / 'records').iterdir()); extra = self.root / 'SP30' / 'records' / 'unexpected.json'
        shutil.copyfile(first, extra)
        with self.assertRaisesRegex(ValueError, 'unexpected result path'): self.analyze()
        extra.unlink()
        path = self.root / 'SP30' / '_mirror' / 'RUN_MIRROR_COMPLETE.json'; value = a.strict_json(path)
        value['artifacts'].append(value['artifacts'][0]); save(path, value)
        with self.assertRaisesRegex(ValueError, 'duplicate/malformed checkpoint'): self.analyze()

    def test_cli_and_new_immutable_output(self):
        output = self.root / 'output'
        args = ['--baseline-dir', str(self.root/'baseline'), '--baseline-archive', str(self.root/'baseline.zip'),
                '--baseline-runner', str(OLD_RUNNER), '--zip', str(INPUT_ZIP), '--runner', str(NEW_RUNNER),
                '--runner-sha256', self.new_sha, '--wrapper-sha256', self.wrapper_sha, '--out', str(output)]
        for directory in self.dirs: args += ['--run-dir', str(directory)]
        captured = io.StringIO()
        with patch.object(a, 'read_plan', return_value=self.plan), contextlib.redirect_stdout(captured): a.main(args)
        summary = json.loads(captured.getvalue()); self.assertEqual(summary['new_records_present'], 1590)
        self.assertEqual(summary['reused_baseline_records'], 318); self.assertNotIn('complete', summary)
        self.assertEqual(len(list(output.iterdir())), 10)
        with patch.object(a, 'read_plan', return_value=self.plan), self.assertRaisesRegex(ValueError, 'new or empty'): a.main(args)


if __name__ == '__main__': unittest.main(verbosity=2)
