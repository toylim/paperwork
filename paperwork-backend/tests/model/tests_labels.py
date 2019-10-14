import unittest

import openpaperwork_core


class TestLabels(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.config.fake")
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.labels")
        self.core.init()

        self.config = self.core.get_by_name("paperwork_backend.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }

        self.fs = self.core.get_by_name("paperwork_backend.fs.fake")

    def test_doc_get_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        labels = set()
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
            ]
        )

    def test_load_all_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
                "some_other_doc": {
                    "labels": (
                        "label B,#ccccbbbbaaaa\n"
                        "label C,#000011112222\n"
                    )
                },
            },
        }

        core = self.core

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def is_doc(self, doc_url):
                    return True

                def on_label_loading_end(self):
                    core.call_all("mainloop_quit_graceful")

        self.core._load_module("mainloop_stopper", FakeModule())

        self.core.call_all("sync")
        self.core.call_one("mainloop")

        labels = set()
        self.core.call_all("labels_get_all", labels)
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
                ("label C", "#000011112222"),
            ]
        )

    def test_doc_add_labels(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc": {
                    "labels": (
                        "label A,#aaaabbbbcccc\n"
                        "label B,#ccccbbbbaaaa\n"
                    )
                },
            },
        }

        self.core.call_success(
            "doc_add_label", "file:///some_work_dir/some_doc",
            label="label C", color="#123412341234"
        )

        labels = set()
        self.core.call_success(
            "doc_get_labels_by_url", labels, "file:///some_work_dir/some_doc"
        )
        labels = list(labels)
        labels.sort()

        self.assertEqual(
            labels,
            [
                ("label A", "#aaaabbbbcccc"),
                ("label B", "#ccccbbbbaaaa"),
                ("label C", "#123412341234"),
            ]
        )
