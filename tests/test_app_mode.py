import http.server
import json
import subprocess
import threading
from support import FixtureCase


class AppModeTests(FixtureCase):
    def start_http(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'App fixture')
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:'+str(server.server_port)+'/'

    def test_app_mode_selects_all_capabilities_and_reuses_live_server(self):
        url = self.start_http()
        result = subprocess.run(self.command('--once', '--app', url, 'Make test artwork'),
                                cwd=self.project, env=self.env, capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertTrue(receipt['access']['browser'])
        self.assertTrue(receipt['access']['network'])
        self.assertEqual(receipt['access']['requestedSandbox'], 'workspace-write')
        self.assertTrue(receipt['app']['reachable'])
        self.assertEqual(receipt['app']['url'], url)
        prompt = (self.home/'fixture-model-input.txt').read_text()
        self.assertIn(url, prompt)
        self.assertIn('Reuse the running service', prompt)
        self.assertIn('Do not start, stop or restart', prompt)
        trace = [json.loads(x) for x in (self.home/'fixture-rpc.jsonl').read_text().splitlines()]
        config = next(x for x in trace if x['method']=='thread/start')['params']['config']
        self.assertTrue(config['sandbox_workspace_write.network_access'])
        calls = [json.loads(x)['args'] for x in (self.home/'fixture-calls.jsonl').read_text().splitlines()]
        native = next(x for x in calls if x[:2]==['exec','resume'])
        self.assertIn('sandbox_workspace_write.network_access=true', native)
        self.assertIn('sandbox_workspace_write.network_access=true', receipt['resumeCommand'])

    def test_network_flag_cannot_override_explicit_read_only(self):
        result = subprocess.run(self.command('--read-only', '--network', 'Question'), cwd=self.project,
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot combine --read-only', result.stderr)
        self.assertFalse((self.home/'fixture-calls.jsonl').exists())

    def test_runtime_network_denial_stops_before_model_task(self):
        self.mode('network-denied')
        result = subprocess.run(self.command('--once', '--app', self.start_http(), 'Question'),
                                cwd=self.project, env=self.env, capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn('runtime denied requested network access', result.stderr)
        self.assertFalse((self.home/'fixture-model-input.txt').exists())
        receipt = json.loads(next((self.root/'state/launcher-receipts').glob('*/receipt.json')).read_text())
        self.assertEqual(receipt['status'], 'prepare_failed')

    def test_invalid_app_url_is_rejected_before_setup(self):
        result = subprocess.run(self.command('--app', 'file:///tmp/ignored', 'Question'),
                                cwd=self.project, env=self.env, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('http:// or https://', result.stderr)
        self.assertFalse((self.home/'fixture-calls.jsonl').exists())
