import logging

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_properties"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.active_doc = None

    def get_interfaces(self):
        return [
            'menu',
            'menu_doc',
            'menu_doc_properties',
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

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "add_doc_main_action",
            "document-properties-symbolic",
            _("Document properties"),
            self._open_properties
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def _open_properties(self, *args, **kwargs):
        assert self.active_doc is not None
        active = self.active_doc

        LOGGER.info("Opening properties of document %s", active[0])
        self.core.call_all("open_doc_properties", *active)
