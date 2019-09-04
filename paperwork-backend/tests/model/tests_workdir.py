import datetime
import unittest

import openpaperwork_core


class TestWorkdir(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.config.fake")
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.workdir")
        self.core.init()

        self.config = self.core.get("paperwork_backend.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }
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

    def test_storage_get_new_doc(self):
        now = lambda: datetime.datetime(
            year=2019, month=9, day=4, hour=13, minute=27, second=10
        )

        self.fs.fs = {
            "some_work_dir": {
                "20191010_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20191010_1327_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        (doc_id, doc_url) = self.core.call_success(
            "storage_get_new_doc", now_func=now
        )
        self.assertEqual(doc_id, "20190904_1327_10")
        self.assertEqual(doc_url, "file:///some_work_dir/20190904_1327_10")
        self.assertIn('20190904_1327_10', self.fs.fs['some_work_dir'])

    def test_storage_get_new_doc_2(self):
        now = lambda: datetime.datetime(
            year=2019, month=9, day=4, hour=13, minute=27, second=10
        )

        self.fs.fs = {
            "some_work_dir": {
                "20190904_1327_10": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                },
                "20190904_1327_10_1": {
                    "doc.pdf": "put_a_pdf_here",
                },
            },
        }

        (doc_id, doc_url) = self.core.call_success(
            "storage_get_new_doc", now_func=now
        )
        self.assertEqual(doc_id, "20190904_1327_10_2")
        self.assertEqual(doc_url, "file:///some_work_dir/20190904_1327_10_2")
        self.assertIn('20190904_1327_10_2', self.fs.fs['some_work_dir'])
