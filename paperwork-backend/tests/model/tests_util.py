import unittest

import openpaperwork_core

import paperwork_backend.model.util


class TestUtil(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.fs.fake")
        self.core.init()

        self.fs = self.core.get_by_name("paperwork_backend.fs.fake")

    def test_delete_page_file(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.words": "abcdef",
                "paper.2.words": "ghijkl",
                "paper.3.words": "mnopqr",
                "paper.4.words": "stuvwx",
            },
        }

        r = paperwork_backend.model.util.delete_page_file(
            self.core, "file:///some_doc", "paper.{}.words", 1
        )
        self.assertTrue(r)

        self.assertEqual(
            self.fs.fs,
            {
                "some_doc": {
                    "paper.1.words": "abcdef",
                    "paper.2.words": "mnopqr",
                    "paper.3.words": "stuvwx",
                },
            }
        )
