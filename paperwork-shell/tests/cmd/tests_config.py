import argparse
import unittest

import openpaperwork_core


class MockConfigFileModule(object):
    """
    Plugin paperwork_backend.config uses openpaperwork.config_file.
    This mock mocks openpaperwork.config_file so we can test
    paperwork_backend.config.file
    """
    class Plugin(openpaperwork_core.PluginBase):
        def __init__(self):
            self.calls = []
            self.returns = {}
            self.config_load = (
                lambda *args, **kwargs:
                self._handle_call('config_load', args, kwargs)
            )
            self.config_save = (
                lambda *args, **kwargs:
                self._handle_call('config_save', args, kwargs)
            )
            self.config_load_plugins = (
                lambda *args, **kwargs:
                self._handle_call('config_load_plugins', args, kwargs)
            )
            self.config_add_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_add_plugin', args, kwargs)
            )
            self.config_remove_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_remove_plugin', args, kwargs)
            )
            self.config_put = (
                lambda *args, **kwargs:
                self._handle_call('config_put', args, kwargs)
            )
            self.config_get = (
                lambda *args, **kwargs:
                self._handle_call('config_get', args, kwargs)
            )
            self.config_add_observer = (
                lambda *args, **kwargs:
                self._handle_call('config_add_observer', args, kwargs)
            )
            self.config_remove_observer = (
                lambda *args, **kwargs:
                self._handle_call('config_remove_observer', args, kwargs)
            )
            self.config_list_active_plugins = (
                lambda *args, **kwargs:
                self._handle_call('config_list_active_plugins', args, kwargs)
            )

        def _handle_call(self, func, args, kwargs):
            self.calls.append((func, args, kwargs))
            if func not in self.returns:
                return None
            r = self.returns[func].pop(0)
            if len(self.returns[func]) <= 0:
                self.returns.pop(func)
            return r

        def get_interfaces(self):
            return ["configuration"]


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core._load_module(
            "openpaperwork_core.config_file", MockConfigFileModule()
        )
        self.core.load("paperwork_shell.cmd.config")
        self.core.init()

        setting = self.core.call_success(
            "paperwork_config_build_simple", "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all("paperwork_config_register", "workdir", setting)

    def test_get_put(self):
        self.core.get_by_name('openpaperwork_core.config_file').returns = {
            'config_put': [None],
            'config_save': [None],
            'config_get': ['file:///pouet/path']
        }

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(
            ['config', 'put', 'workdir', 'str', 'file:///pouet/path']
        )
        self.core.call_all("cmd_set_interactive", False)
        r = self.core.call_success("cmd_run", args)
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                (
                    'config_put',
                    ('Global', "WorkDirectory", "file:///pouet/path"),
                    {}
                ),
                ('config_save', (), {}),
            ]
        )

        args = parser.parse_args(['config', 'get', 'workdir'])
        r = self.core.call_success("cmd_run", args)
        self.assertEqual(r, {"workdir": "file:///pouet/path"})
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                (
                    'config_put',
                    ('Global', "WorkDirectory", "file:///pouet/path"),
                    {}
                ),
                ('config_save', (), {}),
                # it uses the cache for the get --> no call to config_get
            ]
        )

    def test_add_remove_list_plugin(self):
        self.core.get_by_name('openpaperwork_core.config_file').returns = {
            'config_load': [None],
            'config_load_plugins': [None],
            'config_add_plugin': [None],
            'config_save': [None],
            'config_list_active_plugins': [
                ['plugin_a', 'plugin_b', 'plugin_c'],
                ['plugin_a', 'plugin_c']
            ],
            'config_remove_plugin': [None],
            'config_save': [None],
        }

        self.core.call_all(  # so it gets the application name
            'paperwork_config_load', 'paperwork-gtk', default_plugins=['pouet']
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(
            ['config', 'add_plugin', 'plugin_c']
        )
        self.core.call_all("cmd_set_interactive", False)
        r = self.core.call_success("cmd_run", args)
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_load', ('paperwork2',), {}),
                ('config_load_plugins', ('paperwork-gtk', ['pouet']), {}),
                ('config_add_plugin', ('paperwork-gtk', 'plugin_c'), {}),
                ('config_save', (), {}),
            ]
        )

        args = parser.parse_args(['config', 'list_plugins'])
        r = self.core.call_success("cmd_run", args)
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_b', 'plugin_c'])
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_load', ('paperwork2',), {}),
                ('config_load_plugins', ('paperwork-gtk', ['pouet']), {}),
                ('config_add_plugin', ('paperwork-gtk', 'plugin_c'), {}),
                ('config_save', (), {}),
                ('config_list_active_plugins', ('paperwork-gtk',), {})
            ]
        )

        args = parser.parse_args(
            ['config', 'remove_plugin', 'plugin_b']
        )
        r = self.core.call_success("cmd_run", args)
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_load', ('paperwork2',), {}),
                ('config_load_plugins', ('paperwork-gtk', ['pouet']), {}),
                ('config_add_plugin', ('paperwork-gtk', 'plugin_c'), {}),
                ('config_save', (), {}),
                ('config_list_active_plugins', ('paperwork-gtk',), {}),
                ('config_remove_plugin', ('paperwork-gtk', 'plugin_b'), {}),
                ('config_save', (), {}),
            ]
        )

        args = parser.parse_args(['config', 'list_plugins'])
        r = self.core.call_success("cmd_run", args)
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_c'])
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_load', ('paperwork2',), {}),
                ('config_load_plugins', ('paperwork-gtk', ['pouet']), {}),
                ('config_add_plugin', ('paperwork-gtk', 'plugin_c'), {}),
                ('config_save', (), {}),
                ('config_list_active_plugins', ('paperwork-gtk',), {}),
                ('config_remove_plugin', ('paperwork-gtk', 'plugin_b'), {}),
                ('config_save', (), {}),
                ('config_list_active_plugins', ('paperwork-gtk',), {})
            ]
        )
