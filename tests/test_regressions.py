import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from cyclops_fresheye import cli, rpc


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fresheye-regression-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root/'project'
        self.project.mkdir()

    def test_initialization_exception_reaps_spawned_child(self):
        # Removing constructor cleanup must leave this actual child alive.
        real_popen = subprocess.Popen
        children = []

        def spawn(*args, **kwargs):
            child = real_popen([sys.executable, '-c', 'import sys; sys.stdin.read()'],
                               **kwargs)
            children.append(child)
            return child

        def cleanup():
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait()
                for stream in (child.stdin, child.stdout):
                    if stream and not stream.closed:
                        stream.close()
        self.addCleanup(cleanup)
        with mock.patch.object(rpc.subprocess, 'Popen', side_effect=spawn), \
             mock.patch.object(rpc.RPC, 'request', side_effect=RuntimeError('initialize rejected')):
            with self.assertRaisesRegex(RuntimeError, 'initialize rejected'):
                rpc.RPC(self.root/'home', self.project, self.root/'log.jsonl')
        self.assertIsNotNone(children[0].poll(), 'RPC constructor leaked its child')

    def run_rejected(self, home, receipts=None, evidence=None):
        args = ['codex-fresheye', '--cwd', str(self.project), '--home', str(home),
                '--data-dir', str(self.root/'state'),
                '--receipts-dir', str(receipts or self.root/'receipts')]
        if evidence:
            args += ['--evidence', str(evidence)]
        args += ['Review this fixture']
        with mock.patch.object(sys, 'argv', args), \
             mock.patch.object(cli, 'registered_origin', return_value=None), \
             mock.patch.object(cli, 'ensure_login', side_effect=AssertionError('login before validation')):
            try:
                cli.main()
            except (SystemExit, cli.UserError):
                pass

    def test_rejected_project_home_is_not_created(self):
        home = self.project/'new-settings'
        self.run_rejected(home)
        self.assertFalse(home.exists(), 'Rejected home was created before validation')

    def test_rejected_existing_home_permissions_unchanged(self):
        home = self.project/'existing'
        home.mkdir(mode=0o750)
        before = home.stat().st_mode
        self.run_rejected(home)
        self.assertEqual(home.stat().st_mode, before, 'Rejected home was chmodded')

    def test_invalid_receipts_are_rejected_before_login_or_home_creation(self):
        home = self.root/'new-home'
        self.run_rejected(home, receipts=self.project/'receipts')
        self.assertFalse(home.exists())

    def test_bad_evidence_is_rejected_before_login_or_home_creation(self):
        home = self.root/'new-home'
        try:
            self.run_rejected(home, evidence=self.project/'missing.txt')
        except FileNotFoundError:
            pass
        self.assertFalse(home.exists())


if __name__ == '__main__':
    unittest.main()
