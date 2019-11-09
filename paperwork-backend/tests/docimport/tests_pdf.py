import os
import unittest

import openpaperwork_core
import paperwork_backend.docimport


class TestPdfImport(unittest.TestCase):
    def setUp(self):
        self.test_doc_url = (
            "file://{}/test_doc.pdf".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)

        self.copies = []
        self.add_docs = []
        self.nb_commits = 0

        class FakeTransaction(object):
            priority = 0

            def add_obj(s, doc_id):
                self.add_docs.append(doc_id)

            def unchanged_obj(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".pdf")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "application/pdf"

                def fs_mkdir_p(s, dir_uri):
                    return True

                def fs_copy(s, src_uri, dst_uri):
                    self.copies.append((src_uri, dst_uri))
                    return dst_uri

                def on_import_done(s, file_import):
                    self.core.call_all("mainloop_quit_graceful")

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

        self.core._load_module("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.pdf")

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

        self.core.init()

    def test_import_pdf(self):
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_doc_url,]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        # see fake storage behaviour
        self.assertEqual(self.copies, [
            (self.test_doc_url, 'file:///some_work_dir/1/doc.pdf')
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, set())
        self.assertEqual(file_import.imported_files, {self.test_doc_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['PDF'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)


class TestRecursivePdfImport(unittest.TestCase):
    def setUp(self):
        self.test_doc_url = (
            "file://{}/test_doc.pdf".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        self.test_dir_url = (
            "file://{}".format(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)

        self.copies = []
        self.add_docs = []
        self.nb_commits = 0

        class FakeTransaction(object):
            priority = 0

            def add_obj(s, doc_id):
                self.add_docs.append(doc_id)

            def unchanged_obj(s, doc_id):
                pass

            def commit(s):
                self.nb_commits += 1

        class FakeModule(object):
            class Plugin(openpaperwork_core.PluginBase):
                PRIORITY = 999999999999999999

                def fs_isdir(s, dir_uri):
                    return not dir_uri.lower().endswith(".pdf")

                def fs_get_mime(s, file_uri):
                    if s.fs_isdir(file_uri):
                        return "inode/directory"
                    return "application/pdf"

                def fs_mkdir_p(self, dir_uri):
                    return True

                def fs_copy(s, src_uri, dst_uri):
                    self.copies.append((src_uri, dst_uri))
                    return dst_uri

                def on_import_done(s, file_import):
                    self.core.call_all("mainloop_quit_graceful")

                def doc_transaction_start(s, transactions, expected=-1):
                    transactions.append(FakeTransaction())

        self.core._load_module("fake_module", FakeModule())
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.docimport.pdf")

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

        self.core.init()

    def test_import_pdf(self):
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
        ]

        file_import = paperwork_backend.docimport.FileImport(
            file_uris_to_import=[self.test_dir_url,]
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        self.assertEqual(len(importers), 1)

        promise = importers[0].get_import_promise()
        promise.schedule()

        self.core.call_all("mainloop")

        # see fake storage behaviour
        self.assertEqual(self.copies, [
            (self.test_doc_url, 'file:///some_work_dir/1/doc.pdf')
        ])
        self.assertEqual(self.add_docs, ['1'])
        self.assertEqual(self.nb_commits, 1)

        self.assertEqual(file_import.ignored_files, set())
        self.assertEqual(file_import.imported_files, {self.test_doc_url})
        self.assertEqual(file_import.new_doc_ids, {'1'})
        self.assertEqual(file_import.upd_doc_ids, set())
        self.assertEqual(file_import.stats['PDF'], 1)
        self.assertEqual(file_import.stats['Documents'], 1)
