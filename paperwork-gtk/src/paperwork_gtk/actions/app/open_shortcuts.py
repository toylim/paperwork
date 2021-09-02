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
    def get_interfaces(self):
        return [
            'action',
            'action_app',
            'action_app_open_shortcuts',
            'chkdeps',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_shortcut_help',
                'defaults': ['paperwork_gtk.shortcutswin'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new('open_shortcuts', None)
        action.connect("activate", self._open_shortcuts)
        self.core.call_all("app_actions_add", action)

    def _open_shortcuts(self, *args, **kwargs):
        self.core.call_success("gtk_show_shortcuts")
