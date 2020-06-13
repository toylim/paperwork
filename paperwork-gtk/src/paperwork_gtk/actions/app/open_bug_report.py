import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []

    def get_interfaces(self):
        return [
            'action',
            'action_app',
            'action_app_open_bug_report',
            'chkdeps',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new('open_bug_report', None)
        action.connect("activate", self._open_bug_report)
        self.core.call_all("app_actions_add", action)

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def _open_bug_report(self, *args, **kwargs):
        self.core.call_all("open_bug_report", self.active_windows[-1])
