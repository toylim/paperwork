import unittest

import paperwork_backend.util


class TestUtil(unittest.TestCase):
    def test_levenshtein_distance(self):
        levensthein = paperwork_backend.util.levenshtein_distance

        self.assertEqual(levensthein("abc", "abc"), 0)
        self.assertEqual(levensthein("abc", "abce"), 1)  # insert
        self.assertEqual(levensthein("abc", "ab"), 1)  # delete
        self.assertEqual(levensthein("abc", "abd"), 1)  # replace
        self.assertEqual(levensthein("abc", "defg"), 4)  # combo
