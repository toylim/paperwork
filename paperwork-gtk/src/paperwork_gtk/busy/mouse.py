import logging

import openpaperwork_core
import openpaperwork_core.deps


GI_AVAILABLE = False
GDK_AVAILABLE = False

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk
        GDK_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.refcount = 0
        self.windows = []

    def get_interfaces(self):
        return [
            'busy',
            'chkdeps',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GDK_AVAILABLE:
            out['gdk'].update(openpaperwork_core.deps.GDK)

    def _set_mouse_cursor(self, offset):
        self.refcount += offset
        assert(self.refcount >= 0)

        if len(self.windows) <= 0:
            LOGGER.warning(
                "Cannot change mouse cursor: no main window defined"
            )
            return

        if self.refcount > 0:
            LOGGER.info("Mouse cursor --> busy")
            display = self.windows[-1].get_display()
            cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.WATCH)
        else:
            LOGGER.info("Mouse cursor --> idle")
            cursor = None
        self.windows[-1].get_window().set_cursor(cursor)

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def on_busy(self):
        self._set_mouse_cursor(1)

    def on_idle(self):
        self._set_mouse_cursor(-1)
