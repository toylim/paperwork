import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise

from .. import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_export_many"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -50

    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)
        self.active_page_idx = 0

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_action',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'doc_selection',
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._export)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Export"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def on_page_shown(self, active_page_idx):
        self.active_page_idx = active_page_idx

    def _export(self, action, parameter):
        docs = set()
        self.core.call_all("doc_selection_get", docs)
        self.core.call_all(
            "gtk_open_exporter_multiple_docs", docs,
            self.active_doc[0], self.active_doc[1], self.active_page_idx
        )
