import unittest

import openpaperwork_core


class TestImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.init()

        self.fs = self.core.get_by_name("paperwork_backend.fs.fake")

    def test_get_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
            },
        }

        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", "file:///non_existing"
        )
        self.assertIsNone(nb_pages)
        nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", "file:///some_doc"
        )
        self.assertEqual(nb_pages, 2)

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 1
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.jpg")

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 2
        )
        self.assertIsNone(img_url)
