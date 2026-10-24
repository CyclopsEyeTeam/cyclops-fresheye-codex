import json
import subprocess
from pathlib import Path
from unittest import mock
from cyclops_fresheye.capabilities import validate_browser_dependency, browser_temporary
from cyclops_fresheye.paths import UserError, validate_layout
from support import FixtureCase


class CapabilityTests(FixtureCase):
    def run_fresh(self, *flags):
        return subprocess.run(self.command('--once', *flags, 'TASK_ONLY'),
                              cwd=self.project, env=self.env, capture_output=True,
                              text=True, timeout=15)

    def inspect(self):
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        trace = [json.loads(x) for x in (self.home/'fixture-rpc.jsonl').read_text().splitlines()]
        start = next(x for x in trace if x['method']=='thread/start')['params']
        calls = [json.loads(x)['args'] for x in (self.home/'fixture-calls.jsonl').read_text().splitlines()]
        native = next(x for x in calls if x[:2]==['exec','resume'])
        return receipt, start, native

    def test_writable_access_applies_to_prepare_native_and_resume(self):
        result = self.run_fresh('--writable')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt, start, native = self.inspect()
        self.assertEqual(start['sandbox'], 'workspace-write')
        self.assertEqual(start['approvalPolicy'], 'on-request')
        self.assertIn('sandbox_mode="workspace-write"', native)
        self.assertIn('sandbox_mode="workspace-write"', receipt['resumeCommand'])
        self.assertEqual(receipt['access']['requestedSandbox'], 'workspace-write')

    def test_browser_is_explicit_isolated_and_reused_on_resume(self):
        result = self.run_fresh('--browser')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt, start, native = self.inspect()
        config = start['config']
        args = config['mcp_servers.fresheye_browser.args']
        self.assertIn('--isolated', args)
        self.assertIn('--headless', args)
        self.assertTrue(config['mcp_servers.fresheye_browser.required'])
        self.assertTrue(any('mcp_servers.fresheye_browser.args=' in x for x in native))
        self.assertTrue(any('mcp_servers.fresheye_browser.args=' in x for x in receipt['resumeCommand']))
        self.assertEqual(start['sandbox'], 'workspace-write')
        self.assertTrue(receipt['access']['browser'])
        self.assertNotIn('TASK_ONLY', json.dumps(config))

    def test_explicit_read_only_stays_without_browser(self):
        result = self.run_fresh('--read-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt, start, native = self.inspect()
        self.assertEqual(start['sandbox'], 'read-only')
        self.assertFalse(receipt['access']['browser'])
        self.assertFalse(any(k.startswith('mcp_servers.fresheye_browser') for k in start['config']))
        self.assertIn('sandbox_mode="read-only"', receipt['resumeCommand'])

    def test_plain_prompt_has_tester_access_without_url_or_flags(self):
        result = self.run_fresh()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt, start, native = self.inspect()
        self.assertEqual(start['sandbox'], 'workspace-write')
        self.assertEqual(start['approvalPolicy'], 'on-request')
        self.assertTrue(receipt['access']['browser'])
        self.assertTrue(receipt['access']['network'])
        self.assertIsNone(receipt['app'])
        self.assertIn('sandbox_workspace_write.network_access=true', native)
        self.assertIn('sandbox_workspace_write.network_access=true', receipt['resumeCommand'])

    def test_missing_browser_backend_reports_setup_instead_of_silent_no_tools(self):
        env = dict(self.env, NPM_CONFIG_CACHE=str(self.root/'empty-npm-cache'))
        with mock.patch.dict('os.environ', env, clear=True), \
             mock.patch('shutil.which', return_value=None):
            with self.assertRaisesRegex(UserError, 'npm install'):
                validate_browser_dependency(True)

    def test_browser_rejects_long_socket_path_before_creating_it(self):
        target = self.root/('very-long-browser-path-'*8)
        layout = validate_layout(self.project, self.root/'state')
        with mock.patch.dict('os.environ', CYCLOPS_FRESHEYE_BROWSER_TMP=str(target)):
            with self.assertRaisesRegex(UserError, 'short temporary path'):
                browser_temporary(self.project, layout)
        self.assertFalse(target.exists())

    def test_browser_temp_path_cannot_enter_project(self):
        project = Path(self.env['CYCLOPS_FRESHEYE_BROWSER_TMP'])
        layout = validate_layout(project, self.root/'state')
        target = project/'t'
        self.assertLessEqual(len(str(target).encode()), 60)
        with mock.patch.dict('os.environ', CYCLOPS_FRESHEYE_BROWSER_TMP=str(target)):
            with self.assertRaises(UserError):
                browser_temporary(project, layout)
        self.assertFalse(target.exists())

    def test_browser_temp_rejects_file_ancestor(self):
        parent = Path(self.env['CYCLOPS_FRESHEYE_BROWSER_TMP'])/'f'
        parent.write_text('preserve')
        target = parent/'t'
        layout = validate_layout(self.project, self.root/'state')
        self.assertLessEqual(len(str(target).encode()), 60)
        with mock.patch.dict('os.environ', CYCLOPS_FRESHEYE_BROWSER_TMP=str(target)):
            with self.assertRaises(UserError):
                browser_temporary(self.project, layout)
        self.assertEqual(parent.read_text(), 'preserve')
