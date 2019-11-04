import os
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
            self.rets = {}
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
                self._handle_call('config_all_plugin', args, kwargs)
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

        def _handle_call(self, func, args, kwargs):
            self.calls.append((func, args, kwargs))
            if func not in self.rets:
                return None
            r = self.rets[func].pop(0)
            if len(self.rets[func]) <= 0:
                self.rets.pop(func)
            return r

        def get_interfaces(self):
            return ["configuration"]


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core._load_module(
            "openpaperwork_core.config_file", MockConfigFileModule()
        )
        self.core.load("paperwork_backend.config.file")
        self.core.init()

    def test_config_load(self):
        self.core.call_all(
            'paperwork_config_load', 'paperwork-gtk', default_plugins=['pouet']
        )
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_load', ('paperwork-gtk',), {}),
                ('config_load_plugins', (['pouet'],), {}),
            ]
        )

    def test_get_default(self):
        default = self.core.call_success(
            "paperwork_config_get", "workdir"
        )
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(default, "file://" + os.path.expanduser("~/papers"))

    def test_get_nondefault(self):
        self.core.get_by_name('openpaperwork_core.config_file').rets = {
            'config_get': ['file:///pouet/path']
        }

        val = self.core.call_success(
            "paperwork_config_get", "workdir"
        )
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(val, "file:///pouet/path")

    def test_get_cache(self):
        self.core.get_by_name('openpaperwork_core.config_file').rets = {
            # only one call expected
            'config_get': ['file:///pouet/path']
        }

        val1 = self.core.call_success(
            "paperwork_config_get", "workdir"
        )
        val2 = self.core.call_success(
            "paperwork_config_get", "workdir"
        )
        self.assertEqual(
            self.core.get_by_name('openpaperwork_core.config_file').calls,
            [
                ('config_get', ('Global', "WorkDirectory", None), {}),
            ]
        )
        self.assertEqual(val1, "file:///pouet/path")
        self.assertEqual(val1, val2)
