import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return [
            'app_menu_item',
        ]

    def get_deps(self):
        return []

    def app_menu_get_items(self, out: list):
        out.append(("Settings", self._open_settings))

    def _open_settings(self):
        LOGGER.info("Opening settings")
        # TODO
