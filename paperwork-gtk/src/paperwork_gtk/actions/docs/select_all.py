import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_select_all"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def __init__(self):
        super().__init__()
        self.visible_docs = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'docs_action',
            'search_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_selection',
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': 'docs_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def init(self, core):
        super().init(core)

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._select_all)
        self.core.call_all("app_actions_add", action)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Select all"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_search_results(self, query, docs):
        self.visible_docs = docs

    def _select_all(self, action, parameter):
        for doc in self.visible_docs:
            self.core.call_all("doc_selection_add", *doc)
