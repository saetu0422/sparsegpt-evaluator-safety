import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

import drive_wrapper as w


class MirrorTests(unittest.TestCase):
    def setUp(self):
        # Compact generic storage fixtures; separate synthetic full636 integration exercises production counts.
        self.counts=patch.multiple(w,PER_JUDGE=6,TOTAL_TASKS=12);self.counts.start();self.addCleanup(self.counts.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.local, self.remote = self.root / "scratch", self.root / "drive"
        self.identity = {"schema": w.SCHEMA, "run_id": "fixed-test-run", "input_sha256": "test"}

    def tearDown(self):
        self.temp.cleanup()

    def mirror(self):
        return w.Mirror(self.local, self.remote, self.identity)

    def fake_runner(self, judge="HB", fail_model=False):
        runner = types.SimpleNamespace(__file__=__file__, calls=0, canonical=w.canonical)
        def freeze(path, obj):
            return w.immutable_write(path, w.canonical(obj))
        runner.freeze = freeze
        runner.render = lambda task: task
        def main():
            runner.freeze(self.local / "tasks.json", {"tasks": 12})
            runner.freeze(self.local / "input_provenance.json", {"input_sha256": "test"})
            runner.freeze(self.local / "environment.json", {"precision": "fp16"})
            judges = ('HB', 'LG') if judge == 'both' else (judge,)
            for evaluator in judges:
                runner.freeze(self.local / f"{evaluator}_protocol.json", {"judge": evaluator})
                for i in range(6):
                    path = self.local / f"records/{evaluator}_{i}.json"
                    if path.exists():
                        continue
                    runner.render(i)
                    runner.calls += 1
                    if fail_model:
                        print(json.dumps({"status": "stopped", "context": {"stage": "tokenizer_load", "judge": evaluator}, "http_status": 401}))
                        raise SystemExit(1)
                    runner.freeze(path, {"status": "judged", "evaluator": evaluator, "number": i,
                                         "raw_judge_completion": "safe", "parsed": {"label": "safe"}})
            runner.freeze(self.local / f"completion_{judge}.json", {"requested_evaluation_complete": True, "judged": 6 * len(judges)})
            print(json.dumps({"status": "finished", "target_model_generated": False}))
        runner.main = main
        return runner

    def run_fake(self, judge="HB", mirror=None):
        runner = self.fake_runner(judge)
        m = mirror or self.mirror()
        code = w.execute(runner, m, [], "inference", judge)
        return code, runner, m

    def test_success_raw_config_logs_and_scoped_marker(self):
        code, runner, m = self.run_fake()
        self.assertEqual((code, runner.calls), (0, 6))
        self.assertTrue((self.remote / "records/HB_0.json").exists())
        mark = json.loads((self.remote / "_mirror/HB_MIRROR_COMPLETE.json").read_text())
        self.assertNotIn("completion_HB.json", {x["path"] for x in mark["artifacts"]})
        checkpoint = json.loads((self.remote / f"_mirror/invocations/{m.invocation}/MIRROR_VERIFIED.json").read_text())
        self.assertTrue(any("/events/" in x["path"] for x in checkpoint["metadata"]))
        self.assertIn("completion_HB.json", {x["path"] for x in checkpoint["artifacts"]})
        self.assertFalse((self.remote / "_mirror/RUN_MIRROR_COMPLETE.json").exists())

    def test_initial_storage_failure_prevents_all_inference(self):
        m = self.mirror()
        with patch.object(m, "_remote_write", side_effect=w.PersistenceError("simulated offline")):
            code, runner, _ = self.run_fake(mirror=m)
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertFalse((self.remote / "_mirror/HB_MIRROR_COMPLETE.json").exists())

    def test_record_save_failure_stops_before_next_inference(self):
        m = self.mirror()
        original = m._remote_write
        def write(relative, data):
            if relative == "records/HB_0.json":
                m.broken = True
                raise w.PersistenceError("simulated record save failure")
            return original(relative, data)
        with patch.object(m, "_remote_write", side_effect=write):
            code, runner, _ = self.run_fake(mirror=m)
        self.assertEqual((code, runner.calls), (1, 1))
        self.assertTrue((self.local / "records/HB_0.json").exists())
        self.assertFalse((self.local / "records/HB_1.json").exists())
        self.assertFalse((self.remote / "_mirror/HB_MIRROR_COMPLETE.json").exists())

    def test_probe_failure_before_second_record_stops_generation(self):
        m = self.mirror()
        original, count = m.health, [0]
        def health():
            count[0] += 1
            if count[0] == 3:  # begin, record 0, then record 1
                raise w.PersistenceError("offline")
            original()
        with patch.object(m, "health", side_effect=health):
            code, runner, _ = self.run_fake(mirror=m)
        self.assertEqual((code, runner.calls), (1, 1))

    def test_recovery_after_partial_save_avoids_duplicate_inference(self):
        m = self.mirror()
        original = m._remote_write
        def write(relative, data):
            if relative == "records/HB_0.json":
                m.broken = True
                raise w.PersistenceError("offline")
            return original(relative, data)
        with patch.object(m, "_remote_write", side_effect=write):
            self.assertEqual(self.run_fake(mirror=m)[0], 1)
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (0, 5))

    def test_remote_conflict_preserved_and_prevents_inference(self):
        self.assertEqual(self.run_fake()[0], 0)
        path = self.remote / "records/HB_0.json"
        wrong = b"different existing bytes"
        path.write_bytes(wrong)
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertEqual(path.read_bytes(), wrong)
        self.assertNotEqual((self.local / "records/HB_0.json").read_bytes(), wrong)

    def test_immutable_write_never_overwrites_conflict(self):
        path = self.root / "file"
        self.assertTrue(w.immutable_write(path, b"first"))
        self.assertFalse(w.immutable_write(path, b"first"))
        with self.assertRaises(w.PersistenceError):
            w.immutable_write(path, b"second")
        self.assertEqual(path.read_bytes(), b"first")

    def test_repeated_success_does_not_generate_or_change_markers(self):
        self.assertEqual(self.run_fake()[0], 0)
        marker = (self.remote / "_mirror/HB_MIRROR_COMPLETE.json").read_bytes()
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (0, 0))
        self.assertEqual((self.remote / "_mirror/HB_MIRROR_COMPLETE.json").read_bytes(), marker)

    def test_hb_then_both_stable_markers(self):
        self.assertEqual(self.run_fake('HB')[0], 0)
        mark = (self.remote / '_mirror/HB_MIRROR_COMPLETE.json').read_bytes()
        code, runner, _ = self.run_fake('both')
        self.assertEqual((code, runner.calls), (0, 6))
        self.assertEqual((self.remote / '_mirror/HB_MIRROR_COMPLETE.json').read_bytes(), mark)
        self.assertTrue((self.remote / '_mirror/RUN_MIRROR_COMPLETE.json').exists())

    def test_both_then_hb_stable_markers(self):
        self.assertEqual(self.run_fake('both')[0], 0)
        mark = (self.remote / '_mirror/RUN_MIRROR_COMPLETE.json').read_bytes()
        code, runner, _ = self.run_fake('HB')
        self.assertEqual((code, runner.calls), (0, 0))
        self.assertEqual((self.remote / '_mirror/RUN_MIRROR_COMPLETE.json').read_bytes(), mark)

    def test_hb_lg_then_both_stable_markers(self):
        self.assertEqual(self.run_fake('HB')[0], 0)
        self.assertEqual(self.run_fake('LG')[0], 0)
        mark = (self.remote / '_mirror/RUN_MIRROR_COMPLETE.json').read_bytes()
        code, runner, _ = self.run_fake('both')
        self.assertEqual((code, runner.calls), (0, 0))
        self.assertEqual((self.remote / '_mirror/RUN_MIRROR_COMPLETE.json').read_bytes(), mark)

    def test_cross_runtime_recovery_hb_then_lg_overall_complete(self):
        self.assertEqual(self.run_fake()[0], 0)
        previous_logs = list((self.remote / "_mirror/invocations").rglob("*.json"))
        shutil.rmtree(self.local)
        code, runner, _ = self.run_fake("LG")
        self.assertEqual((code, runner.calls), (0, 6))
        self.assertTrue((self.local / "_mirror/HB_MIRROR_COMPLETE.json").exists())
        self.assertTrue((self.remote / "_mirror/RUN_MIRROR_COMPLETE.json").exists())
        self.assertTrue(all((self.local / p.relative_to(self.remote)).is_file() for p in previous_logs))
        m = self.mirror()
        self.assertEqual(len(m.audit()), 19)
        m.audit_control()

    def test_model_failure_preserves_hb_partial_and_no_lg_marker(self):
        self.assertEqual(self.run_fake()[0], 0)
        runner, m = self.fake_runner("LG", fail_model=True), self.mirror()
        self.assertEqual(w.execute(runner, m, [], "inference", "LG"), 1)
        self.assertTrue((self.remote / "_mirror/HB_MIRROR_COMPLETE.json").exists())
        self.assertFalse((self.remote / "_mirror/LG_MIRROR_COMPLETE.json").exists())
        self.assertFalse((self.remote / "_mirror/RUN_MIRROR_COMPLETE.json").exists())
        events = [json.loads(p.read_text()) for p in (self.remote / f"_mirror/invocations/{m.invocation}/events").glob("*.json")]
        final = next(x for x in events if x["event"] == "runner_finished")
        self.assertEqual(final["exit_code"], 1)
        self.assertEqual(final["diagnostics"][0]["http_status"], 401)

    def test_prior_log_tampering_detected_on_resume(self):
        self.assertEqual(self.run_fake()[0], 0)
        event = next((self.remote / "_mirror/invocations").rglob("events/*.json"))
        event.write_text("{}")
        shutil.rmtree(self.local)
        code, runner, _ = self.run_fake("LG")
        self.assertEqual((code, runner.calls), (1, 0))

    def test_run_identity_conflict_prevents_adoption(self):
        self.assertEqual(self.run_fake()[0], 0)
        self.identity = {**self.identity, "input_sha256": "different"}
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (1, 0))

    def test_nonempty_unbound_destination_refused(self):
        self.remote.mkdir()
        (self.remote / "existing.txt").write_text("preserve")
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertEqual((self.remote / "existing.txt").read_text(), "preserve")
        self.assertEqual(sorted(p.name for p in self.remote.iterdir()), ['existing.txt'])

    def test_symlink_metadata_root_refused_without_collecting_outside_file(self):
        self.assertEqual(self.run_fake()[0], 0)
        outside = self.root / 'outside'
        shutil.move(self.local / '_mirror', outside)
        (outside / 'should_not_collect.txt').write_text('outside private sentinel')
        (self.local / '_mirror').symlink_to(outside, target_is_directory=True)
        code, runner, _ = self.run_fake('LG')
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertFalse((self.remote / '_mirror/should_not_collect.txt').exists())
        self.assertTrue((outside / 'should_not_collect.txt').exists())

    def test_symlink_metadata_ancestor_refused(self):
        m = self.mirror()
        m.begin()
        try:
            outside = self.root / 'outside'
            outside.mkdir()
            (self.local / '_mirror/destination').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(w.PersistenceError):
                m.dual('_mirror/destination/secret.txt', b'not sent')
            self.assertFalse((outside / 'secret.txt').exists())
            self.assertFalse((self.remote / '_mirror/destination/secret.txt').exists())
        finally:
            m.close()

    def test_input_archive_copy_is_hash_audited(self):
        m = self.mirror()
        m.begin()
        try:
            data = b'fixture archive bytes'
            m.dual('_mirror/inputs/verified_inputs.zip', data)
            entries = m.audit_control()
            entry = next(x for x in entries if x['path'] == '_mirror/inputs/verified_inputs.zip')
            self.assertEqual(entry['sha256'], w.sha(data))
            self.assertEqual((self.remote / entry['path']).read_bytes(), data)
        finally:
            m.close()

    def test_stale_lock_is_not_deleted_or_retried(self):
        self.remote.mkdir()
        (self.remote / "_mirror").mkdir()
        (self.remote / "_mirror/run_identity.json").write_bytes(w.canonical(self.identity))
        lock = self.remote / ".mirror_session.lock"
        lock.write_text("some other invocation")
        code, runner, _ = self.run_fake()
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertEqual(lock.read_text(), "some other invocation")

    def test_final_metadata_corruption_has_no_success_marker(self):
        m = self.mirror()
        original = m.finish
        def finish(mode, judge):
            event = next((self.remote / "_mirror/invocations").rglob("events/*.json"))
            event.write_text("{}")
            original(mode, judge)
        with patch.object(m, "finish", side_effect=finish):
            code, runner, _ = self.run_fake(mirror=m)
        self.assertEqual(code, 1)
        self.assertEqual(runner.calls, 6)
        self.assertFalse((self.remote / f"_mirror/invocations/{m.invocation}/MIRROR_VERIFIED.json").exists())

    def test_unmounted_directory_refused(self):
        mount = self.root / "mount"
        parent = mount / "MyDrive/project"
        parent.mkdir(parents=True)
        with self.assertRaises(w.PersistenceError):
            w.mounted_drive_parent(parent, mount)

    def test_interrupted_metadata_commit_refused(self):
        self.assertEqual(self.run_fake()[0], 0)
        pending = self.remote / "_mirror/code/x.part"
        pending.parent.mkdir(exist_ok=True)
        pending.write_text("partial upload")
        code, runner, _ = self.run_fake("LG")
        self.assertEqual((code, runner.calls), (1, 0))
        self.assertTrue(pending.exists())

    def test_metadata_failure_after_record_stops_next_inference(self):
        m = self.mirror()
        original = m.event
        def event(kind, **fields):
            if fields.get("path") == "records/HB_0.json":
                m.broken = True
                raise w.PersistenceError("log mirror unavailable")
            return original(kind, **fields)
        with patch.object(m, "event", side_effect=event):
            code, runner, _ = self.run_fake(mirror=m)
        self.assertEqual((code, runner.calls), (1, 1))
        self.assertTrue((self.remote / "records/HB_0.json").is_file())

    def test_drive_unmount_guard_halts_after_first_generation(self):
        m, runner = self.mirror(), self.fake_runner()
        def guard():
            if runner.calls:
                raise w.PersistenceError('mounted Drive lost')
        m.storage_guard = guard
        code = w.execute(runner, m, [], 'inference', 'HB')
        self.assertEqual((code, runner.calls), (1, 1))
        self.assertFalse((self.remote / '_mirror/HB_MIRROR_COMPLETE.json').exists())

    def test_mount_disappearing_during_write_detected_after_readback(self):
        m, runner = self.mirror(), self.fake_runner()
        mounted = [True]
        def guard():
            if not mounted[0]:
                raise w.PersistenceError('mount disappeared during write')
        m.storage_guard = guard
        write = w.immutable_write
        def write_then_unmount(path, data):
            result = write(path, data)
            if Path(path) == self.remote / 'records/HB_0.json':
                mounted[0] = False
            return result
        with patch.object(w, 'immutable_write', side_effect=write_then_unmount):
            code = w.execute(runner, m, [], 'inference', 'HB')
        self.assertEqual((code, runner.calls), (1, 1))
        self.assertTrue((self.remote / 'records/HB_0.json').is_file())
        self.assertFalse((self.remote / '_mirror/HB_MIRROR_COMPLETE.json').exists())

    def test_mount_identity_change_refused(self):
        parent = Path('/content/drive/project')
        with patch.object(w, 'drive_mount_state', return_value=(parent, {'mount_id': '101'})):
            guard = w.DriveMountGuard(parent)
        with patch.object(w, 'drive_mount_state', return_value=(parent, {'mount_id': '102'})):
            with self.assertRaises(w.PersistenceError):
                guard()


    def test_secret_text_not_retained_context_preserved(self):
        s = w.DiagnosticCapture()
        s.write("Authorization: Bearer SECRET\n")
        s.write(json.dumps({"status": "stopped", "detail": "SECRET", "http_status": 401,
            "context": {"stage": "tokenizer_load", "judge": "LG", "model_id": "meta-llama/Llama-Guard-3-8B",
            "revision": "7327bd9f6efbbe6101dc6cc4736302b3cbb6e425", "token": "SECRET"}}) + "\n")
        self.assertNotIn("SECRET", json.dumps(s.diagnostics))
        self.assertEqual(s.diagnostics[0]["context"]["stage"], "tokenizer_load")
        self.assertEqual(s.diagnostics[0]["http_status"], 401)


if __name__ == "__main__":
    unittest.main()
