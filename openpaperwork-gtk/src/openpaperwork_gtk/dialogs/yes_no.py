import logging

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


class Plugin(openpaperwork_core.PluginBase):
    """
    Provides a simple way to show a Yes/No question popup (usually something
    along the line of "are you really really really sure you want to do
    that ?").
    """

    def __init__(self):
        super().__init__()
        self.windows = []

    def get_interfaces(self):
        return [
            'chkdeps',
            'gtk_dialog_yes_no',
            'gtk_window_listener',
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def gtk_show_dialog_yes_no(self, origin, msg, *args, **kwargs):
        confirm = Gtk.MessageDialog(
            parent=self.windows[-1],
            flags=(
                Gtk.DialogFlags.MODAL |
                Gtk.DialogFlags.DESTROY_WITH_PARENT
            ),
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=msg
        )
        confirm.connect("response", self._on_response, origin, (args, kwargs))
        confirm.show_all()
        return True

    def _on_response(self, dialog, response, origin, args):
        (args, kwargs) = args
        if response != Gtk.ResponseType.YES:
            LOGGER.info("User cancelled")
            dialog.destroy()
            self.core.call_all(
                "on_dialog_yes_no_reply", origin, False, *args, **kwargs
            )
            return
        dialog.destroy()
        self.core.call_all(
            "on_dialog_yes_no_reply", origin, True, *args, **kwargs
        )
