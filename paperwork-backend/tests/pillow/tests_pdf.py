import os
import unittest

import PIL.Image

import openpaperwork_core


class TestPillowPdf(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("paperwork_backend.pillow.pdf")
        self.core.init()

        self.pdf_url = (
            "file://" + os.path.dirname(os.path.abspath(__file__))
            + "/test_doc.pdf#page=1"
        )
        self.img_path = (
            os.path.dirname(os.path.abspath(__file__)) + "/test_doc.png"
        )

    def test_pdf_url_to_pillow(self):
        pdf_as_img = self.core.call_success("url_to_pillow", self.pdf_url)

        ref_img = PIL.Image.open(self.img_path)
        ref_img.load()

        self.assertEqual(ref_img.tobytes(), pdf_as_img.tobytes())
