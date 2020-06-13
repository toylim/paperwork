import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_print"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []

    def get_interfaces(self):
        return [
            'menu',
            'menu_doc',
            'menu_doc_print',
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
            "add_doc_action", _("Print document"), "win." + ACTION_NAME
        )
