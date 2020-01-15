import shutil
import tempfile
import unittest

import openpaperwork_core


class TestPageTracker(unittest.TestCase):
    def setUp(self):
        self.tmp_paperwork_dir = tempfile.mkdtemp(
            prefix="paperwork_backend_tests"
        )

        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("paperwork_backend.model.fake")
        self.core.load("paperwork_backend.pagetracker")
        self.core.get_by_name(
            "paperwork_backend.pagetracker"
        ).paperwork_dir = self.tmp_paperwork_dir

        self.fake_storage = self.core.get_by_name(
            "paperwork_backend.model.fake"
        )

        self.core.init()

    def tearDown(self):
        shutil.rmtree(self.tmp_paperwork_dir)

    def test_tracking(self):
        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'page_hashes': [
                    ('file:///somewhere/test_doc/0.jpeg', 123),
                    ('file:///somewhere/test_doc/1.jpeg', 124),
                ],
            },
            {
                'id': 'test_doc_2',
                'url': 'file:///somewhere/test_doc_2',
                'page_hashes': [
                    ('file:///somewhere/test_doc_2/0.jpeg', 125),
                    ('file:///somewhere/test_doc_2/1.jpeg', 126),
                    ('file:///somewhere/test_doc_2/2.jpeg', 127),
                ],
            },
        ]

        tracker = self.core.call_success("page_tracker_get", 'test_tracking')
        out = tracker.find_changes('test_doc', 'file:///somewhere/test_doc')
        self.assertEqual(out, [('new', 0), ('new', 1)])
        tracker.ack_page('test_doc', 'file:///somewhere/test_doc', 0)
        tracker.ack_page('test_doc', 'file:///somewhere/test_doc', 1)
        out = tracker.find_changes('test_doc_2', 'file:///somewhere/test_doc_2')
        self.assertEqual(out, [('new', 0), ('new', 1), ('new', 2)])
        tracker.ack_page('test_doc_2', 'file:///somewhere/test_doc_2', 0)
        tracker.ack_page('test_doc_2', 'file:///somewhere/test_doc_2', 1)
        tracker.ack_page('test_doc_2', 'file:///somewhere/test_doc_2', 2)
        tracker.commit()

        self.fake_storage.docs = [
            {
                'id': 'test_doc',
                'url': 'file:///somewhere/test_doc',
                'page_hashes': [
                    ('file:///somewhere/test_doc/0.jpeg', 256),
                    ('file:///somewhere/test_doc/1.jpeg', 124),
                    ('file:///somewhere/test_doc/2.jpeg', 257),
                ],
            },
        ]

        tracker = self.core.call_success("page_tracker_get", 'test_tracking')
        out = tracker.find_changes('test_doc', 'file:///somewhere/test_doc')
        self.assertEqual(out, [('upd', 0), ('new', 2)])
        tracker.ack_page('test_doc', 'file:///somewhere/test_doc', 0)
        tracker.ack_page('test_doc', 'file:///somewhere/test_doc', 2)
        tracker.delete_doc('test_doc_2')
        tracker.commit()
