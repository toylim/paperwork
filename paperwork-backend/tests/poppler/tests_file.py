import cairo
import gc
import os
import unittest

import openpaperwork_core


class TestFileDescriptorLeak(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_fd_leak(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.file")
        self.core.init()

        self.simple_doc_url = self.core.call_success(
            "fs_safe",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_doc.pdf"
            )
        )

        gc.collect()
        gc.collect()

        our_pid = os.getpid()
        our_fds_dir = self.core.call_success(
            "fs_safe", "/proc/{}/fd".format(our_pid)
        )

        current_fds = self.core.call_success("fs_listdir", our_fds_dir)
        current_fds = list(current_fds)
        current_fds.sort()

        doc = self.core.call_success("poppler_open", self.simple_doc_url)
        self.assertIsNotNone(doc)

        new_fds = self.core.call_success("fs_listdir", our_fds_dir)
        new_fds = list(new_fds)
        new_fds.sort()
        self.assertNotEqual(current_fds, new_fds)

        doc = None
        gc.collect()
        gc.collect()

        new_fds = self.core.call_success("fs_listdir", our_fds_dir)
        new_fds = list(new_fds)
        new_fds.sort()
        self.assertEqual(current_fds, new_fds)

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_fd_leak2(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.file")
        self.core.init()

        self.simple_doc_url = self.core.call_success(
            "fs_safe",
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "test_doc.pdf"
            )
        )

        gc.collect()
        gc.collect()

        our_pid = os.getpid()
        our_fds_dir = self.core.call_success(
            "fs_safe", "/proc/{}/fd".format(our_pid)
        )

        current_fds = self.core.call_success("fs_listdir", our_fds_dir)
        current_fds = list(current_fds)
        current_fds.sort()

        doc = self.core.call_success("poppler_open", self.simple_doc_url)
        self.assertIsNotNone(doc)
        page = doc.get_page(0)

        new_fds = self.core.call_success("fs_listdir", our_fds_dir)
        new_fds = list(new_fds)
        new_fds.sort()
        self.assertNotEqual(current_fds, new_fds)

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        ctx = cairo.Context(surface)
        page.render(ctx)

        doc = None
        gc.collect()
        gc.collect()

        new_fds = self.core.call_success("fs_listdir", our_fds_dir)
        new_fds = list(new_fds)
        new_fds.sort()

        # XXX(JFlesch):
        # And here we got a very nice file description leak
        # self.assertEqual(len(current_fds), len(new_fds))
