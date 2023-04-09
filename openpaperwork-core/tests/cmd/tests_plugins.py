import argparse
import os
import tempfile
import unittest

import openpaperwork_core
import openpaperwork_core.cmd


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config_path = tempfile.NamedTemporaryFile(delete=False)
        self.config_path.close()

        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.cmd.plugins")
        self.core.init()
        self.core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).TEST_FILE_URL = "file://" + self.config_path.name

        self.core.load = lambda *args, **kwargs: None

        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all("config_register", "workdir", setting)

    def tearDown(self):
        os.unlink(self.config_path.name)

    def test_add_remove_list_plugin(self):
        self.core.call_all('config_load')
        self.core.call_all(
            'config_load_plugins', 'paperwork-shell', default_plugins=['pouet']
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        self.core.call_all(
            "cmd_set_console", openpaperwork_core.cmd.DummyConsole()
        )
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_a', '--no_auto']
        )
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_b', '--no_auto']
        )
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)
        args = parser.parse_args(
            ['plugins', 'add', 'plugin_c', '--no_auto']
        )
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertEqual(
            sorted(r), ['plugin_a', 'plugin_b', 'plugin_c', 'pouet']
        )

        args = parser.parse_args(
            ['plugins', 'remove', 'plugin_b', '--no_auto']
        )
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertTrue(r)

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success(
            "cmd_run", openpaperwork_core.cmd.DummyConsole(), args
        )
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_c', 'pouet'])
