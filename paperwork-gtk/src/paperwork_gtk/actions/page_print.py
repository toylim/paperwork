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
ACTION_NAME = "page_print"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_page_idx = -1
        self.active_windows = []
        self.action = None
        self.item = None

    def get_interfaces(self):
        return [
            'chkdeps',
            'page_action',
            'doc_open',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'app_actions',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'doc_print',
                'defaults': ['paperwork_gtk.print'],
            },
            {
                'interface': 'page_actions',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageinfo.actions'
                ],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        self.item = Gio.MenuItem.new(_("Print page"), "win." + ACTION_NAME)

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._print)

        self.core.call_all("app_actions_add", self.action)

    def on_page_menu_ready(self):
        self.core.call_all("page_menu_append_item", self.item)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _print(self, *args, **kwargs):
        assert(self.active_doc is not None)
        self.core.call_all(
            "doc_print", *self.active_doc, [self.active_page_idx]
        )