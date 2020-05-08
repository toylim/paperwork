import cairo
import gc
import os
import unittest
import openpaperwork_core


class TestMemoryDescriptorLeak(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_leak(self):
        self.tracking = False
        self.disposed = False

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def on_dispose(s):
                    self.disposed = True

                def on_objref_track(s, obj):
                    self.tracking = True
                    obj.weak_ref(s.on_dispose)

        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.python")
        self.core.load("paperwork_backend.poppler.memory")
        self.core._load_module("fake_module", FakeModule())

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

        self.assertTrue(self.tracking)
        self.assertFalse(self.disposed)

        page = doc.get_page(0)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        ctx = cairo.Context(surface)
        page.render(ctx)

        self.assertFalse(self.disposed)

        doc = None
        gc.collect()
        gc.collect()

        new_fds = self.core.call_success("fs_listdir", our_fds_dir)
        new_fds = list(new_fds)
        new_fds.sort()
        self.assertEqual(len(current_fds), len(new_fds))

        # XXX(Jflesch): And here we have a very nice memory leak
        # self.assertTrue(self.disposed)
