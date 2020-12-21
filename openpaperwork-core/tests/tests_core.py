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

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModule()
        core.load('whatever_module')
        import_module.assert_called_once_with('whatever_module')

        core.init()
        self.assertTrue(core.get_by_name('whatever_module').init_called)

        core.call_all('test_method')
        self.assertTrue(core.get_by_name('whatever_module').test_method_called)


class TestInit(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_init_order(self, import_module):
        global g_idx
        g_idx = 0

        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_a = -1

                def get_interfaces(self):
                    return ['module_a']

                def init(self, core):
                    global g_idx
                    self.init_called_a = g_idx
                    g_idx += 1

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_b = -1

                def get_interfaces(self):
                    return ['module_b']

                def get_deps(self):
                    return [
                        {
                            'interface': 'module_a',
                            'defaults': ['module_a'],
                        }
                    ]

                def init(self, core):
                    global g_idx
                    self.init_called_b = g_idx
                    g_idx += 1

        class TestModuleC(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called_c = -1

                def get_deps(self):
                    return [
                        {
                            'interface': 'module_b',
                            'defaults': ['module_b'],
                            'expected_already_satisfied': False,
                        }
                    ]

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

        self.assertEqual(core.get_by_name('module_a').init_called_a, 0)
        self.assertEqual(core.get_by_name('module_b').init_called_b, 1)
        self.assertEqual(core.get_by_name('module_c').init_called_c, 2)


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
                    return [
                        {
                            'interface': 'test_interface',
                            'defaults': ['module_a', 'module_b']
                        },
                    ]

                def init(self, core):
                    self.init_called_c = True

                def test_method(self):
                    self.test_method_called_c = True

        core = openpaperwork_core.Core(auto_load_dependencies=True)

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

        self.assertTrue(core.get_by_name('module_b').init_called_b)
        self.assertTrue(core.get_by_name('module_c').init_called_c)

        core.call_all('test_method')
        self.assertTrue(core.get_by_name('module_b').test_method_called_b)
        self.assertTrue(core.get_by_name('module_c').test_method_called_c)

    @unittest.mock.patch("importlib.import_module")
    def test_call_success_priority(self, import_module):
        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 33

                def __init__(self):
                    self.test_method_called_b = False

                def test_method(self):
                    self.test_method_called_b = True
                    return None

        class TestModuleC(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 22

                def __init__(self):
                    self.test_method_called_c = False

                def test_method(self):
                    self.test_method_called_c = True
                    return "value"

        class TestModuleD(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 11

                def __init__(self):
                    self.test_method_called_d = False

                def test_method(self):
                    self.test_method_called_d = True
                    return None

        core = openpaperwork_core.Core(auto_load_dependencies=True)

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
        self.assertTrue(core.get_by_name('module_b').test_method_called_b)
        self.assertTrue(core.get_by_name('module_c').test_method_called_c)
        self.assertFalse(core.get_by_name('module_d').test_method_called_d)

    @unittest.mock.patch("importlib.import_module")
    def test_priority(self, import_module):
        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 22

                def test_method(self):
                    return "A"

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 33

                def test_method(self):
                    return "B"

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleA()
        core.load('module_a')
        import_module.assert_called_once_with('module_a')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        core.init()

        r = core.call_success('test_method')
        self.assertEqual(r, "B")


class TestDependencies(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_default_interface(self, import_module):
        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called = False
                    self.test_method_called = False

                def get_interfaces(self):
                    return [
                        "test_interface",
                        "some_interface",
                    ]

                def init(self, core):
                    self.init_called = True

                def test_method(self):
                    self.test_method_called = True

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(self):
                    self.init_called = False

                def get_interfaces(self):
                    return ['some_interface']

                def get_deps(self):
                    return [
                        {
                            'interface': 'test_interface',
                            'defaults': ['module_a'],
                        }
                    ]

                def init(self, core):
                    self.init_called = True

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleA()
        core.init()  # will load 'module_a' because of dependencies
        import_module.assert_called_once_with('module_a')
        self.assertTrue(core.get_by_name('module_a').init_called)
        self.assertTrue(core.get_by_name('module_b').init_called)

        core.call_all('test_method')
        self.assertTrue(core.get_by_name('module_a').test_method_called)

        self.assertEqual(
            core.get_by_interface('some_interface'),
            [
                core.get_by_name('module_b'),
                core.get_by_name('module_a'),
            ]
        )
        self.assertEqual(core.get_by_interface('unknown_interface'), [])

    @unittest.mock.patch("importlib.import_module")
    def test_no_init_if_dropped(self, import_module):
        self.init_called = False

        class TestModuleA(object):
            class Plugin(openpaperwork_core.PluginBase):
                def get_interfaces(s):
                    return [
                        "test_interface",
                        "some_interface",
                    ]

                def init(s, core):
                    self.init_called = True

        class TestModuleB(object):
            class Plugin(openpaperwork_core.PluginBase):
                def __init__(s):
                    s.init_called = False

                def get_interfaces(s):
                    return ['some_interface']

                def get_deps(s):
                    return [
                        {
                            'interface': 'test_interface',
                            'defaults': ['module_a'],
                        }
                    ]

                def init(s, core):
                    self.init_called = True

        core = openpaperwork_core.Core(auto_load_dependencies=False)

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleA()
        core.init()  # will NOT load 'module_a' and will drop 'module_b'
        self.assertFalse(self.init_called)
        self.assertRaises(KeyError, core.get_by_name, 'module_a')
        self.assertRaises(KeyError, core.get_by_name, 'module_b')
