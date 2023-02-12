import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "doc_open_external"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []

    def get_interfaces(self):
        return [
            'action',
            'action_doc',
            'action_doc_open_external',
            'chkdeps',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'external_apps',
                'defaults': [
                    'openpaperwork_core.external_apps.dbus',
                    'openpaperwork_core.external_apps.windows',
                    'openpaperwork_core.external_apps.xdg',
                ],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        action = Gio.SimpleAction.new(ACTION_NAME, None)
        action.connect("activate", self._open_external)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def _open_external(self, action, parameter):
        assert self.active_doc is not None
        (doc_id, doc_url) = self.active_doc
        self.core.call_success("external_app_open_folder", doc_url)
