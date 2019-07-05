import unittest
import unittest.mock

import openpaperwork_core


class TestLoading(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_simple_loading(self, import_module):
        class TestModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called = False
                    self.test_method_called = False

                def init(self, core):
                    self.init_called = True

                def test_method(self):
                    self.test_method_called = True

        core = openpaperwork_core.Core()

        import_module.return_value = TestModule()
        core.load('whatever_module')
        import_module.assert_called_once_with('whatever_module')

        core.init()
        self.assertTrue(core.get('whatever_module').init_called)

        core.call_all('test_method')
        self.assertTrue(core.get('whatever_module').test_method_called)

    @unittest.mock.patch("importlib.import_module")
    def test_default_interface(self, import_module):
        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called = False
                    self.test_method_called = False

                def get_interfaces(self):
                    return ["test_interface"]

                def init(self, core):
                    self.init_called = True

                def test_method(self):
                    self.test_method_called = True

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called = False

                def get_deps(self):
                    return {
                        'plugins': [],
                        'interfaces': [
                            ('test_interface', ['module_a']),
                        ],
                    }

                def init(self, core):
                    self.init_called = True

        core = openpaperwork_core.Core()

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleA()
        core.init()  # will load 'module_a' because of dependencies
        import_module.assert_called_once_with('module_a')
        self.assertTrue(core.get('module_a').init_called)
        self.assertTrue(core.get('module_b').init_called)

        core.call_all('test_method')
        self.assertTrue(core.get('module_a').test_method_called)


class TestInit(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_init_order(self, import_module):
        global g_idx
        g_idx = 0

        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_a = -1

                def init(self, core):
                    global g_idx
                    self.init_called_a = g_idx
                    g_idx += 1

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_b = -1

                def get_deps(self):
                    return {
                        'plugins': ['module_a'],
                    }

                def init(self, core):
                    global g_idx
                    self.init_called_b = g_idx
                    g_idx += 1

        class TestModuleC(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_c = -1

                def get_deps(self):
                    return {
                        'plugins': ['module_b'],
                    }

                def init(self, core):
                    global g_idx
                    self.init_called_c = g_idx
                    g_idx += 1

        core = openpaperwork_core.Core()

        import_module.return_value = TestModuleA()
        core.load('module_a')
        import_module.assert_called_once_with('module_a')

        import_module.reset_mock()
        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.init()  # will load 'module_b' because of dependencies
        import_module.assert_called_once_with('module_b')

        self.assertEqual(core.get('module_a').init_called_a, 0)
        self.assertEqual(core.get('module_b').init_called_b, 1)
        self.assertEqual(core.get('module_c').init_called_c, 2)


class TestCall(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_default_interface(self, import_module):
        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_b = False
                    self.test_method_called_b = False

                def get_interfaces(self):
                    return ["test_interface"]

                def init(self, core):
                    self.init_called_b = True

                def test_method(self):
                    self.test_method_called_b = True

        class TestModuleC(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_c = False
                    self.test_method_called_c = False

                def get_deps(self):
                    return {
                        'plugins': [],
                        'interfaces': [
                            ('test_interface', [
                                'module_a',
                                'module_b',
                            ]),
                        ],
                    }

                def init(self, core):
                    self.init_called_c = True

                def test_method(self):
                    self.test_method_called_c = True

        core = openpaperwork_core.Core()

        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        # interface already satisfied --> won't load 'module_a'
        core.init()

        self.assertTrue(core.get('module_b').init_called_b)
        self.assertTrue(core.get('module_c').init_called_c)

        core.call_all('test_method')
        self.assertTrue(core.get('module_b').test_method_called_b)
        self.assertTrue(core.get('module_c').test_method_called_c)

    @unittest.mock.patch("importlib.import_module")
    def test_call_success(self, import_module):
        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.test_method_called_b = False

                def test_method(self):
                    self.test_method_called_b = True
                    return None

        class TestModuleC(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.test_method_called_c = False

                def test_method(self):
                    self.test_method_called_c = True
                    return "value"

        class TestModuleD(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.test_method_called_d = False

                def test_method(self):
                    self.test_method_called_d = True
                    return None

        core = openpaperwork_core.Core()

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleD()
        core.load('module_d')
        import_module.assert_called_once_with('module_d')

        import_module.reset_mock()
        # interface already satisfied --> won't load 'module_a'
        core.init()

        r = core.call_success('test_method')
        self.assertEqual(r, "value")
        self.assertTrue(core.get('module_b').test_method_called_b)
        self.assertTrue(core.get('module_c').test_method_called_c)
        self.assertFalse(core.get('module_d').test_method_called_d)
