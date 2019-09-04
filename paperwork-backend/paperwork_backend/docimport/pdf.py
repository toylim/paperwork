import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise

from . import FileImport


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class _SingleImport(object):
    def __init__(self, core, file_import, src_file_uri, transactions):
        self.core = core
        self.file_import = file_import
        self.src_file_uri = src_file_uri
        self.transactions = transactions
        self.doc_id = None
        self.doc_url = None

    def _basic_import(self, file_uri):
        (self.doc_id, self.doc_url) = self.core.call_success(
            "doc_pdf_import", file_uri
        )
        self.file_import.new_doc_ids.add(self.doc_id)
        self.file_import.stats[_("PDF")] += 1

    def _transaction_add_obj(self, transaction):
        transaction.add_obj(self.doc_id)

    def get_promise(self):
        promise = openpaperwork_core.promise.Promise(self.core)

        promise = promise.then(self._basic_import, self.src_file_uri)
        for transaction in self.transactions:
            promise = promise.then(
                self._transaction_add_obj, transaction
            )

        return promise


class PdfImporter(object):
    def __init__(self, plugin, file_import):
        self.plugin = plugin
        self.core = plugin.core
        self.file_import = file_import

    def _get_importables(self):
        for file_uri in self.file_import.ignored_files:
            mime = self.core.call_success("fs_get_mime", file_uri)
            if mime is not None:
                if mime == self.plugin.MIME_TYPE:
                    yield file_uri
                continue
            if file_uri.lower().endswith(self.plugin.FILE_EXTENSION):
                yield file_uri

    def can_import(self):
        return len(list(self._get_importables())) > 0

    def get_import_promise(self):
        """
        Return a promise with all the steps required to import files
        specified in `file_import` (see constructor), transactions included.
        """
        promise = openpaperwork_core.promise.Promise(self.core)
        to_import = list(self._get_importables())
        transactions = []
        self.core.call_all(
            "doc_transaction_start", transactions, len(to_import)
        )

        for file_uri in to_import:
            new_promise = _SingleImport(
                    self.core, self.file_import, file_uri, transactions
                ).get_promise()
            promise = promise.then(new_promise)

        for transaction in transactions:
            promise = promise.then(transaction.commit)

        for file_uri in to_import:
            promise = promise.then(
                self.file_import.ignored_files.remove,file_uri
            )
            promise = promise.then(
                self.file_import.imported_files.add, file_uri
            )

        return promise.then(
            self.core.call_all, "on_import_done", self.file_import
        )

    def __str__(self):
        return _("Import PDF")


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSION = ".pdf"
    MIME_TYPE = "application/pdf"

    def get_interfaces(self):
        return [
            "import"
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_pdf_import', ['paperwork_backend.model.pdf',]),
                ('fs', ['paperwork_backend.fs.gio',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
            ]
        }

    def get_import_mime_type(self, out: list):
        out.append(("PDF", self.MIME_TYPE))

    def get_importer(self, out: list, file_import: FileImport):
        importer = PdfImporter(self, file_import)
        if not importer.can_import():
            return
        out.append(importer)
