import os
import shutil
import tempfile
import unittest

import openpaperwork_core


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.tmp_index_dir = tempfile.mkdtemp(prefix="paperwork_backend_index")

        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.index.whoosh")
        self.core.get_by_name("paperwork_backend.index.whoosh").index_dir = (
            self.tmp_index_dir
        )

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

        self.core.init()

    def tearDown(self):
        shutil.rmtree(self.tmp_index_dir)

    def test_transaction(self):
        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
                'labels': set(),
            }
        ]

        transactions = []
        self.core.call_all('doc_transaction_start', transactions)
        for transaction in transactions:
            transaction.add_obj('test_doc')
        for transaction in transactions:
            transaction.commit()

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, ['test_doc'])

    def test_sync(self):
        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
                'labels': set(),
            }
        ]

        core = self.core

        class FakeModuleToStopMainLoop(object):
            class Plugin(openpaperwork_core.PluginBase):
                def on_index_commit_end(self):
                    core.call_all("mainloop_quit_graceful")

        self.core._load_module(
            "mainloop_stopper", FakeModuleToStopMainLoop()
        )

        promises = []
        self.core.call_all('sync', promises)
        promise = promises[0]
        for p in promises[1:]:
            promise = promise.then(p)
        promise.schedule()

        self.core.call_one('mainloop')

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, ['test_doc'])
