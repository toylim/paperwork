import gettext
import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext
ACTION_NAME = "doc_properties"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.action = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'doc_action',
            'doc_open',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'backend_readonly',
                'defaults': ['paperwork_gtk.readonly'],
            },
            {
                'interface': 'doc_actions',
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
        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._open_properties)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)

    def on_doclist_initialized(self):
        self.core.call_all("app_actions_add", self.action)
        self.core.call_all(
            "add_doc_action", _("Document properties"), "win." + ACTION_NAME
        )

    def on_backend_readonly(self):
        self.action.set_enabled(False)

    def on_backend_readwrite(self):
        self.action.set_enabled(True)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def _open_properties(self, action, parameter):
        assert(self.active_doc is not None)
        active = self.active_doc

        LOGGER.info("Opening properties of document %s", active[0])
        self.core.call_all("open_doc_properties", *active)
