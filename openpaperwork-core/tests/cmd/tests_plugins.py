import argparse
import unittest

import openpaperwork_core


class MockConfigBackendModule(object):
    """
    Plugin paperwork_backend.config uses openpaperwork.config_file.
    This mock mocks openpaperwork.config_file so we can test
    paperwork_backend.config.file
    """
    class Plugin(openpaperwork_core.PluginBase):
        def __init__(self):
            self.calls = []
            self.returns = {}
            self.config_backend_load = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_load', args, kwargs)
            )
            self.config_backend_save = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_save', args, kwargs)
            )
            self.config_backend_load_plugins = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_load_plugins', args, kwargs)
            )
            self.config_backend_add_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_add_plugin', args, kwargs)
            )
            self.config_backend_remove_plugin = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_remove_plugin', args, kwargs)
            )
            self.config_backend_put = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_put', args, kwargs)
            )
            self.config_backend_get = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_get', args, kwargs)
            )
            self.config_backend_add_observer = (
                lambda *args, **kwargs:
                self._handle_call('config_backend_add_observer', args, kwargs)
            )
            self.config_backend_remove_observer = (
                lambda *args, **kwargs:
                self._handle_call(
                    'config_backend_remove_observer', args, kwargs
                )
            )
            self.config_backend_list_active_plugins = (
                lambda *args, **kwargs:
                self._handle_call(
                    'config_backend_list_active_plugins', args, kwargs
                )
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
            return ["config_backend"]


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core._load_module(
            "openpaperwork_core.config.backend.configparser",
            MockConfigBackendModule()
        )
        self.core.load("openpaperwork_core.cmd.plugins")
        self.core.init()

        setting = self.core.call_success(
            "config_build_simple", "Global", "WorkDirectory",
            lambda: "file:///home/toto/papers"
        )
        self.core.call_all("config_register", "workdir", setting)

    def test_add_remove_list_plugin(self):
        self.core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).returns = {
            'config_backend_load': [None],
            'config_backend_load_plugins': [None],
            'config_backend_add_plugin': [None],
            'config_backend_list_active_plugins': [
                ['plugin_a', 'plugin_b', 'plugin_c'],
                ['plugin_a', 'plugin_c']
            ],
            'config_backend_remove_plugin': [None],
            'config_backend_save': [None],
        }

        self.core.call_all('config_load')
        self.core.call_all(
            'config_load_plugins', 'paperwork-shell', default_plugins=['pouet']
        )

        parser = argparse.ArgumentParser()
        cmd_parser = parser.add_subparsers(
            help='command', dest='command', required=True
        )
        self.core.call_all("cmd_complete_argparse", cmd_parser)

        args = parser.parse_args(
            ['plugins', 'add', 'plugin_c', '--no_auto']
        )
        self.core.call_all("cmd_set_interactive", False)
        r = self.core.call_success("cmd_run", args)
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_load', ('openpaperwork_core',), {}),
                (
                    'config_backend_load_plugins',
                    ('paperwork-shell', ['pouet']), {}
                ),
                (
                    'config_backend_add_plugin',
                    ('paperwork-shell', 'plugin_c'), {}
                ),
                ('config_backend_save', (), {}),
            ]
        )

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success("cmd_run", args)
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_b', 'plugin_c'])
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_load', ('openpaperwork_core',), {}),
                (
                    'config_backend_load_plugins',
                    ('paperwork-shell', ['pouet']), {}
                ),
                (
                    'config_backend_add_plugin',
                    ('paperwork-shell', 'plugin_c'), {}
                ),
                ('config_backend_save', (), {}),
                (
                    'config_backend_list_active_plugins',
                    ('paperwork-shell',), {}
                )
            ]
        )

        args = parser.parse_args(
            ['plugins', 'remove', 'plugin_b', '--no_auto']
        )
        r = self.core.call_success("cmd_run", args)
        self.assertTrue(r)
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_load', ('openpaperwork_core',), {}),
                (
                    'config_backend_load_plugins',
                    ('paperwork-shell', ['pouet']), {}
                ),
                (
                    'config_backend_add_plugin',
                    ('paperwork-shell', 'plugin_c'), {}
                ),
                ('config_backend_save', (), {}),
                (
                    'config_backend_list_active_plugins',
                    ('paperwork-shell',), {}
                ),
                (
                    'config_backend_remove_plugin',
                    ('paperwork-shell', 'plugin_b'), {}
                ),
                ('config_backend_save', (), {}),
            ]
        )

        args = parser.parse_args(['plugins', 'list'])
        r = self.core.call_success("cmd_run", args)
        self.assertEqual(sorted(r), ['plugin_a', 'plugin_c'])
        self.assertEqual(
            self.core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).calls,
            [
                ('config_backend_load', ('openpaperwork_core',), {}),
                (
                    'config_backend_load_plugins',
                    ('paperwork-shell', ['pouet']), {}
                ),
                (
                    'config_backend_add_plugin',
                    ('paperwork-shell', 'plugin_c'), {}
                ),
                ('config_backend_save', (), {}),
                (
                    'config_backend_list_active_plugins',
                    ('paperwork-shell',), {}
                ),
                (
                    'config_backend_remove_plugin',
                    ('paperwork-shell', 'plugin_b'), {}
                ),
                ('config_backend_save', (), {}),
                (
                    'config_backend_list_active_plugins',
                    ('paperwork-shell',), {}
                )
            ]
        )
