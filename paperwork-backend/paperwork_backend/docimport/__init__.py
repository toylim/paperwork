import collections

import openpaperwork_core.promise


class FileImport(object):
    """
    Used as both input and output for importer objects.
    Users may import many files at once and files may not be imported at all
    (for example if they were already imported) --> FileImport objects indicate
    what must still be done, what has been done, and what has not been done at
    all.
    """
    def __init__(self, file_uris_to_import, active_doc_id=None):
        self.active_doc_id = active_doc_id
        # those attributes will be updated by importers
        self.ignored_files = set(file_uris_to_import)
        self.imported_files = set()
        self.new_doc_ids = set()
        self.upd_doc_ids = set()
        self.stats = collections.defaultdict(lambda: 0)


class BaseImporter(object):
    def __init__(self, plugin, file_import, single_file_importer_cls):
        self.plugin = plugin
        self.core = plugin.core
        self.file_import = file_import
        self.single_file_importer_cls = single_file_importer_cls

    def _get_importables(self):
        # to implement by sub-classes
        assert()

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
            new_promise = self.single_file_importer_cls(
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
