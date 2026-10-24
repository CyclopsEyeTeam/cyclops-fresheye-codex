import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fresheye-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root/'project'
        self.project.mkdir()
        self.home = self.root/'state'/'launcher-home'
        self.home.mkdir(parents=True)
        self.fake_bin = self.root/'fake-bin'
        self.fake_bin.mkdir()
        fake = self.fake_bin/'codex'
        shutil.copyfile(Path(__file__).parent/'fixtures/fake_codex.py', fake)
        fake.chmod(0o700)
        browser = self.fake_bin/'playwright-mcp'
        browser.write_text('#!/bin/sh\nexit 0\n')
        browser.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.fake_bin)+os.pathsep+os.environ['PATH'],
                        CYCLOPS_FRESHEYE_DATA_DIR=str(self.root/'state'),
                        PYTHONDONTWRITEBYTECODE='1')
        for key in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CODEX_TOOL_CALL_ID'):
            self.env.pop(key, None)
        self.env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]/'src')
        browser_temp = tempfile.TemporaryDirectory(prefix='fb-', dir=os.environ.get('FRESHEYE_TEST_SHORT_ROOT'))
        self.addCleanup(browser_temp.cleanup)
        self.env['CYCLOPS_FRESHEYE_BROWSER_TMP'] = browser_temp.name

    def mode(self, name):
        (self.home/'fixture-mode').write_text(name)

    def command(self, *args):
        return [sys.executable, '-m', 'cyclops_fresheye', *args]
