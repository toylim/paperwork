import itertools
import os
import shutil
import tempfile
import unittest

import openpaperwork_core


class TestAll(unittest.TestCase):
    def setUp(self):
        self.int_generator = itertools.count()

        self.pdf = (
            "file://" + os.path.dirname(os.path.abspath(__file__)) + "/doc.pdf"
        )

        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("paperwork_backend.model.extra_text")
        self.core.load("paperwork_backend.model.hocr")
        self.core.load("paperwork_backend.model.img")
        self.core.load("paperwork_backend.model.img_overlay")
        self.core.load("paperwork_backend.model.pdf")
        self.core.load("paperwork_backend.model.workdir")
        self.core.init()

        self.work_dir = tempfile.mkdtemp(prefix="paperwork_tests_all_")
        self.work_dir_url = "file://" + self.work_dir
        self.core.call_all("config_put", "workdir", self.work_dir_url)

        self.doc_pdf = self.core.call_success(
            "fs_join", self.work_dir_url, "20200525_1241_05"
        )
        self._copy_pdf(self.doc_pdf + "/doc.pdf")
        self._make_file(self.doc_pdf + "/paper.2.edited.jpg")
        self._make_file(self.doc_pdf + "/paper.2.words")
        self._make_file(self.doc_pdf + "/extra.txt")

        self.doc_b = self.core.call_success(
            "fs_join", self.work_dir_url, "19851212_1233_00"
        )
        self._make_file(self.doc_b + "/paper.1.jpg")
        self._make_file(self.doc_b + "/paper.1.words")
        self._make_file(self.doc_b + "/paper.2.jpg")
        self._make_file(self.doc_b + "/paper.2.words")
        self._make_file(self.doc_b + "/paper.3.jpg")
        self._make_file(self.doc_b + "/paper.3.words")
        self._make_file(self.doc_b + "/paper.3.edited.jgg")
        self._make_file(self.doc_b + "/paper.4.jpg")
        self._make_file(self.doc_b + "/paper.4.words")

        self.doc_c = self.core.call_success(
            "fs_join", self.work_dir_url, "19851224_1233_00"
        )
        self._make_file(self.doc_c + "/paper.1.jpg")
        self._make_file(self.doc_c + "/paper.1.words")
        self._make_file(self.doc_c + "/paper.2.jpg")
        self._make_file(self.doc_c + "/paper.2.words")
        self._make_file(self.doc_b + "/paper.2.edited.jgg")
        self._make_file(self.doc_c + "/paper.3.jpg")
        self._make_file(self.doc_c + "/paper.3.words")

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def _copy_pdf(self, out_pdf_url):
        dirname = self.core.call_success("fs_dirname", out_pdf_url)
        self.core.call_success("fs_mkdir_p", dirname)
        self.core.call_success("fs_copy", self.pdf, out_pdf_url)

    def _make_file(self, out_file_url):
        dirname = self.core.call_success("fs_dirname", out_file_url)
        self.core.call_success("fs_mkdir_p", dirname)
        with self.core.call_success("fs_open", out_file_url, 'w') as fd:
            fd.write("Generated content {}\n".format(next(self.int_generator)))

    def test_basic_nb_pages(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 3)

    def _get_page_hash(self, doc_url, page_idx):
        out = []
        self.core.call_all("page_get_hash_by_url", out, doc_url, page_idx)
        h = 0
        for o in out:
            h ^= o
        return h

    def test_img_page_delete(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        self.core.call_all("page_delete_by_url", self.doc_b, 2)

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 3)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 3)
        ]
        self.assertEqual(hashes[0], new_hashes[0])
        self.assertEqual(hashes[1], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[2])

    def test_img_page_move_internal(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        # 0 becomes 2
        # --> 1 becomes 0
        # --> 2 becomes 1
        self.core.call_all(
            "page_move_by_url",
            self.doc_b, 0,
            self.doc_b, 2
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[2])
        self.assertEqual(hashes[1], new_hashes[0])
        self.assertEqual(hashes[2], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_page_move_internal_reversed(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]

        # 2 becomes 0
        # --> 0 becomes 1
        # --> 1 becomes 2
        self.core.call_all(
            "page_move_by_url",
            self.doc_b, 2,
            self.doc_b, 0
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[1])
        self.assertEqual(hashes[1], new_hashes[2])
        self.assertEqual(hashes[2], new_hashes[0])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_page_move_external(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 3)
        doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        # doc_c p1 becomes doc_b p2
        # --> doc_c p2 becomes doc_c p1
        # --> doc_b p2 becomes doc_b p3
        # --> doc_b p3 becomes doc_b p4
        self.core.call_all(
            "page_move_by_url",
            self.doc_c, 1,
            self.doc_b, 2
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_b)
        self.assertEqual(nb, 5)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_b_hashes = [
            self._get_page_hash(self.doc_b, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_b_hashes[0], new_doc_b_hashes[0])
        self.assertEqual(doc_b_hashes[1], new_doc_b_hashes[1])
        self.assertEqual(doc_b_hashes[2], new_doc_b_hashes[3])
        self.assertEqual(doc_b_hashes[3], new_doc_b_hashes[4])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_b_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

    def test_pdf_hashes(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # just make sure all the hashes are different from one another
        for (e, h) in enumerate(hashes):
            for i in hashes[e + 1:]:
                self.assertNotEqual(h, i)

    def test_pdf_page_delete(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        self.core.call_all("page_delete_by_url", self.doc_pdf, 2)

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 3)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 3)
        ]
        self.assertEqual(hashes[0], new_hashes[0])
        self.assertEqual(hashes[1], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[2])

    def test_pdf_page_move_internal(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # 0 becomes 2
        # --> 1 becomes 0
        # --> 2 becomes 1
        self.core.call_all(
            "page_move_by_url",
            self.doc_pdf, 0,
            self.doc_pdf, 2
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[2])
        self.assertEqual(hashes[1], new_hashes[0])
        self.assertEqual(hashes[2], new_hashes[1])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_pdf_page_move_internal_reversed(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]

        # 2 becomes 0
        # --> 0 becomes 1
        # --> 1 becomes 2
        self.core.call_all(
            "page_move_by_url",
            self.doc_pdf, 2,
            self.doc_pdf, 0
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        new_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        self.assertEqual(hashes[0], new_hashes[1])
        self.assertEqual(hashes[1], new_hashes[2])
        self.assertEqual(hashes[2], new_hashes[0])
        self.assertEqual(hashes[3], new_hashes[3])

    def test_img_to_pdf_page_move_then_delete(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 3)
        doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        # doc_c p1 becomes doc_pdf p2
        # --> doc_c p2 becomes doc_c p1
        # --> doc_pdf p2 becomes doc_pdf p3
        # --> doc_pdf p3 becomes doc_pdf p4
        self.core.call_all(
            "page_move_by_url",
            self.doc_c, 1,
            self.doc_pdf, 2
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 5)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 5)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[3])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[4])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[1], new_doc_pdf_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

        # we delete the added img page
        self.core.call_all("page_delete_by_url", self.doc_pdf, 2)

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 2)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 2)
        ]
        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[3])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[1])

    def test_pdf_to_img_page_move(self):
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 4)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 3)
        doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 4)
        ]
        doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 3)
        ]

        # doc_pdf p3 becomes doc_c p2
        # --> doc_c p2 becomes doc_c p3
        # --> doc_c p2 becomes doc_c p3
        # --> doc_pdf p4 becomes doc_pdf p3
        self.core.call_all(
            "page_move_by_url",
            self.doc_pdf, 2,
            self.doc_c, 1
        )

        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_pdf)
        self.assertEqual(nb, 3)
        nb = self.core.call_success("doc_get_nb_pages_by_url", self.doc_c)
        self.assertEqual(nb, 4)
        new_doc_pdf_hashes = [
            self._get_page_hash(self.doc_pdf, page_idx)
            for page_idx in range(0, 3)
        ]
        new_doc_c_hashes = [
            self._get_page_hash(self.doc_c, page_idx)
            for page_idx in range(0, 4)
        ]

        # in that case, an image page has been generated from the PDF page
        # --> hash of the new image page won't match the PDF hash

        self.assertEqual(doc_pdf_hashes[0], new_doc_pdf_hashes[0])
        self.assertEqual(doc_pdf_hashes[1], new_doc_pdf_hashes[1])
        self.assertNotEqual(doc_pdf_hashes[2], new_doc_pdf_hashes[2])
        self.assertEqual(doc_pdf_hashes[3], new_doc_pdf_hashes[2])

        self.assertEqual(doc_c_hashes[0], new_doc_c_hashes[0])
        self.assertNotEqual(doc_c_hashes[1], new_doc_c_hashes[1])
        self.assertEqual(doc_c_hashes[1], new_doc_c_hashes[2])
        self.assertEqual(doc_c_hashes[2], new_doc_c_hashes[3])
