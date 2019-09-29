import ctypes
import io
import logging
import os
import tempfile
import urllib

try:
    from gi.repository import Gio
    from gi.repository import GLib
    GLIB_AVAILABLE = True
except ImportError:
    GLIB_AVAILABLE = False

from . import CommonFsPluginBase


LOGGER = logging.getLogger(__name__)


class GioFileAdapter(io.RawIOBase):
    def __init__(self, gfile, mode='r'):
        super().__init__()
        self.gfile = gfile
        self.mode = mode

        if 'w' in mode and 'r' not in mode:
            self.size = 0
        elif ('w' in mode or 'a' in mode) and not gfile.query_exists():
            self.size = 0
        else:
            try:
                fi = gfile.query_info(
                    Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                    Gio.FileQueryInfoFlags.NONE
                )
                self.size = fi.get_attribute_uint64(
                    Gio.FILE_ATTRIBUTE_STANDARD_SIZE
                )
            except GLib.GError as exc:
                LOGGER.warning("Gio.Gerror", exc_info=exc)
                raise IOError(str(exc))

        self.gfd = None
        self.gin = None
        self.gout = None

        if 'r' in mode:
            self.gin = self.gfd = gfile.read()
        elif 'w' in mode or 'a' in mode:
            if gfile.query_exists():
                self.gfd = gfile.open_readwrite()
            else:
                self.gfd = gfile.create_readwrite(Gio.FileCreateFlags.NONE)
            if 'w' in mode:
                self.gfd.seek(0, GLib.SeekType.SET)
                self.gfd.truncate(0)
            self.gin = self.gfd.get_input_stream()
            self.gout = self.gfd.get_output_stream()

        if 'a' in mode:
            self.seek(0, whence=os.SEEK_END)

    def readable(self):
        return True

    def writable(self):
        return 'w' in self.mode or 'a' in self.mode

    def read(self, size=-1):
        if not self.readable():
            raise OSError("File is not readable")
        if size <= 0:
            size = self.size
            if size <= 0:
                return b""
        assert(size > 0)
        return self.gin.read_bytes(size).get_data()

    def readall(self):
        return self.read(-1)

    def readinto(self, b):
        raise OSError("readinto() not supported on Gio.File objects")

    def readline(self, size=-1):
        raise OSError("readline() not supported on Gio.File objects")

    def readlines(self, hint=-1):
        LOGGER.warning("readlines() shouldn't be called on a binary file"
                       " descriptor. This is not cross-platform")
        return [(x + b"\n") for x in self.readall().split(b"\n")]

    def seek(self, offset, whence=os.SEEK_SET):
        whence = {
            os.SEEK_CUR: GLib.SeekType.CUR,
            os.SEEK_END: GLib.SeekType.END,
            os.SEEK_SET: GLib.SeekType.SET,
        }[whence]
        self.gfd.seek(offset, whence)

    def seekable(self):
        return True

    def tell(self):
        return self.gin.tell()

    def flush(self):
        pass

    def truncate(self, size=None):
        if size is None:
            size = self.tell()
        self.gfd.truncate(size)

    def fileno(self):
        raise io.UnsupportedOperation("fileno() called on Gio.File object")

    def isatty(self):
        return False

    def write(self, b):
        res = self.gout.write_all(b)
        if not res[0]:
            raise OSError("write_all() failed on {}: {}".format(
                self.gfile.get_uri(), res)
            )
        return res[1]

    def writelines(self, lines):
        self.write(b"".join(lines))

    def close(self):
        self.flush()
        super().close()
        if self.gin:
            self.gin.close()
        if self.gout:
            self.gout.close()
        if self.gfd is not self.gin:
            self.gfd.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class GioUTF8FileAdapter(io.RawIOBase):
    def __init__(self, raw):
        super().__init__()
        self.raw = raw

    def readable(self):
        return self.raw.readable()

    def writable(self):
        return self.raw.writable()

    def read(self, *args, **kwargs):
        r = self.raw.read(*args, **kwargs)
        return r.decode("utf-8")

    def readall(self, *args, **kwargs):
        r = self.raw.readall(*args, **kwargs)
        return r.decode("utf-8")

    def readinto(self, *args, **kwargs):
        r = self.raw.readinto(*args, **kwargs)
        return r.decode("utf-8")

    def readlines(self, hint=-1):
        all = self.readall()
        if os.linesep != "\n":
            all = all.replace(os.linesep, "\n")
        lines = [(x + "\n") for x in all.split("\n")]
        if lines[-1] == "\n":
            return lines[:-1]
        return lines

    def readline(self, hint=-1):
        raise OSError("readline() not supported on Gio.File objects")

    def seek(self, *args, **kwargs):
        return self.raw.seek(*args, **kwargs)

    def seekable(self, seekable):
        return self.raw.seekable()

    @property
    def closed(self):
        return self.raw.closed

    def tell(self):
        # XXX(Jflesch): wrong ...
        return self.raw.tell()

    def flush(self):
        return self.raw.flush()

    def truncate(self, *args, **kwargs):
        # XXX(Jflesch): wrong ...
        return self.raw.truncate(*args, **kwargs)

    def fileno(self):
        return self.raw.fileno()

    def isatty(self):
        return self.raw.isatty()

    def write(self, b):
        b = b.encode("utf-8")
        return self.raw.write(b)

    def writelines(self, lines):
        lines = [
            (line + os.linesep).encode("utf-8")
            for line in lines
        ]
        return self.raw.writelines(lines)

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Plugin(CommonFsPluginBase):
    def __init__(self):
        super().__init__()

    def get_interfaces(self):
        return super().get_interfaces() + ['chkdeps']

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['gi.repository.GLib']['debian'] = 'gir1.2-glib-2.0'
            out['gi.repository.GLib']['ubuntu'] = 'gir1.2-glib-2.0'

    @staticmethod
    def _is_file_uri(uri):
        return uri.startswith("file://")

    def fs_open(self, uri, mode='r'):
        if not self._is_file_uri(uri):
            return None

        f = Gio.File.new_for_uri(uri)
        if ('w' not in mode and 'a' not in mode):
            if self.fs_exists(uri) is None:
                return None
        try:
            raw = GioFileAdapter(f, mode)
            if 'b' in mode:
                return raw
            return GioUTF8FileAdapter(raw)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_exists(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            if not f.query_exists():
                # this file does not exist for us, but it does not mean
                # another implementation of the plugin interface 'fs'
                # cannot handle it
                return None
            return True
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_listdir(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            children = f.enumerate_children(
                Gio.FILE_ATTRIBUTE_STANDARD_NAME, Gio.FileQueryInfoFlags.NONE,
                None
            )
            for child in children:
                child = f.get_child(child.get_name())
                yield child.get_uri()
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_rename(self, old_url, new_url):
        if not self._is_file_uri(old_url):
            return None
        if not self._is_file_uri(new_url):
            return None

        try:
            old = Gio.File.new_for_uri(old_url)
            new = Gio.File.new_for_uri(new_url)
            assert(not old.equal(new))
            old.move(new, Gio.FileCopyFlags.NONE)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_unlink(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            LOGGER.info("Deleting %s ...", url)
            f = Gio.File.new_for_uri(url)
            deleted = False
            try:
                deleted = f.trash()
            except Exception as exc:
                LOGGER.warning("Failed to trash %s. Will try to delete it"
                               " instead", f.get_uri(), exc_info=exc)
            if not deleted:
                try:
                    deleted = f.delete()
                except Exception as exc:
                    LOGGER.warning("Failed to deleted %s", f.get_uri(),
                                   exc_info=exc)
            if not deleted:
                raise IOError("Failed to delete %s" % url)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_rm_rf(self, url):
        if not self._is_file_uri(url):
            return None

        if self.fs_exists(url) is None:
            return None

        try:
            LOGGER.info("Deleting %s ...", url)
            f = Gio.File.new_for_uri(url)
            deleted = False
            try:
                deleted = f.trash()
            except Exception as exc:
                LOGGER.warning("Failed to trash %s. Will try to delete it"
                               " instead", f.get_uri(), exc_info=exc)
            if not deleted:
                self._rm_rf(f)
            LOGGER.info("%s deleted", url)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def _rm_rf(self, gfile):
        try:
            to_delete = [f for f in self._recurse(gfile, dir_included=True)]
            for f in to_delete:
                if not f.delete():
                    raise IOError("Failed to delete %s" % f.get_uri())
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_get_mtime(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            if not f.query_exists():
                raise IOError("File {} does not exist".format(str(url)))
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_TIME_CHANGED, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_TIME_CHANGED)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)

    def fs_iswritable(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE,
                Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_boolean(
                Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE
            )
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)

    def fs_getsize(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_SIZE, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_STANDARD_SIZE)
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_isdir(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_TYPE, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_file_type() == Gio.FileType.DIRECTORY
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def fs_copy(self, old_url, new_url):
        if not self._is_file_uri(old_url) or not self._is_file_uri(new_url):
            return None
        try:
            old = Gio.File.new_for_uri(old_url)
            new = Gio.File.new_for_uri(new_url)
            if new.query_exists():
                new.delete()
            old.copy(new, Gio.FileCopyFlags.ALL_METADATA)
            return new_url
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            return None

    def fs_mkdir_p(self, url):
        if not self._is_file_uri(url):
            return None

        try:
            f = Gio.File.new_for_uri(url)
            if not f.query_exists():
                f.make_directory_with_parents()
        except GLib.GError as exc:
            LOGGER.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

        return True

    def _recurse(self, parent, dir_included=False):
        """
        Yield all the children (depth first), but not the parent.
        """
        try:
            children = parent.enumerate_children(
                Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                None
            )
        except GLib.GError:
            # assumes it's a file and not a directory
            yield parent
            return

        for child in children:
            name = child.get_name()
            child = parent.get_child(name)
            try:
                for sub in self._recurse(child):
                    yield sub
            except GLib.GError:
                yield child

        if dir_included:
            yield parent

    def fs_recurse(self, parent_uri, dir_included=False):
        if not self._is_file_uri(parent_uri):
            return None

        parent = Gio.File.new_for_uri(parent_uri)
        for f in self._recurse(parent, dir_included):
            yield f.get_uri()

    def fs_hide(self, uri):
        if not self._is_file_uri(uri):
            return None

        if os.name != 'nt':
            LOGGER.warning("fs_hide('%s') can only works on Windows", uri)
            return
        filepath = self.fs_unsafe(uri)
        LOGGER.info("Hiding file: {}".format(filepath))
        ret = ctypes.windll.kernel32.SetFileAttributesW(
            filepath, 0x02  # hidden
        )
        if not ret:
            raise ctypes.WinError()

    def fs_get_mime(self, uri):
        if not self._is_file_uri(uri):
            return None

        gfile = Gio.File.new_for_uri(file_uri)
        info = gfile.query_info(
            "standard::content-type", Gio.FileQueryInfoFlags.NONE
        )
        return info.get_content_type()

    def fs_mktemp(self, prefix=None, suffix=None):
        tmp = tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, delete=False
        )
        return (self.fs_safe(tmp.name), tmp)
