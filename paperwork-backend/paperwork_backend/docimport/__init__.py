import collections


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
