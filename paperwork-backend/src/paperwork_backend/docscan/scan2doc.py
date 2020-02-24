import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.scan_id_to_doc_id = {}
        self.doc_id_to_scan_id = {}

    def get_interfaces(self):
        return ['scan2doc']

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop.asyncio'],
            },
            {
                'interface': 'page_img',
                'defaults': ['paperwork_backend.model.img'],
            },
            {
                'interface': 'pillow',
                'defaults': ['paperwork_backend.pillow.img'],
            },
            {
                'interface': 'scan',
                'defaults': ['paperwork_backend.docscan.libinsane'],
            },
            {
                'interface': 'thread',
                'defaults': ['openpaperwork_core.thread.simple'],
            },
        ]

    def scan2doc_scan_id_to_doc_id(self, scan_id):
        try:
            return self.scan_id_to_doc_id[scan_id]
        except KeyError:
            return None

    def scan2doc_doc_id_to_scan_id(self, doc_id):
        try:
            return self.doc_id_to_scan_id[doc_id]
        except KeyError:
            return None

    def scan2doc_promise(self, *args, doc_id=None, **kwargs):
        if doc_id is not None:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            nb_pages = self.core.call_success(
                "doc_get_nb_pages_by_url", doc_url
            )
            new = (nb_pages <= 0) if nb_pages is not None else True
        else:
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
            new = True

        (scan_id, p) = self.core.call_success("scan_promise")

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all,
            args=("on_scan2doc_start", scan_id, doc_id, doc_url)
        )
        promise = promise.then(lambda *args, **kwargs: None)
        promise = promise.then(p)

        self.scan_id_to_doc_id[scan_id] = doc_id
        self.doc_id_to_scan_id[doc_id] = scan_id

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)
        transactions.sort(key=lambda transaction: -transaction.priority)

        def add_scans_to_doc(args):
            (source, scan_id, imgs) = args
            nb = 0
            for img in imgs:
                nb += 1
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                if nb_pages is None:
                    nb_pages = 0
                page_url = self.core.call_success(
                    "page_get_img_url", doc_url, nb_pages, write=True
                )
                self.core.call_success("pillow_to_url", img, page_url)
                self.core.call_all(
                    "mainloop_schedule", self.core.call_all,
                    "on_scan2doc_page_scanned",
                    scan_id, doc_id, doc_url, nb_pages
                )
            return nb

        def run_transactions(nb_imgs):
            if nb_imgs <= 0:
                for transaction in transactions:
                    transaction.cancel()
                return
            for transaction in transactions:
                if new:
                    transaction.add_obj(doc_id)
                else:
                    transaction.upd_obj(doc_id)
            for transaction in transactions:
                transaction.commit()

        def drop_scan_id(*args, **kwargs):
            self.scan_id_to_doc_id.pop(scan_id)
            self.doc_id_to_scan_id.pop(doc_id)
            return (doc_id, doc_url)

        def notify_end(*args, **kwargs):
            self.core.call_all("on_scan2doc_end", scan_id, doc_id, doc_url)
            return (doc_id, doc_url)

        def cancel(exc):
            for transaction in transactions:
                transaction.cancel()
            drop_scan_id()
            if new:
                self.core.call_all("storage_delete_doc_id", doc_id)
            raise exc

        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, add_scans_to_doc
            )
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, run_transactions
            )
        )
        promise = promise.then(drop_scan_id)
        promise = promise.then(notify_end)

        promise = promise.catch(cancel)
        return promise
