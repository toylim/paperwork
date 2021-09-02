import logging

try:
    from gi.repository import Gio
    GIO_AVAILABLE = True
except (ImportError, ValueError):
    GIO_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def get_interfaces(self):
        return [
            'chkdeps',
            'action',
            'action_app',
            'action_app_find',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_search_field',
                'defaults': ['paperwork_gtk.mainwindow.search.field'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GIO_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def init(self, core):
        super().init(core)
        if not GIO_AVAILABLE:
            return
        action = Gio.SimpleAction.new('app_find', None)
        action.connect("activate", self._focus_on_search_field)
        self.core.call_all("app_actions_add", action)

    def _focus_on_search_field(self, action, parameter):
        self.core.call_all("search_focus")
