import unittest

import openpaperwork_core


class TestSysinfo(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("paperwork_backend.beacon.sysinfo")

    def test_get(self):
        # just go through the code to make sure it actually runs correctly
        # (we cannot check the output since it's system-dependant)
        out = {}
        self.core.call_all("stats_get", out)
        self.assertIn('os_name', out)
        self.assertIn('platform_architecture', out)
        self.assertIn('platform_processor', out)
        self.assertIn('platform_distribution', out)
        self.assertIn('cpu_count', out)
