import unittest

from .. import Core


class AbstractTest(unittest.TestCase):
    def get_plugin_name(self):
        """
        Must be overloaded by subclasses
        """
        assert()

    def setUp(self):
        self.core = Core(allow_unsatisfied=True)
        self.core.load(self.get_plugin_name())
        self.core.init()

    def test_basic(self):
        boxes = [
            (((0, 0), (10, 10)), "a"),
            (((10, 10), (50, 40)), "b"),
            (((25, 25), (100, 100)), "c"),
        ]
        indexer = self.core.call_success("spatial_indexer_get", boxes)
        self.assertEqual(
            list(indexer.get_boxes(5, 5)),
            [
                (((0, 0), (10, 10)), "a"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(5, 10)),
            [
                (((0, 0), (10, 10)), "a"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(10, 10)),
            [
                (((0, 0), (10, 10)), "a"),
                (((10, 10), (50, 40)), "b"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(25, 20)),
            [
                (((10, 10), (50, 40)), "b"),
            ]
        )
        self.assertEqual(
            list(indexer.get_boxes(75, 75)),
            [
                (((25, 25), (100, 100)), "c"),
            ]
        )
