import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def get_interfaces(self):
        return [
            'menu',
            'menu_doc',
            'menu_doc_delete',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'action_doc_delete',
                'defaults': ['paperwork_gtk.actions.doc.delete'],
            },
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
            "add_doc_action", _("Delete document"), "win." + ACTION_NAME
        )
