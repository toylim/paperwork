import os
import unittest

import openpaperwork_core


class TestLibreOfficePdf(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("paperwork_backend.converter.libreoffice")
        self.core.init()
        self.test_doc = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test.docx"
        )

    def test_convert_pdf(self):
        (tmp_url, tmp_fd) = self.core.call_success(
            "fs_mktemp", suffix=".pdf"
        )
        tmp_fd.close()
        self.core.call_success("fs_unlink", tmp_url, trash=False)
        self.assertIsNone(self.core.call_success("fs_exists", tmp_url))

        self.core.call_success(
            "convert_file_to_pdf",
            self.core.call_success("fs_safe", self.test_doc),
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
            tmp_url
        )

        self.assertTrue(self.core.call_success("fs_exists", tmp_url))
        self.core.call_success("fs_unlink", tmp_url, trash=False)
