import gettext
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext
ACTION_NAME = "doc_export"


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_windows = []
        self.action = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_action',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_actions',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.mainwindow.doclist'],
            },
            {
                'interface': 'gtk_exporter',
                'defaults': ['paperwork_gtk.mainwindow.exporter'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._open_exporter)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)

    def on_doclist_initialized(self):
        self.core.call_all("app_actions_add", self.action)
        self.core.call_all(
            "add_doc_action", _("Export document"), "win." + ACTION_NAME
        )

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def _open_exporter(self, *args, **kwargs):
        assert(self.active_doc is not None)
        self.core.call_all("gtk_open_exporter", *self.active_doc)