import unittest

import openpaperwork_core


class MockConfigModule(object):
    class Plugin(openpaperwork_core.PluginBase):
        def get_interfaces(self):
            return ["paperwork_config"]

        def paperwork_config_get(self, opt_name):
            assert(opt_name == "workdir")
            return "file:///some_work_dir"


class TestWorkdir(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core._load_module(
            "paperwork_backend.config", MockConfigModule()
        )
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.workdir")
        self.core.init()

        self.fs = self.core.get("paperwork_backend.fs.fake")

    def test_storage_get_all_docs(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
            },
        }

        all_docs = []
        self.core.call_success("storage_get_all_docs", all_docs)
        all_docs.sort()
        self.assertEqual(
            all_docs,
            [
                ("some_doc_a", "file:///some_work_dir/some_doc_a"),
                ("some_doc_b", "file:///some_work_dir/some_doc_b"),
            ]
        )
