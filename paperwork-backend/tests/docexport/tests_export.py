import os
import unittest

import openpaperwork_core
import openpaperwork_core.promise


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
        self.result = result

    def test_pdf_to_img(self):
        pipeline = [
            self.core.call_success("export_get_pipe_by_name", "img_boxes"),
            self.core.call_success("export_get_pipe_by_name", "unpaper"),
            self.core.call_success("export_get_pipe_by_name", "swt_soft"),
            self.core.call_success("export_get_pipe_by_name", "png"),
        ]

        def origin():
            return (self.test_doc_pdf_url, 0)  # 1st page of the PDF

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(pipe.get_promise(result='preview'))
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise = promise.schedule()
        self.core.call_one("mainloop")

        self.assertTrue(self.result.startswith("memory://"))
        self.core.call_all("fs_unlink", self.result, trash=False)

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

        self.assertTrue(self.core.call_success("fs_getsize", self.result) > 0)
        self.core.call_all("fs_unlink", self.result, trash=False)

    def test_img_to_pdf(self):
        pipeline = [
            self.core.call_success("export_get_pipe_by_name", "img_boxes"),
            self.core.call_success("export_get_pipe_by_name", "unpaper"),
            self.core.call_success("export_get_pipe_by_name", "swt_soft"),
            self.core.call_success("export_get_pipe_by_name", "generated_pdf"),
        ]

        def origin():
            return (self.test_doc_img_url, 0)  # 1st page of the image doc

        promise = openpaperwork_core.promise.Promise(self.core, origin)
        for pipe in pipeline:
            promise = promise.then(pipe.get_promise(result='preview'))
        promise = promise.then(self.set_result)
        promise = promise.then(self.core.call_all, "mainloop_quit_graceful")
        promise = promise.schedule()
        self.core.call_one("mainloop")

        # required by Poppler
        self.assertTrue(self.result.startswith("file://"))
        self.core.call_all("fs_unlink", self.result, trash=False)

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

        self.assertTrue(self.core.call_success("fs_getsize", self.result) > 0)
        self.core.call_all("fs_unlink", self.result, trash=False)
