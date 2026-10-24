#!/usr/bin/env python3
"""Offline boundary fixture. No credentials, network, or model inference."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

home = Path(os.environ['CODEX_HOME'])
home.mkdir(parents=True, exist_ok=True)
mode_file = home/'fixture-mode'
mode = mode_file.read_text().strip() if mode_file.exists() else 'normal'
args = sys.argv[1:]
with (home/'fixture-calls.jsonl').open('a') as f:
    f.write(json.dumps({'args': args, 'cwd': os.getcwd(),
                       'inheritedMainId': os.environ.get('CODEX_THREAD_ID')})+'\n')

# Global native -c options may precede the App Server subcommand.
while args[:1] in (['-c'], ['--config']):
    args = args[2:]

if args[:2] == ['login', 'status']:
    sys.exit(1 if mode.startswith('login-') and not (home/'fixture-login-ok').exists() else 0)
if args == ['login']:
    if mode == 'login-failed':
        sys.exit(9)
    (home/'fixture-login-ok').touch()
    sys.exit(0)
if args[:1] == ['app-server']:
    (home/'fixture-pid').write_text(str(os.getpid()))
    if mode == 'eof':
        sys.exit(0)
    for line in sys.stdin:
        msg = json.loads(line)
        with (home/'fixture-rpc.jsonl').open('a') as f:
            f.write(json.dumps(msg)+'\n')
        method = msg['method']
        result = {}
        if method == 'initialize':
            if mode == 'descendant':
                child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                         stdin=subprocess.DEVNULL)
                (home/'fixture-descendant-pid').write_text(str(child.pid))
            if mode in ('hang', 'stubborn'):
                if mode == 'stubborn':
                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                while True:
                    time.sleep(1)
            if mode == 'init-error':
                print(json.dumps({'id': msg['id'], 'error': {'code': -32000,
                                                          'message': 'fixture init failure'}}), flush=True)
                continue
            result = {'userAgent': 'offline-fixture', 'platformFamily': 'unix',
                      'platformOs': 'linux'}
        elif method == 'thread/start':
            if mode == 'start-error':
                print(json.dumps({'id': msg['id'], 'error': {'code': -32000,
                                                          'message': 'fixture start failure'}}), flush=True)
                continue
            result = {'thread': {'id': '00000000-0000-4000-8000-000000000001',
                       'sessionId': '00000000-0000-4000-8000-000000000001',
                       'preview': '', 'ephemeral': False, 'modelProvider': 'fixture',
                       'createdAt': 1, 'updatedAt': 1, 'turns': []},
                      'model': 'offline-fixture', 'modelProvider': 'fixture',
                      'instructionSources': [], 'cwd': os.getcwd(),
                      'approvalPolicy': 'never', 'approvalsReviewer': 'user',
                      'sandbox': {'type': 'workspaceWrite' if msg['params'].get('sandbox')=='workspace-write' else 'readOnly',
                                  'networkAccess': False if mode=='network-denied' else msg['params'].get('config',{}).get('sandbox_workspace_write.network_access',False)},
                      'serviceTier': None, 'reasoningEffort': None}
        if 'id' in msg:
            print(json.dumps({'id': msg['id'], 'result': result}), flush=True)
    sys.exit(0)
if args[:2] == ['exec', 'resume']:
    prompt = sys.stdin.read()
    (home/'fixture-model-input.txt').write_text(prompt)
    result = 'OFFLINE FIXTURE REPLY'
    Path(args[args.index('--output-last-message')+1]).write_text(result)
    print(json.dumps({'type': 'thread.started',
                      'thread_id': '00000000-0000-4000-8000-000000000001'}))
    print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message',
                                                       'text': result, 'id': 'item_0'}}))
    print(json.dumps({'type': 'turn.failed' if mode == 'turn-failed' else 'turn.completed',
                      'usage': {'input_tokens': 0, 'output_tokens': 0}}))
    sys.exit(0)
raise SystemExit('Unexpected fixture command: '+str(args))
