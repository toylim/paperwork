import gc
import logging
import os

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_delete"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.active_doc = (None, None)
        self.action = None

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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_dialog_yes_no',
                'defaults': ['openpaperwork_gtk.dialogs.yes_no'],
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

    def on_doclist_initialized(self):
        self.core.call_all("app_actions_add", self.action)
        self.core.call_all(
            "add_doc_action", _("Delete document"), "win." + ACTION_NAME
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = (None, None)

    def _delete(self, action, parameter):
        assert(self.active_doc is not None)
        active = self.active_doc

        LOGGER.info("Asking confirmation before deleting doc %s", active[0])
        msg = _('Are you sure you want to delete document %s ?') % active[0]

        if os.name == "nt":
            # On Windows, we have to be absolutely sure the PDF is actually
            # closed when we try to delete it because Windows s*cks pony d*cks
            # in h*ll.
            self.core.call_all("doc_close")
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_all(
            "gtk_show_dialog_yes_no", self, msg, self.active_doc
        )

    def on_dialog_yes_no_reply(self, parent, reply, *args, **kwargs):
        if parent is not self:
            return
        if not reply:
            return

        (active_doc,) = args
        (doc_id, doc_url) = active_doc

        LOGGER.info("Will delete doc %s", doc_id)

        self.core.call_all("doc_close")
        if os.name == "nt":
            # there is no "close()" method in Poppler
            gc.collect()

        self.core.call_success(
            "mainloop_schedule", self._really_delete, doc_id
        )

    def _really_delete(self, doc_id):
        self.core.call_all("storage_delete_doc_id", doc_id)
        self.core.call_all("search_update_document_list")

        self.core.call_success("transaction_simple", (('del', doc_id),))
