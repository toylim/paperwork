import logging

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

import openpaperwork_core
import openpaperwork_core.promise
import openpaperwork_gtk.deps

from ... import _


LOGGER = logging.getLogger(__name__)
ACTION_NAME = "page_reset"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -80

    def __init__(self):
        super().__init__()
        self.active_doc = None
        self.active_page_idx = -1
        self.action = None
        self.item = None

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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'page_actions',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageinfo.actions'
                ],
            },
            {
                'interface': 'page_reset',
                'defaults': ['paperwork_backend.model.img_overlay'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return

        self.item = Gio.MenuItem.new(_("Reset page"), "win." + ACTION_NAME)

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._reset)

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

    def _reset(self, *args, **kwargs):
        assert(self.active_doc is not None)

        (doc_id, doc_url) = self.active_doc
        page_idx = self.active_page_idx

        LOGGER.info("Will reset page %s p%d", doc_id, page_idx)

        self.core.call_all("page_reset_by_url", doc_url, page_idx)
        self.core.call_all("doc_reload", doc_id, doc_url)
        self.core.call_success(
            "mainloop_schedule", self.core.call_all, "doc_goto_page", page_idx
        )
        self.core.call_success("transaction_simple", (("upd", doc_id),))
