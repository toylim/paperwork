import gc
import logging
import os

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

from .. import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete_many"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.active_windows = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_action',
            'doc_open',
            'gtk_window_listener',
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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Delete"), "win." + ACTION_NAME)
        self.core.call_all("docs_menu_append_item", item)

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def _delete(self, action, parameter):
        docs = set()
        self.core.call_all("doc_selection_get", docs)
        LOGGER.info("Asking confirmation before deleting %d doc", len(docs))
        msg = _('Are you sure you want to delete %d documents ?') % len(docs)

        confirm = Gtk.MessageDialog(
            parent=self.active_windows[-1],
            flags=Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=msg
        )

        confirm.connect("response", self._really_delete, docs)
        confirm.show_all()

        if os.name == "nt":
            # On Windows, we have to be absolutely sure the PDF is actually
            # closed when we try to delete it because Windows s*cks pony d*cks
            # in h*ll.
            self.core.call_all("doc_close")
            # there is no "close()" method in Poppler
            gc.collect()

    def _really_delete(self, dialog, response, docs):
        if response != Gtk.ResponseType.YES:
            LOGGER.info("User cancelled")
            dialog.destroy()
            return
        dialog.destroy()

        self.core.call_all("doc_close")

        for (doc_id, doc_url) in docs:
            LOGGER.info("Deleting document %s", doc_id)
            self.core.call_all("storage_delete_doc_id", doc_id)

        self.core.call_all("search_update_document_list")

        self.core.call_success(
            "transaction_simple", [
                ('del', doc_id) for (doc_id, doc_url) in docs
            ]
        )
