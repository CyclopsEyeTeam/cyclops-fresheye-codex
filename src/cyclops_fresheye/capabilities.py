"""Explicit per-launch capabilities, separate from conversation freshness."""
import json
import shutil
import os
from pathlib import Path
import tempfile
from .paths import UserError, absolute, overlaps

BROWSER_PACKAGE = '@playwright/mcp@0.0.83'


def validate_browser_dependency(enabled):
    if not enabled:
        return None
    direct = shutil.which('playwright-mcp')
    if direct:
        return direct, []
    node = shutil.which('node')
    cache = Path(os.environ.get('npm_config_cache', os.environ.get('NPM_CONFIG_CACHE',
                                                                 str(Path.home()/'.npm'))))
    if node:
        for manifest in sorted((cache/'_npx').glob('*/node_modules/@playwright/mcp/package.json')):
            info = json.loads(manifest.read_text())
            script = manifest.parent/'cli.js'
            if info.get('name') == '@playwright/mcp' and info.get('version') == '0.0.83' and script.is_file():
                return node, [str(script)]
    raise UserError('FreshEye testing access needs Playwright MCP and Chrome. '
                    'For a restricted review use --read-only, or install the MCP backend with:\n'
                    'npm install -g '+BROWSER_PACKAGE)


def launch_config(*, writable, browser, output, backend=None, network=False):
    sandbox = 'workspace-write' if writable else 'read-only'
    approval = 'on-request' if writable or browser else 'never'
    config = {'memories.use_memories': False, 'memories.generate_memories': False,
              'sandbox_mode': sandbox, 'approval_policy': approval}
    if network:
        config['sandbox_workspace_write.network_access'] = True
    if browser:
        command, prefix = backend or validate_browser_dependency(True)
        config.update({
            'mcp_servers.fresheye_browser.command': command,
            'mcp_servers.fresheye_browser.args': [*prefix,
                '--headless', '--isolated',
                '--browser', 'chrome', '--codegen', 'none', '--output-dir', str(output)],
            'mcp_servers.fresheye_browser.required': True,
            'mcp_servers.fresheye_browser.startup_timeout_sec': 30,
        })
    return sandbox, approval, config


def browser_temporary(cwd, layout):
    configured = os.environ.get('CYCLOPS_FRESHEYE_BROWSER_TMP')
    path = absolute(configured or Path(tempfile.gettempdir())/('fresheye-browser-'+str(os.getuid())))
    if len(os.fsencode(path)) > 60:
        raise UserError('Chrome needs a short temporary path. Set CYCLOPS_FRESHEYE_BROWSER_TMP '
                        'to a short private directory; see README browser setup.')
    protected = [cwd, layout.home, layout.receipts, layout.bindings,
                 absolute(Path.home()/'.codex')]
    if os.environ.get('CODEX_HOME'):
        protected.append(absolute(os.environ['CODEX_HOME']))
    if any(overlaps(path, other) for other in protected):
        raise UserError('Browser temporary storage must be separate from project and Codex state')
    if path.exists() and not path.is_dir():
        raise UserError('Browser temporary storage is not a directory')
    ancestor = path
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        raise UserError('Browser temporary storage crosses a non-directory')
    return path


def cli_config(config):
    args = []
    for key, value in config.items():
        # These values are booleans, strings, numbers and arrays of strings;
        # their JSON representation is valid TOML for Codex's -c overrides.
        args += ['-c', key+'='+json.dumps(value, ensure_ascii=False)]
    return args
