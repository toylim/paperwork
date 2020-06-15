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
        self.active_page_idx = -1

    def get_interfaces(self):
        return [
            'action',
            'action_page',
            'action_page_edit',
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
                'interface': 'gtk_page_editor',
                'defaults': ['paperwork_gtk.mainwindow.pageeditor'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        action = Gio.SimpleAction.new("page_edit", None)
        action.connect("activate", self._on_edit)
        self.core.call_all("app_actions_add", action)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def on_page_shown(self, page_idx):
        self.active_page = page_idx

    def _on_edit(self, *args, **kwargs):
        self.core.call_all(
            "gtk_open_page_editor", *self.active_doc, self.active_page
        )
