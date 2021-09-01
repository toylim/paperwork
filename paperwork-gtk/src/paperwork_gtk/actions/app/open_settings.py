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
            'action_app_open_settings',
            'chkdeps',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_settings_dialog',
                'defaults': ['paperwork_gtk.settings'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new('open_settings', None)
        action.connect("activate", self._open_settings)
        self.core.call_all("app_actions_add", action)

    def _open_settings(self, *args, **kwargs):
        self.core.call_success("gtk_open_settings")
