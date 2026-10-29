"""Publication configuration must fail closed without private settings."""
import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import colab_smoke as runner
import drive_wrapper as wrapper
import EXPORT_FULL159_RESULTS_V2 as exporter


class ReleaseConfigTests(unittest.TestCase):
    def test_exporter_dependency_pins_match_public_bytes(self):
        root=Path(__file__).parent
        self.assertEqual(exporter.WRAPPER_SHA,exporter.sha((root/'drive_wrapper.py').read_bytes()))
        for name,digest in exporter.PINS.items():
            self.assertEqual(exporter.sha((root/name).read_bytes()),digest)
        self.assertEqual(wrapper.PINNED,exporter.PINS)

    def test_missing_lineage_configuration_fails_before_reads(self):
        with patch.object(wrapper,'CONFIGURED_DRIVE_FOLDER_ID',None):
            with self.assertRaises(wrapper.PersistenceError):
                wrapper.validate_hb_lineage('unavailable',runner,[],{})
            with self.assertRaises(wrapper.PersistenceError):
                wrapper.validate_lg_lineage('unavailable',runner,[],'unavailable')

    def test_export_requires_configured_folder_before_file_access(self):
        with patch.object(exporter,'FOLDER_ID',None):
            with self.assertRaisesRegex(ValueError,'explicit Drive folder'):
                exporter.export_completed('unavailable','full159_20000101T000000Z_000000000001','unavailable')

    def test_cli_requires_matching_configured_folder(self):
        args=['--runner','unavailable','--drive-parent','unavailable',
              '--verified-drive-folder-id','SYNTHETIC_FOLDER_ID',
              '--run-id','full159_20000101T000000Z_000000000001',
              '--source-hb-run','unavailable','--source-lg-run','unavailable','--',
              '--zip','unavailable','--out','unavailable','--judge','HB']
        with patch.object(wrapper,'CONFIGURED_DRIVE_FOLDER_ID','DIFFERENT_SYNTHETIC_FOLDER'):
            with self.assertRaisesRegex(wrapper.PersistenceError,'must agree'):
                wrapper._main(args)

    def test_cli_rejects_unconfigured_source_run_ids(self):
        args=['--runner','unavailable','--drive-parent','unavailable',
              '--verified-drive-folder-id','SYNTHETIC_FOLDER_ID',
              '--run-id','full159_20000101T000000Z_000000000001',
              '--source-hb-run','unavailable','--source-lg-run','unavailable','--',
              '--zip','unavailable','--out','unavailable','--judge','HB']
        with patch.object(wrapper,'CONFIGURED_DRIVE_FOLDER_ID','SYNTHETIC_FOLDER_ID'),patch.object(wrapper,'SOURCE_HB_RUN_ID',None):
            with self.assertRaisesRegex(wrapper.PersistenceError,'source run IDs'):
                wrapper._main(args)


if __name__=='__main__':
    unittest.main()
