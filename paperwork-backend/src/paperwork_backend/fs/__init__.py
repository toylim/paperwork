import hashlib
import logging
import os
import urllib

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class CommonFsPluginBase(openpaperwork_core.PluginBase):
    def __init__(self):
        """
        Should be used only by sub-classes
        """
        super().__init__()

    def get_interfaces(self):
        return ['fs']

    def fs_safe(self, uri):
        """
        Make sure the specified URI is actually an URI and not a Unix path.
        Returns:
            - An URI
        """
        LOGGER.debug("safe: %s", uri)
        if uri[:2] == "\\\\" or "://" in uri:
            LOGGER.debug("safe: --> %s", uri)
            return uri
        if os.name != "nt":
            uri = os.path.abspath(uri)
            uri = "file://" + urllib.parse.quote(uri)
            LOGGER.debug("safe: --> %s", uri)
            return uri
        else:
            gf = Gio.File.new_for_path(uri)
            uri = gf.get_uri()
            LOGGER.debug("safe: --> %s", uri)
            return uri

    def fs_unsafe(self, uri):
        """
        Turn an URI into an Unix path, whenever possible.
        Shouldn't be used at all.
        """
        LOGGER.debug("unsafe: %s", uri)
        if "://" not in uri and uri[:2] != "\\\\":
            LOGGER.debug("unsafe: --> %s", uri)
            return uri
        if not uri.startswith("file://"):
            LOGGER.debug("unsafe: --> EXC")
            raise Exception("TARGET URI SHOULD BE A LOCAL FILE")
        uri = uri[len("file://"):]
        if os.name == 'nt' and uri[0] == '/':
            # for some reason, some URI on Windows starts with
            # "file:///C:\..." instead of "file://C:\..."
            uri = uri[1:]
        uri = urllib.parse.unquote(uri)
        LOGGER.debug("unsafe: --> %s", uri)
        return uri

    def fs_join(self, base, url):
        if not base.endswith("/"):
            base += "/"
        return urllib.parse.urljoin(base, url)

    def fs_basename(self, url):
        url = urllib.parse.urlparse(url)
        basename = os.path.basename(url.path)
        # Base name can be safely unquoted
        return urllib.parse.unquote(basename)

    def fs_dirname(self, url):
        # dir name should not be unquoted. It could mess up the URI
        return os.path.dirname(url)

    def fs_hash(self, url):
        with self.core.call_success("fs_open", url, 'rb') as fd:
            content = fd.read()
        return int(hashlib.sha256(content).hexdigest(), 16)
