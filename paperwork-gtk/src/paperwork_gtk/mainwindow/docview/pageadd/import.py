import logging

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

try:
    GTK_AVAILABLE = False
    if GI_AVAILABLE:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        GTK_AVAILABLE = True
except (ImportError, ValueError):
    pass

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

import paperwork_backend.docimport

from .... import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.windows = []
        self.active_doc_id = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_scan_buttons_popover_sources',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_scan_buttons_popover',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageadd.source_popover'
                ],
            },
            {
                'interface': 'import',
                'defaults': [
                    'paperwork_backend.docimport.img',
                    'paperwork_backend.docimport.pdf',
                ],
            },
            {
                'interface': 'notifications',
                'defaults': ['paperwork_gtk.notifications.dialog'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "mainloop_schedule", self.core.call_all,
            "pageadd_sources_refresh"
        )

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def pageadd_get_sources(self, out: list):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageadd", "source_box.glade"
        )
        source_long_txt = _("Import image or PDF file(s)")
        source_short_txt = _("Import file(s)")
        img = "insert-image-symbolic"

        widget_tree.get_object("source_image").set_from_icon_name(
            img, Gtk.IconSize.SMALL_TOOLBAR
        )
        widget_tree.get_object("source_name").set_text(source_long_txt)

        out.append(
            (
                widget_tree.get_object("source_selector"),
                source_short_txt, "import", self._on_import
            )
        )

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def doc_open(self, doc_id, doc_url):
        if self.core.call_success("is_doc", doc_url) is None:
            # New document --> no need to track this doc id.
            # Importer will create a new document in time
            self.active_doc_id = None
            return
        self.active_doc_id = doc_id

    def doc_close(self):
        self.active_doc_id = None

    def _on_import(self, doc_id, doc_url, source_id):
        LOGGER.info("Opening file chooser dialog")

        mimes = []
        self.core.call_all("get_import_mime_type", mimes)

        dialog = Gtk.FileChooserDialog(
            _("Select a file or a directory to import"),
            self.windows[-1],
            Gtk.FileChooserAction.OPEN,
            (
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                # WORKAROUND(Jflesch): Use response ID 0 so the user
                # can select a folder.
                Gtk.STOCK_OPEN, 0
            )
        )
        dialog.set_select_multiple(True)
        dialog.set_local_only(False)

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All supported file formats"))
        for (txt, mime) in mimes:
            filter_all.add_mime_type(mime)
        dialog.add_filter(filter_all)

        file_filter = Gtk.FileFilter()
        file_filter.set_name(_("Any files"))
        file_filter.add_pattern("*.*")
        dialog.add_filter(file_filter)

        for (txt, mime) in mimes:
            file_filter = Gtk.FileFilter()
            file_filter.add_mime_type(mime)
            file_filter.set_name(txt)
            dialog.add_filter(file_filter)

        dialog.set_filter(filter_all)

        dialog.connect("response", self._on_dialog_response)
        dialog.show_all()

    def _log_result(self, file_import):
        LOGGER.info("Import result:")
        LOGGER.info("- Imported files: %s", file_import.imported_files)
        LOGGER.info("- Non-imported files: %s", file_import.ignored_files)
        LOGGER.info("- New documents: %s", file_import.new_doc_ids)
        LOGGER.info("- Updated documents: %s", file_import.upd_doc_ids)
        for (k, v) in file_import.stats.items():
            LOGGER.info("- %s: %s", k, v)

    def _show_no_importer(self, file_uris):
        msg = (
            _("Don't know how to import '%s'. Sorry.") % (file_uris)
        )
        flags = (
            Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        dialog = Gtk.MessageDialog(
            transient_for=self.windows[-1],
            flags=flags,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=msg
        )
        dialog.connect("response", lambda dialog, response: dialog.destroy())
        dialog.show_all()

    def _show_result_no_doc(self):
        msg = _("No new document to import found")
        flags = (
            Gtk.DialogFlags.MODAL |
            Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        dialog = Gtk.MessageDialog(
            transient_for=self.windows[-1],
            flags=flags,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=msg
        )
        dialog.connect(
            "response", lambda dialog, response: dialog.destroy()
        )
        dialog.show_all()

    def _show_result_doc(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        assert(doc_url is not None)

        if self.active_doc_id != doc_id:
            self.core.call_all("doc_open", doc_id, doc_url)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages <= 0:
            # empty PDF ?
            LOGGER.warning("Document import %s, but no page in it ?!", doc_id)
            return
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "doc_goto_page", nb_pages - 1
        )

    def _show_result_notification(self, file_import):
        msg = _("Imported:\n")
        for (k, v) in file_import.stats.items():
            msg += ("- {}: {}\n".format(k, v))
        msg = msg.strip()

        notification = self.core.call_success(
            "get_notification_builder", _("Import successful"),
            need_actions=True
        )
        if notification is not None:
            notification.set_message(
                msg
            ).set_icon(
                "document-new"
            ).add_action(
                "delete", _("Delete imported files"),
                self._delete_files, file_import.imported_files
            ).show()

    def _show_result(self, file_import):
        doc_id = None
        if len(file_import.upd_doc_ids) > 0:
            doc_id = list(file_import.upd_doc_ids)[0]
        if len(file_import.new_doc_ids) > 0:
            doc_id = list(file_import.new_doc_ids)[0]
        if doc_id is None:
            self._show_result_no_doc()
            return
        self._show_result_doc(doc_id)
        self._show_result_notification(file_import)

    def _add_to_recent(self, file_uris):
        for file_uri in file_uris:
            if self.core.call_success("fs_isdir", file_uri) is None:
                # If the user imported a file, assume they won't import it
                # twice but they may import again other files from the same
                # directory
                file_uri = self.core.call_success("fs_dirname", file_uri)
            LOGGER.info("Adding %s to recently used files", file_uri)
            Gtk.RecentManager().add_item(file_uri)

    def _on_dialog_response(self, dialog, response_id):
        if (response_id != 0 and
                response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User canceled (response_id=%d)", response_id)
            dialog.destroy()
            return

        selected = dialog.get_uris()
        dialog.destroy()
        LOGGER.info("Importing: %s", selected)

        file_import = paperwork_backend.docimport.FileImport(
            selected, self.active_doc_id
        )

        importers = []
        self.core.call_all("get_importer", importers, file_import)
        if len(importers) <= 0:
            self._show_no_importer(selected)
            return
        # TODO(Jflesch): Should ask the user what must be done
        importer = importers[0]

        self._add_to_recent(selected)

        promise = importer.get_import_promise()
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(self._log_result, file_import)
        promise = promise.then(self._show_result, file_import)
        self.core.call_success("transaction_schedule", promise)

    def _delete_files(self, file_uris):
        LOGGER.info("Moving imported file(s) to trash ...")
        for file_uri in file_uris:
            LOGGER.info("Moving %s to trash ...", file_uri)
            self.core.call_all("fs_unlink", file_uri)
        notification = self.core.call_success(
            "get_notification_builder", _("Imported file(s) deleted"),
        )
        if notification is None:
            return
        notification.set_icon("edit-delete").show()
