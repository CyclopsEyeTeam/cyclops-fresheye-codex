#!/usr/bin/env python3
"""Second-terminal FreshEye launcher; uses App Server and the unmodified Codex CLI."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

from .rpc import RPC, payload, save
from .paths import UserError, absolute, default_data_dir, validate_layout
from .capabilities import launch_config, cli_config, validate_browser_dependency, browser_temporary
from .app import validate_app_url, probe_app, app_context
from . import __version__


def clean_environment(home, temporary):
    env = dict(os.environ, CODEX_HOME=str(home), TMPDIR=str(temporary))
    for key in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CODEX_TOOL_CALL_ID'):
        env.pop(key, None)
    return env


def ensure_login(home, cwd, interactive, *, temporary):
    env = clean_environment(home, temporary)
    status = subprocess.run(['codex', 'login', 'status'], env=env, cwd=cwd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode == 0:
        return
    if not interactive:
        raise UserError('FreshEye needs its one-time sign-in. Run codex-fresheye in a terminal, '
                        'or sign in with:\n'+shlex.join(['env', 'CODEX_HOME='+str(home), 'codex', 'login']))
    print('Welcome to Codex FreshEye. A one-time sign-in keeps its settings separate '
          'from your main chat. Follow the Codex sign-in prompt below.', flush=True)
    result = subprocess.run(['codex', 'login'], env=env, cwd=cwd)
    if result.returncode != 0:
        raise UserError('Sign-in was not completed. Run codex-fresheye again when ready.')
    status = subprocess.run(['codex', 'login', 'status'], env=env, cwd=cwd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode != 0:
        raise UserError('Codex did not confirm the sign-in. No FreshEye session was started.')


def binding_path(cwd, directory):
    return directory/(hashlib.sha256(str(cwd).encode()).hexdigest()+'.json')


def registered_origin(cwd, directory):
    path = binding_path(cwd, directory)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get('cwd') != str(cwd):
        raise UserError('The saved main-chat link does not match this project.')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(prog='codex-fresheye',
        description='Open a fresh Codex chat with browser, workspace writes and network access. '
                    'Your main chat stays open; normal Codex approvals apply.')
    parser.add_argument('prompt', nargs='?', help='Question for FreshEye; asks you when omitted')
    parser.add_argument('--cwd', default=os.getcwd())
    parser.add_argument('--data-dir', default=str(default_data_dir()),
                        help='State directory (default: CYCLOPS_FRESHEYE_DATA_DIR or XDG state directory)')
    parser.add_argument('--home',
                        help='Dedicated Codex home; authenticate here with codex login')
    parser.add_argument('--receipts-dir')
    parser.add_argument('--model', help='Optional native Codex model override')
    parser.add_argument('--origin', help='Main session UUID; metadata only, never sent to FreshEye')
    parser.add_argument('--origin-terminal', help='Optional main-terminal label; metadata only')
    parser.add_argument('--bind', action='store_true',
                        help='Register the main chat from --origin or the launching Codex environment')
    parser.add_argument('--evidence', action='append', default=[])
    parser.add_argument('--once', action='store_true', help='One native codex exec turn, then exit')
    parser.add_argument('--read-only', action='store_true',
                        help='Restrict this run to read-only access, without browser or command networking')
    parser.add_argument('--browser', action='store_true',
                        help='Compatibility flag; an isolated Playwright browser is enabled by default')
    parser.add_argument('--writable', action='store_true',
                        help='Compatibility flag; workspace writes are enabled by default')
    parser.add_argument('--network', action='store_true',
                        help='Compatibility flag; command network/listen access is enabled by default')
    parser.add_argument('--app', metavar='URL',
                        help='Optional known app URL; check availability and reuse a responding service')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare thread and print native command')
    args = parser.parse_args(argv)
    if args.read_only and (args.browser or args.writable or args.network or args.app):
        parser.error('cannot combine --read-only with --browser, --writable, --network or --app')
    args.browser = args.writable = args.network = not args.read_only
    if args.app:
        validate_app_url(args.app)

    cwd = absolute(args.cwd)
    layout = validate_layout(cwd, args.data_dir, args.home, args.receipts_dir)
    home, receipts = layout.home, layout.receipts
    origin = args.origin or os.environ.get('CODEX_THREAD_ID')
    binding = 'explicit' if args.origin else ('launch-environment' if origin else 'unbound')
    if args.bind:
        if not origin:
            raise UserError('Ask your main Codex chat to bind FreshEye here, '
                            'or use --bind --origin MAIN_CHAT_ID.')
        save(binding_path(cwd, layout.bindings), {'cwd': str(cwd), 'threadId': origin,
             'terminalLabel': args.origin_terminal,
             'registeredAt': datetime.now(timezone.utc).isoformat()})
        print(f'FreshEye receipts are now linked to this main chat for {cwd}.')
        return 0
    saved_origin = registered_origin(cwd, layout.bindings) if not origin else None
    if saved_origin:
        origin, binding = saved_origin['threadId'], 'registered-project'
        args.origin_terminal = args.origin_terminal or saved_origin.get('terminalLabel')
    interactive_terminal = sys.stdin.isatty() and sys.stdout.isatty()
    if not args.prompt:
        if not interactive_terminal:
            parser.error('Give a question: codex-fresheye "Review this project"')
        args.prompt = input('What would you like FreshEye to investigate? ').strip()
    if not args.prompt.strip():
        raise UserError('No question entered. No FreshEye session was started.')
    # Read and validate every selected file before setup or authentication.
    text, evidence = payload(args.prompt, args.evidence, cwd=cwd)
    browser_backend = validate_browser_dependency(args.browser)
    browser_tmp = browser_temporary(cwd, layout) if args.browser else None
    app = probe_app(args.app) if args.app else None
    if app:
        text += app_context(app)
    for directory in (home, receipts, layout.temporary):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if browser_tmp:
        browser_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (home/'config.toml').exists():
        (home/'config.toml').write_text(
            'approval_policy = "never"\nsandbox_mode = "read-only"\n'
            '[memories]\nuse_memories = false\ngenerate_memories = false\n')
    ensure_login(home, cwd, interactive_terminal, temporary=layout.temporary)
    run = receipts/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    run.mkdir(mode=0o700)
    receipt_path = run/'receipt.json'
    browser_output = run/'browser'
    if args.browser:
        browser_output.mkdir(mode=0o700)
    sandbox, approval, config = launch_config(writable=args.writable, browser=args.browser,
                                               output=browser_output, backend=browser_backend,
                                               network=args.network)
    if browser_tmp:
        config['mcp_servers.fresheye_browser.env.TMPDIR'] = str(browser_tmp)
    receipt = {
        'version': 0, 'status': 'preparing', 'cwd': str(cwd), 'codexHome': str(home),
        'launcherVersion': __version__, 'app': app,
        'origin': {'threadId': origin, 'binding': binding,
                   'terminalLabel': args.origin_terminal},
        'freshThreadId': None, 'evidence': evidence,
        'taskSha256': hashlib.sha256(args.prompt.encode()).hexdigest(),
        'access': {'requestedSandbox': sandbox, 'approvalPolicy': approval,
                   'network': args.network,
                   'browser': args.browser,
                   'browserOutput': str(browser_output) if args.browser else None,
                   'browserTemporary': str(browser_tmp) if browser_tmp else None,
                   'shellNetwork': 'enabled for this run' if args.network else 'native sandbox default; browser MCP networking is separate'},
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'context': {'conversationHistoryCopied': False, 'memoryUse': False,
                    'memoryGeneration': False, 'projectAndGlobalInstructions': 'normal discovery',
                    'hooks': 'normal dedicated-home trust rules', 'completeIsolationClaimed': False},
        'receiptDelivery': 'local-file-and-launch-terminal; no main-terminal injection'}
    save(receipt_path, receipt)
    rpc = None
    try:
        rpc = RPC(home, cwd, run/'prepare.rpc.jsonl', temp_dir=layout.temporary,
                  extra_args=cli_config(config))
        fresh = rpc.start('◎ FreshEye · App Test' if app else '◎ FreshEye · Fresh Context', config, model=args.model,
                          sandbox=sandbox, approval=approval)
        tid = fresh['thread']['id']
        receipt.update(freshThreadId=tid, status='prepared',
                       instructionSources=fresh.get('instructionSources', []),
                       model=fresh.get('model'), modelProvider=fresh.get('modelProvider'))
        receipt['access']['effectiveSandbox'] = fresh.get('sandbox')
        if args.network and fresh.get('sandbox', {}).get('networkAccess') is False:
            raise UserError('The runtime denied requested network access. No model task was started; '
                            'inspect the receipt and managed permissions. No bypass was attempted.')
    except Exception as exc:
        receipt.update(status='prepare_failed', error=str(exc))
        save(receipt_path, receipt)
        raise
    finally:
        if rpc is not None:
            rpc.close()

    common = cli_config(config)
    if args.model:
        common += ['--model', args.model]
    interactive = ['codex', 'resume', '--no-daemon', '--sandbox', sandbox,
                   '--ask-for-approval', approval, *common, '--', tid, text]
    receipt['resumeCommand'] = ['env', 'CODEX_HOME='+str(home), 'codex', 'resume',
                                '--no-daemon', *common, '--', tid]
    save(receipt_path, receipt)
    print(f'◎ FreshEye · Fresh Context\nProject: {cwd}', flush=True)
    print('Main chat: receipt link saved.' if origin else 'Main chat: no receipt link registered.', flush=True)
    print('Your main chat stays open. Switch terminals to return.', flush=True)
    print('Memory is off; project instructions still apply.', flush=True)
    print(f'Workspace access: {sandbox}. Browser: {"enabled (isolated)" if args.browser else "off"}.', flush=True)
    if args.network:
        print('Command network/listen access: enabled for this run.', flush=True)
    if app:
        print(f'App: {app["url"]} — '+('already responding; reuse it.' if app['reachable'] else 'host check unreachable; check with browser first.'), flush=True)
    if args.prepare_only:
        print(shlex.join(['env', 'CODEX_HOME='+str(home), *interactive]))
        return 0
    receipt['status'] = 'running'
    save(receipt_path, receipt)
    try:
        if args.once or not interactive_terminal:
            command = ['codex', 'exec', 'resume', '--skip-git-repo-check', '--json',
                       '--output-last-message', str(run/'result.txt'), *common, '--', tid, '-']
            with (run/'native.events.jsonl').open('w') as out, (run/'native.stderr').open('w') as err:
                process = subprocess.run(command, input=text, text=True, stdout=out, stderr=err,
                                         cwd=cwd, env=clean_environment(home, layout.temporary))
            events = []
            for line in (run/'native.events.jsonl').read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            complete = any(e.get('type') == 'turn.completed' for e in events)
            receipt['status'] = 'completed' if process.returncode == 0 and complete else 'failed'
            receipt['resultPath'] = str(run/'result.txt') if (run/'result.txt').exists() else None
            if receipt['resultPath']:
                print((run/'result.txt').read_text(), flush=True)
            code = process.returncode or (0 if complete else 1)
        else:
            code = subprocess.run(interactive, cwd=cwd, env=clean_environment(home, layout.temporary)).returncode
            receipt['status'] = 'native_cli_closed' if code == 0 else 'native_cli_failed'
        receipt['exitCode'] = code
    except KeyboardInterrupt:
        receipt['status'], code = 'interrupted', 130
    except Exception as exc:
        receipt.update(status='launcher_failed', error=str(exc))
        raise
    finally:
        receipt['updatedAt'] = datetime.now(timezone.utc).isoformat()
        save(receipt_path, receipt)
        print(f'◎ FreshEye receipt: {receipt_path}', flush=True)
    return code


def entrypoint():
    try:
        return main()
    except (UserError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f'FreshEye: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('\nFreshEye cancelled.', file=sys.stderr)
        return 130
