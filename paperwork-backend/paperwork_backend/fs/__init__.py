import os
import urllib

import openpaperwork_core


class CommonFsPluginBase(openpaperwork_core.PluginBase):
    def __init__(self):
        """
        Should be used only by sub-classes
        """
        super().__init__()

    def get_interfaces(self):
        return ['fs']

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
