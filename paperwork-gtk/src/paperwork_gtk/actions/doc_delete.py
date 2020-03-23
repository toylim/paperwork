import gettext
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


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext
ACTION_NAME = "doc_delete"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_action',
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
        ]

    def init(self, core):
        super().init(core)

        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._delete)
        self.core.call_all("app_actions_add", action)
        self.core.call_all("add_doc_action", _("Delete"), "win." + ACTION_NAME)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

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

        self.core.call_all("storage_delete_doc_id", doc_id)
        self.core.call_all("doc_close")
        self.core.call_all("search_update_document_list")

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._upd_index, args=(doc_id, doc_url,)
        )
        promise.schedule()

    def _upd_index(self, doc_id, doc_url):
        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)

        for transaction in transactions:
            transaction.del_obj(doc_id)

        for transaction in transactions:
            transaction.commit()
