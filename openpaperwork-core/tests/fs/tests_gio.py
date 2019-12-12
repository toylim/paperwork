import os
import tempfile
import time
import unittest

import openpaperwork_core


class TestSafe(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_linux(self):
        v = self.core.call_one('fs_safe', '/home/flesch jerome')
        self.assertEqual(v, "file:///home/flesch%20jerome")

        v = self.core.call_one('fs_safe', 'file:///home/flesch%20jerome')
        self.assertEqual(v, "file:///home/flesch%20jerome")

    @unittest.skipUnless(os.name == 'nt', reason="Windows only")
    def test_windows(self):
        v = self.core.call_one('fs_safe', 'c:\\Users\\flesch jerome')
        self.assertEqual(v, "file://c:\\Users\\flesch%20jerome")

        v = self.core.call_one('fs_safe', '\\\\someserver\\someshare')
        self.assertEqual(v, "\\\\someserver\\someshare")


class TestUnsafe(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    @unittest.skipUnless(os.name == 'posix', reason="Linux only")
    def test_linux(self):
        v = self.core.call_one('fs_unsafe', 'file:///home/flesch%20jerome')
        self.assertEqual(v, "/home/flesch jerome")

        v = self.core.call_one('fs_unsafe', 'file:///home/flesch jerome')
        self.assertEqual(v, "/home/flesch jerome")

        v = self.core.call_one('fs_unsafe', '/home/flesch jerome')
        self.assertEqual(v, "/home/flesch jerome")

    @unittest.skipUnless(os.name == 'nt', reason="Windows only")
    def test_windows(self):
        v = self.core.call_one('fs_safe', 'file://c:\\Users\\flesch%20jerome')
        self.assertEqual(v, "c:\\Users\\flesch jerome")

        v = self.core.call_one('fs_safe', '\\\\someserver\\someshare')
        self.assertEqual(v, "\\\\someserver\\someshare")


class TestOpen(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_read_binary(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as fd:
            file_name = fd.name
            fd.write(b"content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one(
                        'fs_open', safe_file_name, mode='rb'
                    ) as fd:
                content = fd.read()
                self.assertEqual(content, b"content")
        finally:
            os.unlink(file_name)

    def test_write_binary(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as fd:
            file_name = fd.name
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one(
                        'fs_open', safe_file_name, mode='wb'
                    ) as fd:
                fd.write(b"content\n")
            with open(file_name, 'rb') as fd:
                content = fd.read()
                self.assertEqual(content, b"content\n")
        finally:
            os.unlink(file_name)

    def test_read(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one('fs_open', safe_file_name, mode='r') as fd:
                content = fd.read()
                self.assertEqual(content, "content")
        finally:
            os.unlink(file_name)

    def test_write(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            with self.core.call_one('fs_open', safe_file_name, mode='w') as fd:
                fd.write("content\n")
            with open(file_name, 'r') as fd:
                content = fd.read()
                self.assertEqual(content, "content\n")
        finally:
            os.unlink(file_name)


class TestExists(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_not_exist(self):
        self.assertFalse(self.core.call_one('fs_exists', "/whatever"))

    def test_exists(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")
        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            self.assertTrue(self.core.call_one('fs_exists', safe_file_name))
        finally:
            os.unlink(file_name)


class TestListDir(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

        self.dirname = tempfile.mkdtemp()
        self.uri_dirname = self.core.call_one('fs_safe', self.dirname)
        with open(os.path.join(self.dirname, 'test1.txt'), 'w') as fd:
            fd.write('test1')
        with open(os.path.join(self.dirname, 'test2.txt'), 'w') as fd:
            fd.write('test2')
        os.mkdir(os.path.join(self.dirname, 'test3'))
        with open(os.path.join(self.dirname, 'test3', 'test4.txt'), 'w') as fd:
            fd.write('test4')

    def tearDown(self):
        # check fs_rm_rf at the same time
        self.core.call_one("fs_rm_rf", self.uri_dirname)
        self.assertFalse(os.path.exists(self.dirname))

    def test_listdir(self):
        files = list(self.core.call_one('fs_listdir', self.uri_dirname))
        files.sort()

        self.assertEqual(files, [
            self.uri_dirname + '/test1.txt',
            self.uri_dirname + '/test2.txt',
            self.uri_dirname + '/test3'
        ])

    def test_recurse(self):
        files = list(self.core.call_one('fs_recurse', self.uri_dirname))
        files.sort()

        self.assertEqual(files, [
            self.uri_dirname + '/test1.txt',
            self.uri_dirname + '/test2.txt',
            self.uri_dirname + '/test3/test4.txt'
        ])


class TestRename(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_rename(self):
        src_file_name = None
        dst_file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            src_file_name = fd.name
            fd.write("content")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            dst_file_name = fd.name
            fd.write("content")
        os.unlink(dst_file_name)

        try:
            safe_src_file_name = self.core.call_one('fs_safe', src_file_name)
            safe_dst_file_name = self.core.call_one('fs_safe', dst_file_name)
            self.assertTrue(os.path.exists(src_file_name))
            self.assertFalse(os.path.exists(dst_file_name))

            self.core.call_one(
                'fs_rename', safe_src_file_name, safe_dst_file_name
            )
            self.assertFalse(os.path.exists(src_file_name))
            self.assertTrue(os.path.exists(dst_file_name))
        finally:
            if os.path.exists(src_file_name):
                os.unlink(src_file_name)
            if os.path.exists(dst_file_name):
                os.unlink(dst_file_name)


class TestUnlink(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_unlink(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)
            self.assertTrue(os.path.exists(file_name))

            self.core.call_one('fs_unlink', safe_file_name)
            self.assertFalse(os.path.exists(file_name))
        finally:
            if os.path.exists(file_name):
                os.unlink(file_name)


class TestGetMtime(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_get_mtime(self):
        now = time.time()

        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)

            mtime = self.core.call_one('fs_get_mtime', safe_file_name)
            self.assertTrue(int(now) <= mtime)
            self.assertTrue(mtime <= now + 2)
        finally:
            os.unlink(file_name)


class TestGetsize(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_getsize(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")  # 7 bytes

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)

            s = self.core.call_one('fs_getsize', safe_file_name)
            self.assertEqual(s, 7)
        finally:
            os.unlink(file_name)


class TestIsdir(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_isdir_true(self):
        dirname = tempfile.mkdtemp()
        uri_dirname = self.core.call_one('fs_safe', dirname)

        try:
            self.assertTrue(self.core.call_one("fs_isdir", uri_dirname))
        finally:
            # check fs_rm_rf at the same time
            self.core.call_one("fs_rm_rf", uri_dirname)
            self.assertFalse(os.path.exists(dirname))

    def test_isdir_false(self):
        file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            file_name = fd.name
            fd.write("content")

        try:
            safe_file_name = self.core.call_one('fs_safe', file_name)

            self.assertFalse(self.core.call_one('fs_isdir', safe_file_name))
        finally:
            os.unlink(file_name)


class TestCopy(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_copy(self):
        src_file_name = None
        dst_file_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            src_file_name = fd.name
            fd.write("content")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fd:
            dst_file_name = fd.name
            fd.write("xxxxxxx")
        os.unlink(dst_file_name)

        try:
            safe_src_file_name = self.core.call_one('fs_safe', src_file_name)
            safe_dst_file_name = self.core.call_one('fs_safe', dst_file_name)
            self.assertTrue(os.path.exists(src_file_name))
            self.assertFalse(os.path.exists(dst_file_name))

            self.core.call_one(
                'fs_copy', safe_src_file_name, safe_dst_file_name
            )
            self.assertTrue(os.path.exists(src_file_name))
            self.assertTrue(os.path.exists(dst_file_name))

            with open(dst_file_name, 'r') as fd:
                content = fd.read()
                self.assertEqual(content, 'content')
        finally:
            if os.path.exists(src_file_name):
                os.unlink(src_file_name)
            if os.path.exists(dst_file_name):
                os.unlink(dst_file_name)


class TestMkdirP(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(allow_unsatisfied=True)
        self.core.load("openpaperwork_core.fs.gio")
        self.core.init()

    def test_mkdir_p(self):
        dirname = tempfile.mkdtemp()
        uri_dirname = self.core.call_one('fs_safe', dirname)
        try:
            new_dirs = uri_dirname + "/testA/testB/testC"
            self.core.call_one("fs_mkdir_p", new_dirs)
            self.assertTrue(os.path.exists(os.path.join(
                dirname, "testA", "testB", "testC"
            )))
        finally:
            # check fs_rm_rf at the same time
            self.core.call_one("fs_rm_rf", uri_dirname)
            self.assertFalse(os.path.exists(dirname))
