import gettext
import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_gtk.deps


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000000

    def __init__(self):
        super().__init__()
        self.windows = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_settings',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'config',
                'defaults': ['openpaperwork_core.config'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.workdir = self.core.call_success("config_get", "workdir")

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def complete_settings(self, global_widget_tree):
        widget_tree = self.core.call_success(
            "gtk_load_widget_tree", "paperwork_gtk.settings", "storage.glade"
        )

        workdir_button = widget_tree.get_object("work_dir_chooser_button")
        basename = self.core.call_success("fs_basename", self.workdir)
        workdir_button.set_label(basename)
        workdir_button.connect("clicked", self._on_button_clicked, widget_tree)

        self.core.call_success(
            "add_setting_to_dialog", global_widget_tree, _("Storage"),
            [widget_tree.get_object("workdir")]
        )

    def _on_button_clicked(self, button, widget_tree):
        dialog = Gtk.FileChooserDialog(
            _("Work Directory"),
            self.windows[-1],
            Gtk.FileChooserAction.SELECT_FOLDER,
            (
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
            )
        )
        dialog.set_modal(True)
        dialog.set_local_only(False)
        dialog.connect("response", self._on_dialog_response, widget_tree)
        dialog.show_all()

    def _on_dialog_response(self, dialog, response_id, widget_tree):
        if (response_id != Gtk.ResponseType.ACCEPT and
                response_id != Gtk.ResponseType.OK and
                response_id != Gtk.ResponseType.YES and
                response_id != Gtk.ResponseType.APPLY):
            LOGGER.info("User canceled (response_id=%d)", response_id)
            dialog.destroy()
            return

        workdir = dialog.get_uri()
        dialog.set_visible(False)

        LOGGER.info("Setting work directory to %s", workdir)
        self.core.call_all("config_put", "workdir", workdir)

        basename = self.core.call_success("fs_basename", workdir)
        widget_tree.get_object("work_dir_chooser_button").set_label(basename)

    def config_save(self):
        workdir = self.core.call_success("config_get", "workdir")

        if workdir != self.workdir:
            LOGGER.info("Work directory has been changed --> Synchronizing")
            self.core.call_all("transaction_sync_all")

        self.workdir = workdir
