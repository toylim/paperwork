import os
import unittest

import PIL.Image

import openpaperwork_core


class TestPillowImg(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.fs.gio")
        self.core.load("paperwork_backend.fs.memory")
        self.core.load("paperwork_backend.pillow.img")
        self.core.init()

        self.img_path = (
            "file://" + os.path.dirname(os.path.abspath(__file__))
            + "/test_doc.png"
        )

    def test_img_url_to_pillow(self):
        img = self.core.call_success("url_to_pillow", self.img_path)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (2380, 3364))

    def test_pillow_to_url(self):
        img = self.core.call_success("url_to_pillow", self.img_path)

        (img_url, fd) = self.core.call_success(
            "fs_mktemp", prefix="paperwork-test", suffix=".png"
        )
        fd.close()
        self.core.call_success("pillow_to_url", img, img_url, format="PNG")

        # no real way to make sure the image was correctly written I guess

        self.core.call_success("fs_unlink", img_url)
