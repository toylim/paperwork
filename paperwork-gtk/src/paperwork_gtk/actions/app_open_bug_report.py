import gettext
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -100

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []
        self.action = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'app_action',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Report bug"), "win.open_bug_report")
        self.core.call_all("menu_app_append_item", item)

        action = Gio.SimpleAction.new('open_bug_report', None)
        action.connect("activate", self._open_bug_report)
        self.core.call_all("app_actions_add", action)

    def on_gtk_window_opened(self, window):
        self.active_windows.append(window)

    def on_gtk_window_closed(self, window):
        self.active_windows.remove(window)

    def _open_bug_report(self, *args, **kwargs):
        self.core.call_all("open_bug_report", self.active_windows[-1])
