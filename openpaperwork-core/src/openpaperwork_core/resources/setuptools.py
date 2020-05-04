import logging
import os
try:
    import pkg_resources
    PKG_RESOURCES_AVAILABLE = True
except Exception:
    PKG_RESOURCES_AVAILABLE = False

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['resources']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def resources_get_file(self, pkg, filename):
        if not PKG_RESOURCES_AVAILABLE:
            return

        path = pkg_resources.resource_filename(pkg, filename)

        if not os.access(path, os.R_OK):
            LOGGER.warning("Failed to find resource file %s/%s", pkg, filename)
            return None

        LOGGER.debug("%s:%s --> %s", pkg, filename, path)
        return self.core.call_success("fs_safe", path)

    def resources_get_dir(self, pkg, dirname):
        return self.resources_get_file(pkg, dirname)
