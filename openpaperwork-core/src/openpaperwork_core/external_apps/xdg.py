import logging
import os
import shutil

from .. import PluginBase


LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    def get_interfaces(self):
        return ['external_apps']

    def get_deps(self):
        return []

    def external_app_open_file(self, file_url):
        if shutil.which("xdg-open") is None:
            return None
        LOGGER.info("Opening %s with xdg-open", file_url)
        os.spawnlp(os.P_NOWAIT, 'xdg-open', 'xdg-open', file_url)
        return True

    def external_app_open_folder(self, folder_url):
        return self.external_app_open_file(folder_url)
