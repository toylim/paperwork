import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.scan_id_to_doc_id = {}

    def get_interfaces(self):
        return ['scan2doc']

    def get_deps(self):
        return {
            'interfaces': [
                ('document_storage', ['paperwork_backend.model.workdir']),
                ('doc_img_import', ['paperwork_backend.model.img']),
                ('pillow', ['paperwork_backend.pillow.img']),
                ('scan', ['paperwork_backend.docscan.libinsane']),
            ]
        }

    def scan2doc_scan_id_to_doc_id(self, scan_id):
        try:
            return self.scan_id_to_doc_id[scan_id]
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

        (scan_id, promise) = self.core.call_success("scan_promise")

        self.scan_id_to_doc_id[scan_id] = doc_id

        transactions = []
        self.core.call_all("doc_transaction_start", transactions, 1)

        def add_scans_to_doc(args):
            (source, scan_id, imgs) = args
            for img in imgs:
                self.core.call_all("doc_img_import_img_by_id", img, doc_id)

                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                if nb_pages is None:
                    nb_pages = 0

                page_url = self.core.call_success(
                    "page_get_img_url", doc_url, nb_pages, write=True
                )
                self.core.call_success("pillow_to_url", img, page_url)
            return len(imgs)

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
            return (doc_id, doc_url)

        def cancel(exc):
            for transaction in transactions:
                transaction.cancel()
            drop_scan_id()
            if new:
                self.core.call_all("storage_delete_doc_id", doc_id)
            raise exc

        promise = promise.then(add_scans_to_doc)
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, run_transactions
            )
        )
        promise = promise.then(drop_scan_id)
        promise = promise.catch(cancel)
        return promise
