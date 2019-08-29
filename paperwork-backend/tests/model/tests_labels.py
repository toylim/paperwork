import unittest

import openpaperwork_core


class TestLabels(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.labels")
        self.core.init()

        self.fs = self.core.get("paperwork_backend.fs.fake")

    def test_get_labels(self):
        self.fs.fs = {
            "some_doc": {
                "labels": (
                    "label A,#aaaabbbbcccc\n"
                    "label B,#ccccbbbbaaaa\n"
                )
            },
        }

        labels = []
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_doc"
        )
        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
            ]
        )
