import os
import shutil
import tempfile
import unittest

import PIL
import PIL.Image

import openpaperwork_core


class TestPyocr(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.test_img = PIL.Image.open(
            "{}/test_img.png".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.doctracker")
        self.core.load("paperwork_backend.pagetracker")
        self.core.load("paperwork_backend.guesswork.ocr.pyocr")

        self.core.get_by_name(
            "paperwork_backend.pagetracker"
        ).paperwork_dir = self.tmp_paperwork_dir
        self.core.get_by_name(
            "paperwork_backend.doctracker"
        ).paperwork_dir = self.tmp_paperwork_dir

        self.core.init()

        self.model = self.core.get_by_name("paperwork_backend.model.fake")

        self.core.call_all("config_put", "ocr_langs", ["eng"])

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)

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
                "page_hashes": [
                    ("file:///some_image.png", 0),
                ]
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
                "page_hashes": [
                    ("file:///paper.0.png", 0),
                    ("file:///paper.1.png", 1),
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
                "page_hashes": [
                    ("file:///some_image.png", 3),
                ],
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        transactions.sort(key=lambda transaction: -transaction.priority)
        self.assertNotEqual(transactions, [])

        for t in transactions:
            t.add_obj('some_doc_with_text')
        for t in transactions:
            t.add_obj('some_doc')
        for t in transactions:
            t.commit()

        # first doc already had boxes --> no boxes or text added
        self.assertNotIn('text', self.model.docs[0])
        self.assertEqual(self.model.docs[0]['page_boxes'], [
            "putsomething", "here"  # unchanged
        ])

        # but OCR should be run on the other doc
        self.assertNotEqual(len(self.model.docs[1]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[1]['text'],
            "This is a test\n"
            "image created\n"
            "by Flesch\n"
        )

    def test_tricky(self):
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
                    ("file:///paper.0.png", self.test_img),
                    ("file:///paper.1.png", self.test_img),
                ],
                "page_hashes": [
                    ("file:///paper.0.png", 0),
                    ("file:///paper.1.png", 1),
                ],
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.add_obj('some_doc_with_text')
        for t in transactions:
            t.commit()

        # first doc already had boxes --> no boxes or text added
        self.assertNotIn('text', self.model.docs[0])
        self.assertEqual(self.model.docs[0]['page_boxes'], [
            "putsomething", "here"  # unchanged
        ])

        self.model.docs = [
            {
                "id": 'some_doc_with_text',
                "url": 'file:///some_work_dir/some_doc_id',
                "mtime": 12346,
                "labels": [],
                "page_boxes": [],
                "page_imgs": [
                    ("file:///paper.0.png", self.test_img),  # new page
                    ("file:///paper.1.png", self.test_img),
                    ("file:///paper.2.png", self.test_img),  # modified
                ],
                "page_hashes": [
                    ("file:///paper.0.png", 0xDEADBEEF),  # new page
                    ("file:///paper.1.png", 0),
                    ("file:///paper.2.png", 0xBEEFDEAD),  # modified
                ],
            },
        ]

        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertNotEqual(transactions, [])
        for t in transactions:
            t.upd_obj('some_doc_with_text')
        for t in transactions:
            t.commit()

        self.assertNotEqual(len(self.model.docs[0]['page_boxes']), 0)
        self.assertEqual(
            self.model.docs[0]['text'],
            "This is a test\n"  # new page
            "image created\n"  # new page
            "by Flesch\n"  # new page
            "\n\n"
            # unchanged page --> no OCR
            "\n\n"
            "This is a test\n"  # modified page
            "image created\n"  # modified page
            "by Flesch\n"  # modified page
        )
