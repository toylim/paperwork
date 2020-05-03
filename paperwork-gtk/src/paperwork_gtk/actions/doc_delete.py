import logging

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
ACTION_NAME = "doc_delete"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)
        self.active_windows = []
        self.action = None

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
        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._delete)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_doclist_initialized(self):
        self.core.call_all("app_actions_add", self.action)
        self.core.call_all(
            "add_doc_action", _("Delete document"), "win." + ACTION_NAME
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = (None, None)

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def _delete(self, action, parameter):
        assert(self.active_doc is not None)
        active = self.active_doc

        LOGGER.info("Asking confirmation before deleting doc %s", active[0])
        msg = _('Are you sure you want to delete document %s ?') % active[0]

        confirm = Gtk.MessageDialog(
            parent=self.active_windows[-1],
            flags=Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=msg
        )

        confirm.connect("response", self._really_delete)
        confirm.show_all()

    def _really_delete(self, dialog, response):
        if response != Gtk.ResponseType.YES:
            LOGGER.info("User cancelled")
            dialog.destroy()
            return
        dialog.destroy()
        assert(self.active_doc is not None)
        (doc_id, doc_url) = self.active_doc

        LOGGER.info("Will delete doc %s", doc_id)

        self.core.call_all("doc_close")
        self.core.call_all("storage_delete_doc_id", doc_id)
        self.core.call_all("search_update_document_list")

        self.core.call_success("transaction_simple", (('del', doc_id),))
