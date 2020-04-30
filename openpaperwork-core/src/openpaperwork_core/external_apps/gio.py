import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except ImportError:
    GLIB_AVAILABLE = False

from .. import deps
from .. import PluginBase

LOGGER = logging.getLogger(__name__)


class Plugin(PluginBase):
    PRIORITY = 75

    def get_interfaces(self):
        return [
            'chkdeps',
            'external_apps',
        ]

    def get_deps(self):
        return []

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'] = deps.GLIB

    def external_app_open_file(self, file_url):
        LOGGER.info("Opening file '%s' using Gio", file_url)
        if not Gio.AppInfo.launch_default_for_uri(file_url):
            LOGGER.warning("Failed to opening file '%s' using Gio", file_url)
            return None
        return True

    def external_app_open_folder(self, folder_url):
        return self.external_app_open_file(folder_url)
