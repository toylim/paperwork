import logging
import os

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
BASE_PACKAGE = "paperwork_android"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.base_path = os.getcwd()

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
        if pkg != BASE_PACKAGE and not pkg.startswith(BASE_PACKAGE + "."):
            return None
        path = pkg.replace(".", os.path.sep)
        path = os.path.join(os.getcwd(), path, filename)
        if not os.path.exists(path):
            LOGGER.warning("Resource %s doesn't exist", path)
            return None
        return self.core.call_success("fs_safe", path)

    def resources_get_dir(self, pkg, dirname):
        return self.resources_get_file(pkg, dirname)
