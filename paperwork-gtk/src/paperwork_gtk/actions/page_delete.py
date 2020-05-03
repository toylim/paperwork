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
ACTION_NAME = "page_delete"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_page_idx = -1
        self.active_windows = []
        self.action = None
        self.item = None

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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'page_actions',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageinfo.actions'
                ],
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

        self.item = Gio.MenuItem.new(_("Delete page"), "win." + ACTION_NAME)

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._delete)

        self.core.call_all("app_actions_add", self.action)

    def on_page_menu_ready(self):
        self.core.call_all("page_menu_append_item", self.item)

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

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _delete(self, *args, **kwargs):
        assert(self.active_doc is not None)

        LOGGER.info(
            "Asking confirmation before deleting page %d of document %s",
            self.active_page_idx, self.active_doc[0]
        )
        msg = (
            _(
                "Are you sure you want to delete page"
                " {page_idx} of document {doc_id} ?"
            ).format(
                page_idx=(self.active_page_idx + 1),
                doc_id=self.active_doc[0]
            )
        )

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
        page_idx = self.active_page_idx

        LOGGER.info("Will delete page %s p%d", doc_id, page_idx)

        self.core.call_all("page_delete_by_url", doc_url, page_idx)
        self.core.call_all("search_update_document_list")
        self.core.call_all("doc_reload", doc_id, doc_url)

        self.core.call_success("transaction_simple", (('upd', doc_id),))
