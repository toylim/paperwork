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
        self.core.get("paperwork_backend.index.whoosh").index_dir = (
            self.tmp_index_dir
        )

        self.fake_storage = self.core.get("paperwork_backend.model.fake")

    def tearDown(self):
        shutil.rmtree(self.tmp_index_dir)

    def test_transaction(self):
        self.core.init()

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
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
        self.core.init()

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, [])

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Whoosh and Flesch are\nthe best',
            }
        ]

        core = self.core

        class FakeModuleToStopMainLoop(object):
            class Plugin(openpaperwork_core.PluginBase):
                def on_index_updated(self):
                    core.call_all("mainloop_quit")

        self.core._load_module(
            "mainloop_stopper", FakeModuleToStopMainLoop()
        )

        self.core.call_all('sync')
        self.core.call_one('mainloop')

        results = []
        self.core.call_all("index_search", results, "flesch")
        self.assertEqual(results, ['test_doc'])
