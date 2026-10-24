#!/usr/bin/env python3
"""Disposable Codex App Server client. No TUI control or session-file edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import signal
import selectors
import stat
import tempfile
from . import __version__


class RPC:
    def __init__(self, home, cwd, log, extra_args=(), *, startup_timeout=30, temp_dir=None):
        self.home, self.cwd = Path(home).resolve(), Path(cwd).resolve()
        self.log = Path(log)
        self.proc = self.err = self.reader = None
        self.stop_reading = threading.Event()
        self.events, self.pending, self.serial = queue.Queue(), [], 0
        try:
            self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.err = self.log.with_suffix('.stderr').open('a')
            temp = Path(temp_dir or self.log.parent/'runtime-tmp')
            temp.mkdir(parents=True, exist_ok=True, mode=0o700)
            env = dict(os.environ, CODEX_HOME=str(self.home), TMPDIR=str(temp))
            for key in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CODEX_TOOL_CALL_ID'):
                env.pop(key, None)
            self.proc = subprocess.Popen(
                ['codex', *extra_args, 'app-server', '--listen', 'stdio://'],
                cwd=self.cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self.err, text=True, bufsize=1, start_new_session=True)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self.request('initialize', {'clientInfo': {
                'name': 'cyclops_fresheye', 'title': 'Cyclops FreshEye Experimental V0',
                'version': __version__}}, timeout=startup_timeout)
            self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            self.close()
            raise

    def _record(self, direction, message):
        with self.log.open('a') as f:
            f.write(json.dumps({'direction': direction, 'message': message}) + '\n')

    def _read(self):
        try:
            buffered = b''
            with selectors.DefaultSelector() as selector:
                selector.register(self.proc.stdout, selectors.EVENT_READ)
                while not self.stop_reading.is_set():
                    if not selector.select(timeout=.1):
                        continue
                    chunk = os.read(self.proc.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    buffered += chunk
                    while b'\n' in buffered:
                        line, buffered = buffered.split(b'\n', 1)
                        try:
                            msg = json.loads(line)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                        self._record('receive', msg)
                        self.events.put(msg)
        finally:
            self.events.put({'_eof': True})

    def send(self, message):
        self._record('send', message)
        self.proc.stdin.write(json.dumps(message) + '\n')
        self.proc.stdin.flush()

    def receive(self, deadline):
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('Codex App Server response deadline exceeded')
        try:
            msg = self.events.get(timeout=left)
        except queue.Empty as exc:
            raise TimeoutError('Codex App Server response deadline exceeded') from exc
        if msg.get('_eof'):
            raise RuntimeError('Codex App Server closed; inspect the evidence log')
        if 'id' in msg and 'method' in msg:
            # This read-only spike never silently grants approvals or invokes UI.
            self.send({'id': msg['id'], 'error': {
                'code': -32601, 'message': 'Interactive server requests are unsupported in this spike'}})
        return msg

    def request(self, method, params, timeout=120):
        self.serial += 1
        rid = self.serial
        self.send({'id': rid, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while True:
            msg = self.receive(deadline)
            if msg.get('id') == rid and 'method' not in msg:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg['result']
            self.pending.append(msg)

    def start(self, name, config=None, ephemeral=False, model=None,
              sandbox='read-only', approval='never'):
        params = {
            'cwd': str(self.cwd),
            'approvalPolicy': approval, 'sandbox': sandbox,
            'ephemeral': ephemeral, 'config': config or {}}
        if model:
            params['model'] = model
        result = self.request('thread/start', params)
        tid = result['thread']['id']
        self.request('thread/name/set', {'threadId': tid, 'name': name})
        return result

    def resume(self, tid):
        return self.request('thread/resume', {'threadId': tid, 'excludeTurns': True})

    def turn(self, tid, text, timeout=180):
        result = self.request('turn/start', {
            'threadId': tid, 'input': [{'type': 'text', 'text': text}]})
        turn_id = result['turn']['id']
        deadline, messages = time.monotonic() + timeout, []
        while True:
            msg = self.pending.pop(0) if self.pending else self.receive(deadline)
            params = msg.get('params', {})
            if params.get('threadId') != tid:
                continue
            if msg.get('method') == 'item/completed':
                item = params.get('item', {})
                if item.get('type') == 'agentMessage':
                    messages.append(item.get('text', ''))
            if msg.get('method') == 'turn/completed' and params['turn']['id'] == turn_id:
                turn = params['turn']
                if turn['status'] != 'completed':
                    raise RuntimeError(f'Turn {turn_id}: {turn}')
                return '\n'.join(messages)

    def close(self):
        proc = self.proc
        if proc is not None:
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
            # The direct process may have exited while a helper retained its pipes.
            # Every server starts in its own session: signals cannot reach the main chat.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if self.reader and self.reader is not threading.current_thread():
                self.stop_reading.set()
                self.reader.join(timeout=1)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
        if self.err and not self.err.closed:
            self.err.close()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+path.name+'.', suffix='.new', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def payload(task, evidence, *, cwd=None):
    sections, manifest = [task], []
    base = Path(cwd) if cwd is not None else Path.cwd()
    for path in evidence:
        path = (base / Path(path).expanduser()).resolve()
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f'Evidence must be a regular file: {path}')
        # Nonblocking open also prevents a regular-file-to-FIFO swap from hanging.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError(f'Evidence must be a regular file: {path}')
            data = stream.read(64 * 1024 + 1)
        if len(data) > 64 * 1024:
            raise ValueError(f'Evidence exceeds disposable prototype limit: {path}')
        digest = hashlib.sha256(data).hexdigest()
        manifest.append({'path': str(path), 'sha256': digest, 'bytes': len(data)})
        sections.append(f'Explicitly selected evidence: {path.name}\n{data.decode("utf-8")}')
    return '\n\n'.join(sections), manifest
