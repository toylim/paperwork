import unittest

import openpaperwork_core


class TestImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.img_overlay")
        self.core.init()

        self.fs = self.core.get_by_name("paperwork_backend.fs.fake")

    def test_get_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.jpg")

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 3, write=False
        )
        self.assertEqual(img_url, None)

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 3, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.4.jpg")

    def test_get_edited_img_urls(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.2.edited.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
            },
        }

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 1, write=False
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

        img_url = self.core.call_success(
            "page_get_img_url", "file:///some_doc", 1, write=True
        )
        self.assertEqual(img_url, "file:///some_doc/paper.2.edited.jpg")

    def test_reset_img(self):
        self.fs.fs = {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.2.edited.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        }

        self.core.call_all(
            "page_reset_by_url", "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        })

        self.core.call_all(
            "page_reset_by_url", "file:///some_doc", 1
        )

        self.assertEqual(self.fs.fs, {
            "some_doc": {
                "paper.1.jpg": "put_an_image_here",
                "paper.2.jpg": "put_an_image_here",
                "paper.3.jpg": "put_an_image_here",
                "paper.3.edited.jpg": "put_an_image_here",
            },
        })
