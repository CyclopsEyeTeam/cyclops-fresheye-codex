import json
import os
import unittest
from pathlib import Path
from unittest import mock

from cyclops_fresheye import cli
from cyclops_fresheye.paths import UserError, default_data_dir, validate_layout
from support import FixtureCase


class PathTests(FixtureCase):
    def test_explicit_data_dir_needs_no_disk_identity_probe(self):
        target = self.root/'custom state'
        with mock.patch.dict(os.environ, self.env, clear=True), \
             mock.patch('subprocess.check_output', side_effect=AssertionError('disk probe')):
            code = cli.main(['--cwd', str(self.project), '--data-dir', str(target),
                             '--bind', '--origin', 'MAIN_ID'])
        self.assertEqual(code, 0)
        files = list((target/'launcher-bindings').glob('*.json'))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())['threadId'], 'MAIN_ID')

    def test_xdg_default(self):
        env = dict(self.env, XDG_STATE_HOME=str(self.root/'portable-xdg'))
        env.pop('CYCLOPS_FRESHEYE_DATA_DIR')
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(default_data_dir(), self.root/'portable-xdg/cyclops-fresheye-codex')

    def test_home_alias_into_project_is_rejected_without_mutation(self):
        alias = self.root/'alias'
        alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(UserError):
            validate_layout(self.project, self.root/'state', alias/'settings')
        self.assertEqual(list(self.project.iterdir()), [])

    def test_main_home_is_rejected_without_chmod(self):
        before = self.home.stat().st_mode
        with mock.patch.dict(os.environ, CODEX_HOME=str(self.home)):
            with self.assertRaises(UserError):
                validate_layout(self.project, self.root/'elsewhere', self.home)
        self.assertEqual(self.home.stat().st_mode, before)

    def test_home_ancestor_of_project_is_rejected(self):
        with self.assertRaises(UserError):
            validate_layout(self.project, self.root/'state', self.root)

    def test_state_directories_cannot_overlap(self):
        with self.assertRaises(UserError):
            validate_layout(self.project, self.root/'state', receipts=self.home/'receipts')

    def test_path_crossing_a_file_is_rejected(self):
        obstacle = self.root/'file'
        obstacle.write_text('keep')
        with self.assertRaises(UserError):
            validate_layout(self.project, self.root/'state', receipts=obstacle/'records')
        self.assertEqual(obstacle.read_text(), 'keep')

    @unittest.skipUnless(os.environ.get('FRESHEYE_TEST_MOUNT_ROOT') and
                         os.environ.get('FRESHEYE_TEST_ALIAS_ROOT'), 'no bind-mount test roots configured')
    def test_mount_alias_cannot_place_new_home_inside_project(self):
        root = Path(os.environ['FRESHEYE_TEST_MOUNT_ROOT'])
        alias_root = Path(os.environ['FRESHEYE_TEST_ALIAS_ROOT'])
        alias_project = alias_root/self.project.relative_to(root)
        self.assertTrue(os.path.samefile(self.project, alias_project))
        with self.assertRaises(UserError):
            validate_layout(alias_project, self.root/'state', self.project/'new-home')
        self.assertFalse((self.project/'new-home').exists())

    @unittest.skipUnless(os.environ.get('FRESHEYE_TEST_MOUNT_ROOT') and
                         os.environ.get('FRESHEYE_TEST_ALIAS_ROOT'), 'no bind-mount test roots configured')
    def test_mount_alias_cannot_enter_main_codex_home(self):
        root = Path(os.environ['FRESHEYE_TEST_MOUNT_ROOT'])
        alias_root = Path(os.environ['FRESHEYE_TEST_ALIAS_ROOT'])
        alias_home = alias_root/self.home.relative_to(root)
        self.assertTrue(os.path.samefile(self.home, alias_home))
        with mock.patch.dict(os.environ, CODEX_HOME=str(self.home)):
            with self.assertRaises(UserError):
                validate_layout(self.project, self.root/'other-state', alias_home/'new-home')
        self.assertFalse((self.home/'new-home').exists())
