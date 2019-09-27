import os
import unittest

import openpaperwork_core


class TestHocr(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.model.pdf")
        self.core.init()

        self.doc_url = "file://" + os.path.dirname(os.path.abspath(__file__))

    def test_is_doc(self):
        self.assertTrue(self.core.call_success("is_doc", self.doc_url))

    def test_hash(self):
        h = []
        self.core.call_all("doc_get_hash_by_url", h, self.doc_url)
        expected = [
            0x7d2ffb0e8ddce8f7dfbb4a8dfc14d563b272bd47b1bafb9617fbfd228bf2eecd
        ]
        self.assertEqual(h, expected)

    def test_get_nb_pages(self):
        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", self.doc_url
        )
        self.assertEqual(nb_pages, 1)

    def test_get_text(self):
        text = []
        self.core.call_all("doc_get_text_by_url", text, self.doc_url)
        self.assertEqual(text, [
            'This is a test PDF file.\n'
            'Written by Jflesch.'
        ])

    def test_get_boxes(self):
        lines = list(self.core.call_success(
            "page_get_boxes_by_url", self.doc_url, 0
        ))

        self.assertEqual(len(lines), 2)

        self.assertEqual(lines[0].position, ((227, 228), (656, 281)))
        self.assertEqual(len(lines[0].word_boxes), 6)
        self.assertEqual(lines[0].content, "This is a test PDF file.")
        self.assertEqual(
            lines[0].word_boxes[0].position, ((227, 228), (312, 281))
        )
        self.assertEqual(lines[0].word_boxes[0].content, "This")
        self.assertEqual(
            lines[0].word_boxes[1].position, ((324, 228), (356, 281))
        )
        self.assertEqual(lines[0].word_boxes[1].content, "is")
        self.assertEqual(
            lines[0].word_boxes[2].position, ((368, 228), (389, 281))
        )
        self.assertEqual(lines[0].word_boxes[2].content, "a")
        self.assertEqual(
            lines[0].word_boxes[3].position, ((401, 228), (468, 281))
        )
        self.assertEqual(lines[0].word_boxes[3].content, "test")
        self.assertEqual(
            lines[0].word_boxes[4].position, ((480, 228), (568, 281))
        )
        self.assertEqual(lines[0].word_boxes[4].content, "PDF")
        self.assertEqual(
            lines[0].word_boxes[5].position, ((580, 228), (656, 281))
        )
        self.assertEqual(lines[0].word_boxes[5].content, "file.")

        self.assertEqual(lines[1].position, ((227, 284), (588, 337)))
        self.assertEqual(lines[1].content, "Written by Jflesch.")
        self.assertEqual(len(lines[1].word_boxes), 3)
        self.assertEqual(
            lines[1].word_boxes[0].position, ((227, 284), (371, 337))
        )
        self.assertEqual(lines[1].word_boxes[0].content, "Written")
        self.assertEqual(
            lines[1].word_boxes[1].position, ((383, 284), (431, 337))
        )
        self.assertEqual(lines[1].word_boxes[1].content, "by")
        self.assertEqual(
            lines[1].word_boxes[2].position, ((443, 284), (588, 337))
        )
        self.assertEqual(lines[1].word_boxes[2].content, "Jflesch.")
