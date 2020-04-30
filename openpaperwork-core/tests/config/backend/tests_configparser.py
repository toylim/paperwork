import datetime
import shutil
import tempfile
import unittest
import unittest.mock

import openpaperwork_core


class TestReadWrite(unittest.TestCase):
    def test_simple_getset(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.init()

        core.call_all(
            'config_backend_put', 'test_section', 'test_key', 'test_value'
        )
        v = core.call_one('config_backend_get', 'test_section', 'test_key')
        self.assertEqual(v, 'test_value')

        v = core.call_one(
            'config_backend_get', 'wrong_section', 'test_key', 'default'
        )
        self.assertEqual(v, 'default')

        self.assertIsNone(
            core.call_success(
                'config_backend_get', 'test_section', 'wrong_key'
            )
        )

        core.call_all('config_add_plugin', 'some_opt', 'some_test_module')

    def test_no_config_file(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        try:
            core.init()

            # must not throw an exception
            core.call_all('config_backend_load', 'openpaperwork_test')
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))

    def test_simple_readwrite(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        try:
            core.init()

            core.call_all(
                'config_backend_put', 'test_section', 'test_key', 'test_value'
            )
            core.call_all(
                'config_backend_add_plugin', 'some_opt', 'some_test_module'
            )
            core.call_all('config_backend_save', 'openpaperwork_test')

            core.call_all('config_backend_load', 'openpaperwork_test')
            v = core.call_one('config_backend_get', 'test_section', 'test_key')
            self.assertEqual(v, 'test_value')
            v = core.call_one(
                'config_backend_get', 'wrong_section', 'test_key', 'default'
            )
            self.assertEqual(v, 'default')
            self.assertIsNone(
                core.call_success(
                    'config_backend_get', 'test_section', 'wrong_key'
                )
            )
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))

    def test_observers(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        class Observer(object):
            def __init__(self):
                self.count = 0

            def obs(self):
                self.count += 1

        try:
            core.init()

            obs = Observer()
            core.call_all(
                'config_backend_add_observer', 'test_section', obs.obs
            )

            core.call_all(
                'config_backend_put', 'other_section', 'test_key', 'test_value'
            )
            self.assertEqual(obs.count, 0)

            core.call_all(
                'config_backend_put', 'test_section', 'test_key', 'test_value'
            )
            self.assertEqual(obs.count, 1)

            core.call_all(
                'config_backend_add_plugin', 'some_opt', 'some_test_module'
            )
            self.assertEqual(obs.count, 1)

            core.call_all('config_backend_save', 'openpaperwork_test')
            self.assertEqual(obs.count, 1)

            core.call_all('config_backend_load', 'openpaperwork_test')
            self.assertEqual(obs.count, 2)
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))

    def test_simple_readwrite_list(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        try:
            core.init()

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default=["test_value_a", "test_value_b"]
            )
            self.assertNotEqual(v, None)
            self.assertEqual(len(v), 2)

            v[1] = 'test_value_c'
            core.call_all('config_backend_put', 'test_section', 'test_key', v)

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default=["test_value_a", "test_value_b"]
            )
            self.assertEqual(len(v), 2)
            self.assertEqual(v[1], "test_value_c")

            core.call_all('config_backend_save', 'openpaperwork_test')
            core.call_all('config_backend_load', 'openpaperwork_test')

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default=["test_value_a", "test_value_b"]
            )
            self.assertEqual(len(v), 2)
            self.assertEqual(v[1], "test_value_c")
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))

    def test_simple_readwrite_dict(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        try:
            core.init()

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default={
                    "test_key_a": "test_key_b",
                    "test_key_b": "test_value_b"
                }
            )
            self.assertNotEqual(v, None)
            self.assertEqual(len(v), 2)

            v['test_key_b'] = 'test_value_c'
            core.call_all('config_backend_put', 'test_section', 'test_key', v)

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default={
                    "test_key_a": "test_key_b",
                    "test_key_b": "test_value_b"
                }
            )
            self.assertEqual(len(v), 2)
            self.assertEqual(v['test_key_b'], "test_value_c")

            core.call_all('config_backend_save', 'openpaperwork_test')
            core.call_all('config_backend_load', 'openpaperwork_test')

            v = core.call_success(
                'config_backend_get', 'test_section', 'test_key',
                default={
                    "test_key_a": "test_key_b",
                    "test_key_b": "test_value_b"
                }
            )
            self.assertEqual(len(v), 2)
            self.assertEqual(v['test_key_b'], "test_value_c")
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))

    def test_getset_date(self):
        core = openpaperwork_core.Core(allow_unsatisfied=True)
        core.load('openpaperwork_core.config.backend.configparser')

        core.get_by_name(
            'openpaperwork_core.config.backend.configparser'
        ).base_path = (
            tempfile.mkdtemp(prefix='openpaperwork_core_config_tests')
        )

        try:
            core.init()

            core.call_all(
                'config_backend_put', 'test_section', 'test_key',
                datetime.date(year=1985, month=1, day=1)
            )
            core.call_all('config_backend_save', 'openpaperwork_test')

            core.call_all('config_backend_load', 'openpaperwork_test')
            v = core.call_one('config_backend_get', 'test_section', 'test_key')
            self.assertEqual(v, datetime.date(year=1985, month=1, day=1))
        finally:
            shutil.rmtree(core.call_success("fs_unsafe", core.get_by_name(
                'openpaperwork_core.config.backend.configparser'
            ).base_path))
