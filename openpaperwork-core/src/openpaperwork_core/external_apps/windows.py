import logging
import os

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return ['external_apps']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_core.fs.python'],
            },
        ]

    def external_app_open_file(self, file_url):
        if not hasattr(os, 'startfile'):
            return None
        # os.startfile() is Windows-only.
        LOGGER.info("Opening %s with os.startfile()", file_url)
        assert file_url.startswith("file://")
        file_path = self.core.call_success("fs_safe", file_url)
        os.startfile(file_path)
        return True

    def external_app_open_folder(self, folder_url):
        return self.external_app_open_file(folder_url)

    def external_app_can_send_as_attachment(self) -> None:
        return None

    def external_app_send_as_attachment(self, uri) -> None:
        return None
