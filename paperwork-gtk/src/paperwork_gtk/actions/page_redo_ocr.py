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
ACTION_NAME = "page_redo_ocr"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -70

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
                'interface': 'backend_readonly',
                'defaults': ['paperwork_gtk.readonly'],
            },
            {
                'interface': 'ocr',
                'defaults': ['paperwork_backend.guesswork.ocr.pyocr'],
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

        self.item = Gio.MenuItem.new(
            _("Redo OCR on page"), "win." + ACTION_NAME
        )

        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._redo_ocr)

        self.core.call_all("app_actions_add", self.action)

    def on_page_menu_ready(self):
        self.core.call_all("page_menu_append_item", self.item)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)

    def on_backend_readonly(self):
        self.action.set_enabled(False)

    def on_backend_readwrite(self):
        self.action.set_enabled(True)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def on_page_shown(self, page_idx):
        self.active_page_idx = page_idx

    def _redo_ocr(self, *args, **kwargs):
        (doc_id, doc_url) = self.active_doc
        page_idx = self.active_page_idx

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=(
                "on_progress", "redo_ocr", 0.0,
                _("OCR on %s p%d") % (doc_id, page_idx)
            )
        )
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self.core.call_all,
            args=("ocr_page_by_url", doc_url, page_idx,)
        ))
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(
            self.core.call_all, "on_progress", "redo_ocr", 1.0
        )
        promise = promise.then(lambda *args, **kwargs: None)

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, self._upd_index, args=(doc_id, doc_url,)
        ))
        promise.schedule()

    def _upd_index(self, doc_id, doc_url):
        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0

        for transaction in transactions:
            if nb_pages > 0:
                transaction.upd_obj(doc_id)
            else:
                transaction.del_obj(doc_id)

        for transaction in transactions:
            transaction.commit()
