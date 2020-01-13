import threading
import unittest

from .. import (Core, PluginBase)


class AbstractTestThread(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert()

    def setUp(self):
        class DummyMainloop(object):
            class Plugin(PluginBase):
                def get_interfaces(s):
                    return ['mainloop']

                def mainloop_ref(s, r):
                    pass

                def mainloop_unref(s, r):
                    pass

        self.core = Core(allow_unsatisfied=True)
        self.core._load_module("dummy_mainloop", DummyMainloop())
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_basic(self):
        out = {
            'task_a_done': False,
            'task_b_done': False,
        }
        sem = threading.Semaphore(value=0)

        def task_a():
            out['task_a_done'] = True
            sem.release()

        def task_b():
            out['task_b_done'] = True
            sem.release()

        self.core.call_one("thread_start", task_a)
        self.core.call_one("thread_start", task_b)

        for _ in range(0, 2):
            sem.acquire()

        self.assertTrue(out['task_a_done'])
        self.assertTrue(out['task_b_done'])
