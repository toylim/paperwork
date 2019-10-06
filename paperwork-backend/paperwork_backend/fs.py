import io
import logging
import os
import urllib

from gi.repository import Gio
from gi.repository import GLib

logger = logging.getLogger(__name__)


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
                logger.warning("Gio.Gerror", exc_info=exc)
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
        logger.warning("readlines() shouldn't be called on a binary file"
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


class CommonFs(object):
    def __init__(self):
        pass

    def join(self, base, url):
        if not base.endswith("/"):
            base += "/"
        return urllib.parse.urljoin(base, url)

    def basename(self, url):
        url = urllib.parse.urlparse(url)
        basename = os.path.basename(url.path)
        # Base name can be safely unquoted
        return urllib.parse.unquote(basename)

    def dirname(self, url):
        # dir name should not be unquoted. It could mess up the URI
        return os.path.dirname(url)


class GioFileSystem(CommonFs):
    def __init__(self):
        super().__init__()

    def safe(self, uri):
        logger.debug("safe: %s", uri)
        if uri[:2] == "\\\\" or "://" in uri:
            logger.debug("safe: --> %s", uri)
            return uri
        if os.name != "nt":
            uri = os.path.abspath(uri)
            uri = "file://" + urllib.parse.quote(uri)
            logger.debug("safe: --> %s", uri)
            return uri
        else:
            gf = Gio.File.new_for_path(uri)
            uri = gf.get_uri()
            logger.debug("safe: --> %s", uri)
            return uri

    def unsafe(self, uri):
        logger.debug("unsafe: %s", uri)
        if "://" not in uri and uri[:2] != "\\\\":
            logger.debug("unsafe: --> %s", uri)
            return uri
        if not uri.startswith("file://"):
            logger.debug("unsafe: --> EXC")
            raise Exception("TARGET URI SHOULD BE A LOCAL FILE")
        uri = uri[len("file://"):]
        if os.name == 'nt' and uri[0] == '/':
            # for some reason, some URI on Windows starts with
            # "file:///C:\..." instead of "file://C:\..."
            uri = uri[1:]
        uri = urllib.parse.unquote(uri)
        logger.debug("unsafe: --> %s", uri)
        return uri

    def open(self, uri, mode='rb'):
        f = Gio.File.new_for_uri(uri)
        if ('w' not in mode and 'a' not in mode) and not f.query_exists():
            raise IOError("File does not exist")
        try:
            raw = GioFileAdapter(f, mode)
            if 'b' in mode:
                return raw
            return GioUTF8FileAdapter(raw)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def exists(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            return f.query_exists()
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def listdir(self, url):
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
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def rename(self, old_url, new_url):
        try:
            old = Gio.File.new_for_uri(old_url)
            new = Gio.File.new_for_uri(new_url)
            assert(not old.equal(new))
            old.move(new, Gio.FileCopyFlags.NONE)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def unlink(self, url):
        try:
            logger.info("Deleting %s ...", url)
            f = Gio.File.new_for_uri(url)
            deleted = False
            try:
                deleted = f.trash()
            except Exception as exc:
                logger.warning("Failed to trash %s. Will try to delete it"
                               " instead", f.get_uri(), exc_info=exc)
            if not deleted:
                try:
                    deleted = f.delete()
                except Exception as exc:
                    logger.warning("Failed to deleted %s", f.get_uri(),
                                   exc_info=exc)
            if not deleted:
                raise IOError("Failed to delete %s" % url)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def rm_rf(self, url):
        try:
            logger.info("Deleting %s ...", url)
            f = Gio.File.new_for_uri(url)
            deleted = False
            try:
                deleted = f.trash()
            except Exception as exc:
                logger.warning("Failed to trash %s. Will try to delete it"
                               " instead", f.get_uri(), exc_info=exc)
            if not deleted:
                self._rm_rf(f)
            logger.info("%s deleted", url)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def _rm_rf(self, gfile):
        try:
            to_delete = [f for f in self._recurse(gfile, dir_included=True)]
            for f in to_delete:
                if not f.delete():
                    raise IOError("Failed to delete %s" % f.get_uri())
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def getmtime(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            if not f.query_exists():
                raise IOError("File {} does not exist".format(str(url)))
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_TIME_CHANGED, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_TIME_CHANGED)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def writable(self, url):
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
            raise IOError(str(exc))

    def getsize(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_SIZE, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_attribute_uint64(Gio.FILE_ATTRIBUTE_STANDARD_SIZE)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def isdir(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            fi = f.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_TYPE, Gio.FileQueryInfoFlags.NONE
            )
            return fi.get_file_type() == Gio.FileType.DIRECTORY
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def copy(self, old_url, new_url):
        try:
            old = Gio.File.new_for_uri(old_url)
            new = Gio.File.new_for_uri(new_url)
            if new.query_exists():
                new.delete()
            old.copy(new, Gio.FileCopyFlags.ALL_METADATA)
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

    def mkdir_p(self, url):
        try:
            f = Gio.File.new_for_uri(url)
            if not f.query_exists():
                f.make_directory_with_parents()
        except GLib.GError as exc:
            logger.warning("Gio.Gerror", exc_info=exc)
            raise IOError(str(exc))

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

    def recurse(self, parent_uri, dir_included=False):
        parent = Gio.File.new_for_uri(parent_uri)
        for f in self._recurse(parent, dir_included):
            yield f.get_uri()
