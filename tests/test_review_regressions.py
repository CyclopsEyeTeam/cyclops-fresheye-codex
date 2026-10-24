import hashlib
import json
import os
from pathlib import Path
import subprocess
from unittest import mock

from cyclops_fresheye.rpc import save
from support import FixtureCase


class ReviewRegressionTests(FixtureCase):
    def test_stale_save_file_does_not_prevent_rebinding(self):
        first = '11111111-1111-4111-8111-111111111111'
        second = '22222222-2222-4222-8222-222222222222'
        command = self.command('--bind', '--origin')
        result = subprocess.run([*command, first], cwd=self.project, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        binding = self.root/'state/launcher-bindings'/(
            hashlib.sha256(str(self.project).encode()).hexdigest()+'.json')
        stale = binding.with_name(binding.name+'.new')
        stale.write_text('INTERRUPTED SAVE: preserve this evidence')
        result = subprocess.run([*command, second], cwd=self.project, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(binding.read_text())['threadId'], second)
        self.assertEqual(stale.read_text(), 'INTERRUPTED SAVE: preserve this evidence')

    def test_failed_save_preserves_target_and_cleans_own_temporary(self):
        target = self.root/'receipt.json'
        target.write_text('{"original": true}\n')
        before = set(self.root.iterdir())
        with mock.patch('cyclops_fresheye.rpc.os.replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                save(target, {'replacement': True})
        self.assertEqual(json.loads(target.read_text()), {'original': True})
        self.assertEqual(set(self.root.iterdir()), before)

    def test_special_evidence_is_rejected_without_hanging_or_starting_codex(self):
        pipe = self.project/'evidence-pipe'
        os.mkfifo(pipe)
        link = self.project/'linked-pipe'
        link.symlink_to(pipe)
        for path in (pipe, link, self.project, Path('/dev/null')):
            with self.subTest(path=path):
                try:
                    result = subprocess.run(
                        self.command('--read-only', '--evidence', str(path), 'Review evidence'),
                        cwd=self.project, env=self.env, capture_output=True, text=True, timeout=3)
                except subprocess.TimeoutExpired:
                    self.fail('Special evidence blocked the launcher')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('regular file', result.stderr)
                self.assertFalse((self.home/'fixture-calls.jsonl').exists())
                self.assertFalse((self.home/'config.toml').exists())

    def test_relative_evidence_comes_from_selected_project(self):
        selected = self.root/'selected-project'
        selected.mkdir()
        (self.project/'README.md').write_text('CALLER_README_MUST_NOT_BE_SENT')
        (selected/'README.md').write_text('SELECTED_PROJECT_README')
        result = subprocess.run(
            self.command('--once', '--cwd', str(selected), '--evidence', 'README.md', 'Review'),
            cwd=self.project, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        sent = (self.home/'fixture-model-input.txt').read_text()
        self.assertIn('SELECTED_PROJECT_README', sent)
        self.assertNotIn('CALLER_README_MUST_NOT_BE_SENT', sent)
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['evidence'][0]['path'], str(selected/'README.md'))

    def test_absolute_evidence_path_is_preserved_with_selected_project(self):
        selected = self.root/'selected-project'
        selected.mkdir()
        explicit = self.project/'README.md'
        explicit.write_text('EXPLICIT_ABSOLUTE_EVIDENCE')
        (selected/'README.md').write_text('UNSELECTED_PROJECT_EVIDENCE')
        result = subprocess.run(
            self.command('--once', '--cwd', str(selected), '--evidence', str(explicit), 'Review'),
            cwd=self.project, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        sent = (self.home/'fixture-model-input.txt').read_text()
        self.assertIn('EXPLICIT_ABSOLUTE_EVIDENCE', sent)
        self.assertNotIn('UNSELECTED_PROJECT_EVIDENCE', sent)
