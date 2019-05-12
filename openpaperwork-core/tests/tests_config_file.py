import tempfile
import unittest
import unittest.mock

import openpaperwork_core


class TestReadWrite(unittest.TestCase):
    def test_simple_getset(self):
        core = openpaperwork_core.Core()
        core.load('openpaperwork_core.config_file')

        core.init()

        core.call_all('config_put', 'test_section', 'test_key', 'test_value')
        v = core.call_one('config_get', 'test_section', 'test_key')
        self.assertEqual(v, 'test_value')

        v = core.call_one('config_get', 'wrong_section', 'test_key', 'default')
        self.assertEqual(v, 'default')

        with self.assertRaises(KeyError):
            core.call_one('config_get', 'test_section', 'wrong_key')

        core.call_all('config_add_plugin', 'some_test_module')

    def test_simple_readwrite(self):
        core = openpaperwork_core.Core()
        core.load('openpaperwork_core.config_file')

        core.get('openpaperwork_core.config_file').base_path = tempfile.mkdtemp(
            prefix='openpaperwork_core_config_tests'
        )

        core.init()

        core.call_all('config_put', 'test_section', 'test_key', 'test_value')
        core.call_all('config_add_plugin', 'some_test_module')
        core.call_all('config_save', 'openpaperwork_test')

        core.call_all('config_load', 'openpaperwork_test')
        v = core.call_one('config_get', 'test_section', 'test_key')
        self.assertEqual(v, 'test_value')
        v = core.call_one('config_get', 'wrong_section', 'test_key', 'default')
        self.assertEqual(v, 'default')
        with self.assertRaises(KeyError):
            core.call_one('config_get', 'test_section', 'wrong_key')

    @unittest.mock.patch("importlib.import_module")
    def test_simple_load_module(self, import_module):
        import openpaperwork_core.config_file

        core = openpaperwork_core.Core()

        import_module.return_value = openpaperwork_core.config_file
        core.load('openpaperwork_core.config_file')
        import_module.assert_called_once_with('openpaperwork_core.config_file')

        core.init()

        class TestModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.initialized = False

                def init(self):
                    self.initialized = True

        core.call_all('config_add_plugin', 'some_test_module')
        core.call_all('config_add_plugin', 'some_test_module_2')

        import_module.reset_mock()
        import_module.side_effect = [TestModule(), TestModule()]
        core.call_all('config_load_plugins', core)
        import_module.assert_called_with('some_test_module_2')

        self.assertEqual(core.get('some_test_module').initialized, True)
        self.assertEqual(core.get('some_test_module_2').initialized, True)
