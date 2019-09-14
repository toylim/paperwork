import os
import unittest

import PIL
import PIL.Image

import openpaperwork_core


class TestPyocr(unittest.TestCase):
    def setUp(self):
        self.test_img = PIL.Image.open(
            "{}/test_img.png".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.ocr.pyocr")
        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

        self.core.call_all("paperwork_config_put", "ocr_lang", "eng")

    def test_ocr(self):
        self.model.docs = [
            {
                "id": 'some_id',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///some_image.png", self.test_img)
                ],
            },
        ]

        self.core.call_all(
            "ocr_page_by_url", "file:///some_work_dir/some_doc_id", page_idx=0
        )

        self.assertNotEqual(len(self.model.docs[0]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[0]['text'],
            "This is a test\n"
            "image created\n"
            "by Flesch\n"
        )

    def test_transaction(self):
        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [
                    # Should be list of LineBoxes, but meh.
                    "putsomething",
                    "here"
                ],
                "page_imgs": [
                    ("file:///paper.0.png", None),
                    ("file:///paper.1.png", None),
                ],
            },
            {
                "id": 'some_doc',
                "url": 'file:///some_work_dir/some_2',
                "mtime": 12345,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///some_image.png", self.test_img)
                ],
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertNotEqual(transactions, [])

        for t in transactions:
            t.add_obj('some_doc_with_text')
        for t in transactions:
            t.add_obj('some_doc')
        for t in transactions:
            t.commit()

        # first doc already had boxes --> no boxes or text added
        self.assertNotIn('text', self.model.docs[0])

        # but OCR should be run on the other doc
        print(self.model.docs)
        self.assertNotEqual(len(self.model.docs[1]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[1]['text'],
            "This is a test\n"
            "image created\n"
            "by Flesch\n"
        )
