"""
Provides support for URIs "file://".
"""

import codecs
import logging
import os
import os.path
import shutil
import tempfile

from . import CommonFsPluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(CommonFsPluginBase):
    def _uri_to_path(self, uri):
        if not uri.lower().startswith("file://"):
            return None
        path = uri[len("file://"):]
        if "#" in path:
            path = path[:path.index("#")]
        return path

    def fs_open(self, uri, mode='r'):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        if 'b' in mode:
            return open(path, mode)
        return codecs.open(path, mode, encoding='utf-8')

    def fs_exists(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        return os.path.exists(path)

    def fs_listdir(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        for f in os.listdir(path):
            yield self.fs_safe(os.path.join(path, f))

    def fs_rename(self, old_uri, new_uri):
        old_path = self._uri_to_path(old_uri)
        new_path = self._uri_to_path(new_uri)
        if old_path is None or new_path is None:
            return None

        os.rename(old_path, new_path)
        return True

    def fs_unlink(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        os.unlink(path)
        return True

    def fs_rm_rf(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        shutil.rmtree(path, ignore_errors=True)
        return True

    def fs_get_mtime(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        return os.stat(path).st_mtime

    def fs_getsize(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        return os.stat(path).st_size

    def fs_isdir(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        return os.path.isdir(path)

    def fs_copy(self, old_uri, new_uri):
        old_path = self._uri_to_path(old_uri)
        new_path = self._uri_to_path(new_uri)
        if old_path is None or new_path is None:
            return None

        shutil.copy(old_path, new_path)
        return True

    def fs_mkdir_p(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return

        os.makedirs(path, mode=0o700, exist_ok=True)
        return True

    def fs_recurse(self, parent_uri, dir_included=False):
        path = self._uri_to_path(parent_uri)
        if path is None:
            return

        for (root, dirs, files) in os.walk(path):
            if dir_included:
                for d in dirs:
                    p = os.path.join(path, root, d)
                    yield self.fs_safe(p)
            for f in files:
                p = os.path.join(path, root, f)
                yield self.fs_safe(p)

    def fs_hide(self, uri):
        pass

    def fs_get_mime(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        # should use 'magic', but Core can't have any dependency on it.
        # other we would pull it on all platforms.
        path = path.lower()
        if path.endswith(".pdf"):
            return "application/pdf"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".tiff"):
            return "image/tiff"
        if path.endswith(".bmp"):
            return "image/x-ms-bmp"
        if path.endswith(".jpeg") or path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".txt"):
            return "text/plain"

        return None

    def fs_iswritable(self, uri):
        path = self._uri_to_path(uri)
        if path is None:
            return None

        return os.access(path, os.W_OK)

    def fs_mktemp(
                self, prefix=None, suffix=None, mode='w+b', on_disk=False,
                **kwargs
            ):
        tmp = tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, delete=False, mode=mode
        )
        return (self.fs_safe(tmp.name), tmp)