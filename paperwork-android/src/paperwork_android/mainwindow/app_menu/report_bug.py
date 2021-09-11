import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def get_interfaces(self):
        return [
            'app_menu_item',
        ]

    def get_deps(self):
        return []

    def app_menu_get_items(self, out: list):
        out.append(("Report bug", self._open_bug_report))

    def _open_bug_report(self):
        LOGGER.info("Opening bug report screen")
        # TODO
