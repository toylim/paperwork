import unittest

import openpaperwork_core


class TestScan2Doc(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.fs.fake")
        self.core.load("paperwork_backend.docscan.fake")
        self.core.load("paperwork_backend.docscan.scan2doc")

        self.fs = self.core.get_by_name("paperwork_backend.fs.fake")
        self.results = []
        self.transaction_type = None
        self.nb_commits = 0

        class FakeTransaction(object):
            def add_obj(s, doc_id):
                self.assertIsNone(self.transaction_type)
                self.transaction_type = "add"

            def upd_obj(s, doc_id):
                self.assertIsNone(self.transaction_type)
                self.transaction_type = "upd"

            def del_obj(s, doc_id):
                pass

            def unchanged_obj(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                def on_scan_feed_start(s, scan_id):
                    doc_id = self.core.call_success(
                        "scan2doc_scan_id_to_doc_id", scan_id
                    )
                    self.assertIsNotNone(doc_id)

                def doc_transaction_start(self, transactions, nb_expected=-1):
                    transactions.append(FakeTransaction())

                def fs_exists(self, file_url):
                    if "paper.10" in file_url:
                        return None
                    if "existing" in file_url:
                        return True
                    return None

        self.core._load_module("fake_module", FakeModule())
        self.core.init()

    def test_scan2doc_new(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success("scan2doc_promise")
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "add")

    def test_scan2doc_upd(self):
        def at_the_end(args):
            (doc_id, doc_url) = args
            self.results.append(doc_id)

        promise = self.core.call_success("scan2doc_promise", doc_id="existing")
        promise.then(at_the_end)
        promise.schedule()

        self.core.call_all("mainloop_quit_graceful")
        self.core.call_one("mainloop")

        self.assertTrue(len(self.results) > 0)
        self.assertEqual(self.transaction_type, "upd")
