import os
import shutil
import tempfile
import unittest

import openpaperwork_core


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.tmp_index_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_labels"
        )

        self.core = openpaperwork_core.Core()
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.guesswork.label_guesser")
        self.core.get("paperwork_backend.guesswork.label_guesser").bayes_dir = (
            self.tmp_index_dir
        )

        self.fake_storage = self.core.get("paperwork_backend.model.fake")

        self.core.init()

    def tearDown(self):
        shutil.rmtree(self.tmp_index_dir)

    def test_training(self):
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
            {
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
        ]

        # make a transaction to indicate that those documents are now in
        # the storage --> it will update the training of bayesian filters.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertEqual(len(transactions), 1)
        for transaction in transactions:
            transaction.add_obj("test_doc")
        for transaction in transactions:
            transaction.add_obj("test_doc_2")
        for transaction in transactions:
            transaction.add_obj("test_doc_3")
        for transaction in transactions:
            transaction.commit()

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\ncamion',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'pouet pouet pouet',
                'labels': set(),
            }
        ]

        # make a transaction to make the plugin label_guesser add labels
        # on them.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertEqual(len(transactions), 1)
        for transaction in transactions:
            transaction.add_obj("new_doc")
        for transaction in transactions:
            transaction.add_obj("new_doc_2")
        for transaction in transactions:
            transaction.commit()

        self.assertEqual(len(self.fake_storage.docs[4]['labels']), 0)

        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 1)
        self.assertEqual(
            list(self.fake_storage.docs[3]['labels'])[0],
            ("some_label", "#123412341234")
        )

    def test_sync(self):
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
            {
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
        ]

        core = self.core
        mainloop = False

        class FakeModuleToStopMainLoop(object):
            class Plugin(openpaperwork_core.PluginBase):
                def on_label_guesser_updated(self):
                    if mainloop:  # avoid double call at next transaction
                        core.call_all("mainloop_quit")

        self.core._load_module(
            "mainloop_stopper", FakeModuleToStopMainLoop()
        )

        self.core.call_all('sync')
        mainloop = True
        self.core.call_one('mainloop')
        mainloop = False

        self.fake_storage.docs = [
            {  # old doc
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\nthe best',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'mtime': 123,
                'text': 'Flesch Simplebayes\nbest',
                'labels': {("some_label", "#123412341234")},
            },
            {  # old doc
                'id': 'test_doc_3',
                'url': 'file:///somewhere/test_doc_3',
                'mtime': 123,
                'text': 'something else',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc',
                'url': 'file:///somewhere/new_doc',
                'mtime': 123,
                'text': 'Simplebayes and Flesch are\ncamion',
                'labels': set(),
            },
            {  # new doc on which we will guess the labels
                'id': 'new_doc_2',
                'url': 'file:///somewhere/new_doc_2',
                'mtime': 123,
                'text': 'pouet pouet pouet',
                'labels': set(),
            }
        ]

        # make a transaction to make the plugin label_guesser add labels
        # on them.
        transactions = []
        self.core.call_all("doc_transaction_start", transactions)
        self.assertEqual(len(transactions), 1)
        for transaction in transactions:
            transaction.add_obj("new_doc")
        for transaction in transactions:
            transaction.add_obj("new_doc_2")
        for transaction in transactions:
            transaction.commit()

        self.assertEqual(len(self.fake_storage.docs[4]['labels']), 0)

        self.assertEqual(len(self.fake_storage.docs[3]['labels']), 1)
        self.assertEqual(
            list(self.fake_storage.docs[3]['labels'])[0],
            ("some_label", "#123412341234")
        )
