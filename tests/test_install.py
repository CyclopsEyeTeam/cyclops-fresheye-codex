from pathlib import Path
import os
import shutil
import subprocess
from support import FixtureCase

PROJECT = Path(__file__).resolve().parents[1]


class InstallationTests(FixtureCase):
    def install(self, *extra):
        return subprocess.run(['bash', str(PROJECT/'install.sh'), '--prefix',
             str(self.root/'prefix'), '--data-dir', str(self.root/'installed-state'), *extra],
             env=self.env, cwd=self.root, capture_output=True, text=True, timeout=20)

    def test_installed_command_is_independent_of_checkout(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        env = dict(self.env)
        env.pop('PYTHONPATH', None)
        env.pop('CYCLOPS_FRESHEYE_DATA_DIR', None)
        command = self.root/'prefix/bin/codex-fresheye'
        help_result = subprocess.run([str(command), '--help'], cwd=self.root, env=env,
                                     capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn('Open a fresh Codex chat', help_result.stdout)
        run = subprocess.run([str(command), '--once', 'PORTABLE_INSTALL'], cwd=self.project,
                             env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(list((self.root/'installed-state/launcher-receipts').glob('*/receipt.json')))

    def test_unrelated_command_is_preserved(self):
        command = self.root/'prefix/bin/codex-fresheye'
        command.parent.mkdir(parents=True)
        command.write_text('DO NOT REPLACE')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(command.read_text(), 'DO NOT REPLACE')

    def test_explicit_replacement_keeps_rollback_copy(self):
        command = self.root/'prefix/bin/codex-fresheye'
        command.parent.mkdir(parents=True)
        command.write_text('PREVIOUS COMMAND')
        result = self.install('--replace')
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.root/'prefix/share/cyclops-fresheye-codex/backups').glob('*'))
        self.assertTrue(any(p.read_text()=='PREVIOUS COMMAND' for p in backups if p.is_file()))

    def test_installed_browser_mode_uses_saved_temp_choice_without_env_setup(self):
        temp = self.env['CYCLOPS_FRESHEYE_BROWSER_TMP']
        installed = self.install('--browser-temp-dir', temp)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        env = dict(self.env)
        for key in ('PYTHONPATH', 'CYCLOPS_FRESHEYE_DATA_DIR', 'CYCLOPS_FRESHEYE_BROWSER_TMP'):
            env.pop(key, None)
        result = subprocess.run([str(self.root/'prefix/bin/codex-fresheye'), '--once',
                                 '--browser', '--writable', 'Browser test'],
                                cwd=self.project, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        receipt = json.loads(next((self.root/'installed-state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['access']['browserTemporary'], temp)
        self.assertTrue(receipt['access']['browser'])
        self.assertEqual(receipt['access']['requestedSandbox'], 'workspace-write')
