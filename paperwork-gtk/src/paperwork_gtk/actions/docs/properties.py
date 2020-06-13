import itertools
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_change_labels"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.menu_add = None
        self.menu_remove = None
        self.idx_generator = itertools.count()

    def get_interfaces(self):
        return [
            'chkdeps',
            'docs_action',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'docs_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'doc_selection',
                'defaults': ['paperwork_gtk.doc_selection'],
            },
            {
                'interface': 'gtk_doc_properties',
                'defaults': ['paperwork_gtk.mainwindow.docproperties'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def init(self, core):
        super().init(core)

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._open_editor)
        self.core.call_all("app_actions_add", action)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Change labels"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def _open_editor(self, action, parameter):
        selection = set()
        self.core.call_all("doc_selection_get", selection)

        if len(selection) <= 0:
            LOGGER.info("No document selected")
            return

        LOGGER.info("Opening properties for %d documents", len(selection))
        self.core.call_all("open_docs_properties", selection)
