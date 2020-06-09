import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise

from .. import _


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -150

    def __init__(self):
        super().__init__()
        self.action = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'app_action',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_app_menu',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_shortcuts',
                'defaults': ['paperwork_gtk.shortcutswin'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def on_doclist_initialized(self):
        item = Gio.MenuItem.new(_("Shortcuts"), "win.open_shortcuts")
        self.core.call_all("menu_app_append_item", item)

        action = Gio.SimpleAction.new('open_shortcuts', None)
        action.connect("activate", self._open_shortcuts)
        self.core.call_all("app_actions_add", action)

    def _open_shortcuts(self, *args, **kwargs):
        self.core.call_success("gtk_show_shortcuts")
