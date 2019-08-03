import unittest
import unittest.mock

import openpaperwork_core


class TestSafe(unittest.TestCase):
    def test_simple(self):
        core = openpaperwork_core.Core()
        core.load("paperwork_backend.fs.gio")
        core.init()

        v = core.call_one('fs_safe', '/home/jflesch')
        self.assertEqual(v, "file:///home/jflesch")
