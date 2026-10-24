import json
import os
from pathlib import Path
import subprocess
import signal
import sys
from unittest import mock

from cyclops_fresheye.rpc import RPC
from support import FixtureCase


class ProtocolTests(FixtureCase):
    def make_rpc(self, timeout=1):
        return RPC(self.home, self.project, self.root/'rpc.jsonl', startup_timeout=timeout)

    def assert_reaped(self):
        pid = int((self.home/'fixture-pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_initialization_error_reaps_real_fixture(self):
        self.mode('init-error')
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'fixture init failure'):
                self.make_rpc()
        self.assert_reaped()

    def test_early_eof_is_reaped(self):
        self.mode('eof')
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'closed'):
                self.make_rpc()
        self.assert_reaped()

    def test_initialization_timeout_terminates_child(self):
        self.mode('hang')
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaises(TimeoutError):
                self.make_rpc(.1)
        self.assert_reaped()

    def test_timeout_kills_child_that_ignores_termination(self):
        self.mode('stubborn')
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaises(TimeoutError):
                self.make_rpc(.1)
        self.assert_reaped()

    def test_repeated_close_closes_streams_and_reaps(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            rpc = self.make_rpc()
            rpc.close()
            rpc.close()
        self.assert_reaped()
        self.assertTrue(rpc.err.closed and rpc.proc.stdin.closed and rpc.proc.stdout.closed)

    def test_close_is_bounded_when_descendant_holds_stdout(self):
        self.mode('descendant')
        script = ('from cyclops_fresheye.rpc import RPC; '
                  f'r=RPC({str(self.home)!r}, {str(self.project)!r}, {str(self.root/"child-log.jsonl")!r}); '
                  'r.close(); print("CLOSED")')
        try:
            result = subprocess.run([sys.executable, '-c', script], env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('CLOSED', result.stdout)
        except subprocess.TimeoutExpired:
            self.fail('RPC.close blocked while a descendant retained stdout')
        finally:
            path = self.home/'fixture-pid'
            if path.exists():
                try:
                    os.killpg(int(path.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_fresh_input_and_registered_receipt_are_separate(self):
        origin = '11111111-1111-4111-8111-111111111111'
        bind = subprocess.run(self.command('--bind', '--origin', origin), cwd=self.project,
                              env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(bind.returncode, 0, bind.stderr)
        evidence = self.project/'selected.txt'
        evidence.write_text('SELECTED_EVIDENCE')
        run = subprocess.run(self.command('--once', '--evidence', str(evidence), 'TASK_ONLY'),
                             cwd=self.project, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        model_input = (self.home/'fixture-model-input.txt').read_text()
        self.assertIn('TASK_ONLY', model_input)
        self.assertIn('SELECTED_EVIDENCE', model_input)
        self.assertNotIn(origin, model_input)
        trace = [json.loads(x) for x in (self.home/'fixture-rpc.jsonl').read_text().splitlines()]
        self.assertNotIn('thread/resume', [m['method'] for m in trace])
        self.assertNotIn('thread/fork', [m['method'] for m in trace])
        start = next(m for m in trace if m['method']=='thread/start')
        self.assertFalse(start['params']['config']['memories.use_memories'])
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['origin']['threadId'], origin)
        self.assertEqual(receipt['origin']['binding'], 'registered-project')
        self.assertEqual(receipt['status'], 'completed')

    def test_failure_event_is_not_reported_as_completion(self):
        self.mode('turn-failed')
        result = subprocess.run(self.command('--once', 'Question'), cwd=self.project,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['status'], 'failed')

    def test_start_failure_has_receipt_and_no_running_child(self):
        self.mode('start-error')
        result = subprocess.run(self.command('--once', 'Question'), cwd=self.project,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['status'], 'prepare_failed')
        self.assert_reaped()
