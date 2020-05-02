import os
import unittest

import openpaperwork_core
import openpaperwork_core.promise

import paperwork_backend.docexport


class TestExport(unittest.TestCase):
    def setUp(self):
        self.test_doc_pdf_url = (
            "file://{}/test_pdf_doc".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        self.test_doc_img_url = (
            "file://{}/test_img_doc".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_gtk.fs.gio")
        self.core.load("openpaperwork_core.fs.memory")
        self.core.load("paperwork_backend.docexport.img")
        self.core.load("paperwork_backend.docexport.pdf")
        self.core.load("paperwork_backend.docexport.pillowfight")
        self.core.init()

        self.result = None

    def set_result(self, result):
        self.result = list(result)

    def test_pdf_to_img(self):
        pipeline = [
            self.core.call_success("export_get_pipe_by_name", "img_boxes"),
            self.core.call_success("export_get_pipe_by_name", "unpaper"),
            self.core.call_success("export_get_pipe_by_name", "swt_soft"),
            self.core.call_success("export_get_pipe_by_name", "png"),
        ]

        def origin():
            return paperwork_backend.docexport.ExportData.build_page(
                # 1st page of the PDF
                "some_doc_id", self.test_doc_pdf_url, 0
            )

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(pipe.get_promise(result='preview'))
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise = promise.schedule()
        self.core.call_one("mainloop")

        self.assertEqual(len(self.result), 1)
        self.assertTrue(self.result[0].startswith("memory://"))
        self.core.call_all("fs_unlink", self.result[0], trash=False)

        (tmp_file, fd) = self.core.call_success(
            "fs_mktemp", prefix="paperwork-test-", suffix=".png"
        )
        fd.close()

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(
                pipe.get_promise(result='final', target_file_url=tmp_file)
            )
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise.schedule()
        self.core.call_one("mainloop")

        self.assertEqual(len(self.result), 1)
        self.assertTrue(
            self.core.call_success("fs_getsize", self.result[0]) > 0
        )
        self.core.call_all("fs_unlink", self.result[0], trash=False)

    def test_img_to_pdf(self):
        pipeline = [
            self.core.call_success("export_get_pipe_by_name", "img_boxes"),
            self.core.call_success("export_get_pipe_by_name", "unpaper"),
            self.core.call_success("export_get_pipe_by_name", "swt_soft"),
            self.core.call_success("export_get_pipe_by_name", "generated_pdf"),
        ]

        def origin():
            return paperwork_backend.docexport.ExportData.build_page(
                # 1st page of the image doc
                "some_doc_id", self.test_doc_img_url, 0
            )

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(pipe.get_promise(result='preview'))
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise = promise.schedule()
        self.core.call_one("mainloop")

        # required by Poppler
        self.assertEqual(len(self.result), 1)
        self.assertTrue(self.result[0].startswith("file://"))
        self.core.call_all("fs_unlink", self.result[0], trash=False)

        (tmp_file, fd) = self.core.call_success(
            "fs_mktemp", prefix="paperwork-test-", suffix=".png"
        )
        fd.close()

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(
                pipe.get_promise(result='final', target_file_url=tmp_file)
            )
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise.schedule()
        self.core.call_one("mainloop")

        self.assertEqual(len(self.result), 1)
        self.assertTrue(self.core.call_success(
            "fs_getsize", self.result[0]
        ) > 0)
        self.core.call_all("fs_unlink", self.result[0], trash=False)
