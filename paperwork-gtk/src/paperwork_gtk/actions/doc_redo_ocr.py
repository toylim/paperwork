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
ACTION_NAME = "doc_redo_ocr"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -90

    def __init__(self):
        super().__init__()
        self.active_doc = None
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
            {
                'interface': 'ocr',
                'defaults': ['paperwork_backend.guesswork.ocr.pyocr'],
            },
        ]

    def init(self, core):
        super().init(core)
        if not GLIB_AVAILABLE:
            return
        self.action = Gio.SimpleAction.new(ACTION_NAME, None)
        self.action.connect("activate", self._redo_ocr)

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_gtk.deps.GLIB)

    def on_doclist_initialized(self):
        self.core.call_all("app_actions_add", self.action)
        self.core.call_all(
            "add_doc_action", _("Redo OCR on document"), "win." + ACTION_NAME
        )

    def on_backend_readonly(self):
        self.action.set_enabled(False)

    def on_backend_readwrite(self):
        self.action.set_enabled(True)

    def doc_open(self, doc_id, doc_url):
        self.active_doc = (doc_id, doc_url)

    def doc_close(self):
        self.active_doc = None

    def _redo_ocr(self, action, parameter):
        assert(self.active_doc is not None)
        (doc_id, doc_url) = self.active_doc

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            LOGGER.warning("No pages in document %s. Nothing to do", doc_id)
            return

        LOGGER.info(
            "Will redo OCR on document %s (nb pages = %d)", doc_id, nb_pages
        )

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=("on_progress", "redo_ocr", 0.0, _("OCR on %s") % doc_id)
        )
        promise = promise.then(lambda *args, **kwargs: None)

        for page_idx in range(0, nb_pages):
            promise = promise.then(
                self.core.call_all, "on_progress", "redo_ocr",
                page_idx / nb_pages,
                _("OCR on %s p%d") % (doc_id, page_idx + 1)
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

        for transaction in transactions:
            transaction.del_obj(doc_id)

        for transaction in transactions:
            transaction.commit()
