"""
Takes of various document format that are actually converted to PDF files
so Paperwork can read them quickly
"""
import logging

import openpaperwork_core
import openpaperwork_core.promise

from .. import _


LOGGER = logging.Logger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 200

    def __init__(self):
        super().__init__()
        self.pending_doc_urls = set()
        self.file_types = {}

    def get_interfaces(self):
        return [
            "page_img",
            "sync",
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_converter',
                'defaults': ['paperwork_backend.converter.libreoffice'],
            },
            {
                'interface': 'doc_pdf_import',
                'defaults': ['paperwork_backend.model.pdf'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'transaction_manager',
                'defaults': ['paperwork_backend.sync'],
            },
        ]

    def init(self, core):
        super().init(core)

        file_types = set()
        self.core.call_all("converter_get_file_types", file_types)
        self.file_types = {ext: mime for (mime, ext) in file_types}

    def _is_converted(self, doc_url):
        for doc_file_url in self.core.call_success("fs_listdir", doc_url):
            doc_filename = self.core.call_success("fs_basename", doc_file_url)
            if "." not in doc_filename:
                continue
            (doc_filename, doc_ext) = doc_filename.rsplit(".", 1)
            doc_filename = doc_filename.lower()
            doc_ext = doc_ext.lower()
            if doc_filename == "doc" and doc_ext in self.file_types:
                return (doc_file_url, doc_ext)
        else:
            # not a converted document
            return (None, None)

    def _update_pdf(self, doc_id, doc_url, doc_file_url, doc_ext):
        LOGGER.debug(
            "Document %s: %s (%s)",
            doc_id, doc_file_url, self.file_types[doc_ext]
        )
        doc_mtime = self.core.call_success("fs_get_mtime", doc_file_url)

        pdf = self.core.call_success(
            "doc_get_pdf_url_by_url", doc_url, write=True
        )
        if not self.core.call_success("fs_exists", pdf):
            pdf_mtime = -1
        else:
            pdf_mtime = self.core.call_success("fs_get_mtime", pdf)

        if pdf_mtime >= doc_mtime:
            LOGGER.debug("Document %s: PDF is up-to-date")
            return

        LOGGER.info(
            "Document %s: Updating PDF: %s --> %s",
            doc_id, doc_file_url, pdf
        )
        self.core.call_all(
            "on_progress", "converting", 0.0,
            _("Converting document %s to PDF ...")
        )
        self.core.call_success(
            "convert_file_to_pdf",
            doc_file_url, self.file_types[doc_ext],
            pdf
        )
        LOGGER.info("PDF updated")
        self.core.call_all("on_progress", "converting", 1.0)

    def page_get_img_url(self, doc_url, page_idx, write=False):
        if page_idx != 0:
            return
        # prevent double conversion
        if doc_url in self.pending_doc_urls:
            LOGGER.debug("Doc %s will already be checked", doc_url)
            return
        self.pending_doc_urls.add(doc_url)

        (doc_file_url, doc_ext) = self._is_converted(doc_url)
        if doc_file_url is None:
            self.pending_doc_urls.remove(doc_url)
            return

        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._update_pdf, args=(
                doc_id, doc_url, doc_file_url, doc_ext
            )
        )

        def do_transaction():
            transactions = []
            self.core.call_all("doc_transaction_start", transactions, 1)
            transactions.sort(key=lambda t: -t.priority)

            try:
                for transaction in transactions:
                    transaction.upd_obj(doc_id)
                for transaction in transactions:
                    transaction.commit()
            except Exception:
                for transaction in transactions:
                    transaction.cancel()

        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            self.core, do_transaction
        ))
        promise = promise.then(self.pending_doc_urls.remove, doc_url)
        self.core.call_success("transaction_schedule", promise)

        return None

    def _check_all_docs(self):
        if len(self.file_types) <= 0:
            LOGGER.info("No file converter available")
            return

        all_docs = []
        self.core.call_all("storage_get_all_docs", all_docs, only_valid=False)

        self.pending_doc_urls.update((x[1] for x in all_docs))

        msg = _("Checking converted documents")
        self.core.call_all("on_progress", "converted_check", 0.0, msg)
        total = len(all_docs)
        for (idx, (doc_id, doc_url)) in enumerate(all_docs):
            (doc_file_url, doc_ext) = self._is_converted(doc_url)
            if doc_file_url is None:
                continue
            self._update_pdf(doc_id, doc_url, doc_file_url, doc_ext)
            self.pending_doc_urls.remove(doc_url)
            if idx % 100 == 0:
                self.core.call_all(
                    "on_progress", "converted_check", idx / total, msg
                )
        self.core.call_all("on_progress", "converted_check", 1.0)

    def sync(self, promises: list):
        promise = openpaperwork_core.promise.ThreadedPromise(
            self.core, self._check_all_docs
        )
        promises.insert(0, promise)
