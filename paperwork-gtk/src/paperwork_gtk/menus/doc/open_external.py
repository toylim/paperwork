import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_open_external"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -50

    def get_interfaces(self):
        return [
            'menu',
            'menu_doc',
            'menu_doc_open_external',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def on_doclist_initialized(self):
        self.core.call_all(
            "add_doc_action", _("Open folder"), "win." + ACTION_NAME
        )
