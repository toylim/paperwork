import logging
import os
import pkg_resources

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
        path = pkg_resources.resource_filename(pkg, filename)

        if not os.access(path, os.R_OK):
            raise FileNotFoundError(
                "Can't find resource file '{}'. Aborting".format(filename)
            )

        LOGGER.debug("%s:%s --> %s", pkg, filename, path)
        return self.core.call_success("fs_safe", path)