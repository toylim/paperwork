import datetime
import functools
import gettext
import logging
import os
import shutil
import unicodedata

import whoosh.fields
import whoosh.index
import whoosh.qparser
import whoosh.query
import whoosh.sorting

import openpaperwork_core

from .. import sync


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)

WHOOSH_SCHEMA = whoosh.fields.Schema(
    docid=whoosh.fields.ID(stored=True, unique=True, sortable=True),
    docfilehash=whoosh.fields.ID(),
    content=whoosh.fields.TEXT(spelling=True),
    label=whoosh.fields.KEYWORD(commas=True, scorable=True),
    date=whoosh.fields.DATETIME(sortable=True),
    last_read=whoosh.fields.DATETIME(stored=True),
)


def strip_accents(string):
    """
    Strip all the accents from the string
    """
    return u''.join(
        (character for character in unicodedata.normalize('NFD', string)
         if unicodedata.category(character) != 'Mn'))


class CustomFuzzySearch(whoosh.qparser.query.FuzzyTerm):
    def __init__(
                self, fieldname, text, boost=1.0, maxdist=1,
                prefixlength=0, constantscore=True
            ):
        whoosh.qparser.query.FuzzyTerm.__init__(
            self, fieldname, text, boost, maxdist,
            prefixlength, constantscore=True
        )


class WhooshTransaction(object):
    """
    Transaction to apply on the index. Methods may be slow but they
    are thread-safe.
    """
    def __init__(self, plugin, total_expected=-1):
        LOGGER.debug("Starting Whoosh index transaction")
        self.core = plugin.core
        self.writer = plugin.index.writer()
        self.counts = {
            'add': 0,
            'upd': 0,
            'del': 0,
        }
        self.unchanged = 0
        self.total_expected = total_expected

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def __del__(self):
        self.cancel()

    def _update_doc_in_index(self, doc_id):
        """
        Collect infos on the document and add/update a document in the index
        """
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        doc_mtime = []
        self.core.call_all("doc_get_mtime_by_url", doc_mtime, doc_url)
        doc_mtime = datetime.datetime.fromtimestamp(max(doc_mtime))

        doc_hash = []
        self.core.call_all("doc_get_hash_by_url", doc_hash, doc_url)
        if len(doc_hash) <= 0:
            # we get a hash only for PDF documents, not image documents.
            doc_hash = "undefined"
        else:
            doc_hash = functools.reduce(lambda x, y: x ^ y, doc_hash)
            doc_hash = ("%X" % doc_hash)

        doc_text = []
        self.core.call_all("doc_get_text_by_url", doc_text, doc_url)
        doc_text = "\n\n".join(doc_text)
        doc_text = strip_accents(doc_text)

        doc_labels = set()
        self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
        doc_labels = ",".join([label[0] for label in doc_labels])
        doc_labels = strip_accents(doc_labels)

        doc_date = self.core.call_success("doc_get_date_by_id", doc_id)
        if doc_date is None:
            doc_date = datetime.datetime(year=1970, month=1, day=1)

        query = whoosh.query.Term("docid", doc_id)
        self.writer.delete_by_query(query)

        self.writer.update_document(
            docid=doc_id,
            docfilehash=doc_hash,
            content=doc_text,
            label=doc_labels,
            date=doc_date,
            last_read=doc_mtime
        )

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        total = sum(self.counts.values()) + self.unchanged
        return total / self.total_expected

    def add_obj(self, doc_id):
        LOGGER.info("Adding document '%s' to index", doc_id)
        self.counts['add'] += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "index_update", self._get_progression(),
            _("Indexing new document %s") % doc_id
        )
        self._update_doc_in_index(doc_id)

    def del_obj(self, doc_id):
        LOGGER.info("Removing document '%s' from index", doc_id)
        self.counts['del'] += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "index_update", self._get_progression(),
            _("Removing document %s from index") % doc_id
        )
        query = whoosh.query.Term("docid", doc_id)
        self.writer.delete_by_query(query)

    def upd_obj(self, doc_id):
        LOGGER.info("Updating document '%s' in index", doc_id)
        self.counts['upd'] += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "index_update", self._get_progression(),
            _("Indexing updated document %s") % doc_id
        )
        self._update_doc_in_index(doc_id)

    def unchanged_obj(self, doc_id):
        self.unchanged += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "index_update", self._get_progression(),
            _("Document unchanged %s") % doc_id
        )

    def cancel(self):
        if self.writer is None:
            return

        self.core.call_one(
            "schedule", self.core.call_all,
            'on_index_cancel'
        )
        LOGGER.info("Canceling transaction")
        self.writer.cancel()
        self.writer = None
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_index_updated"
        )

    def commit(self):
        total = sum(self.counts.values())
        if total == 0:
            LOGGER.info(
                "commit() called but nothing to commit."
                " Cancelling transaction"
            )
            self.cancel()
            return
        LOGGER.info("Committing changes to Whoosh index: %s", str(self.counts))
        self.core.call_one(
            "schedule", self.core.call_all,
            'on_index_commit_start'
        )
        self.writer.commit()
        self.writer = None
        self.core.call_one(
            "schedule", self.core.call_all,
            'on_progress', 'index_update', 1.0
        )
        self.core.call_all(
            "schedule", self.core.call_all,
            'on_index_commit_end'
        )


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.obs_callbacks = []
        self.query_parsers = {
            'strict': [],
            'fuzzy': [],
        }
        self.index = None

        # Whoosh index *must* be on local disk --> we use Unix path here, not
        # URLs

        self.local_dir = os.path.expanduser("~/.local")
        self.index_dir = None

    def get_interfaces(self):
        return [
            "index",
            "syncable",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('fs', ['paperwork_backend.fs.gio',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
                # Optional dependencies:
                # ('page_boxes', [
                #     'paperwork_backend.model.hocr',
                #     'paperwork_backend.model.pdf',
                # ]),
                # ('doc_hash', ['paperwork_backend.model.pdf',]),
                # ('doc_labels', ['paperwork_backend_model.labels',])
            ]
        }

    def init(self, core):
        super().init(core)

        if self.index_dir is None:
            data_dir = os.getenv(
                "XDG_DATA_HOME", os.path.join(self.local_dir, "share")
            )
            self.index_dir = os.path.join(data_dir, "paperwork", "index")

        need_index_rewrite = True
        while need_index_rewrite:
            try:
                LOGGER.info(
                    "Opening Whoosh index '%s' ...", self.index_dir
                )
                self.index = whoosh.index.open_dir(self.index_dir)
                # check that the schema is up-to-date
                # We use the string representation of the schemas, because
                # previous versions of whoosh don't always implement __eq__
                if str(self.index.schema) != str(WHOOSH_SCHEMA):
                    raise Exception("Index version mismatch")
                need_index_rewrite = False
            except Exception as exc:
                LOGGER.warning(
                    "Failed to open index '%s': %s."
                    " Will rebuild index from scratch",
                    self.index_dir, exc
                )

            if need_index_rewrite:
                self._destroy()

                LOGGER.info("Creating a new index")

                os.makedirs(self.index_dir, mode=0o700)
                if os.name == 'nt':  # hide ~/.local on Windows
                    local_dir_url = self.core.call_success(
                        "fs_safe", self.local_dir
                    )
                    self.core.call_all("fs_hide", local_dir_url)

                new_index = whoosh.index.create_in(
                    self.index_dir, WHOOSH_SCHEMA
                )
                new_index.close()
                LOGGER.info("Index '%s' created" % self.index_dir)

        self.query_parsers = {
            'fuzzy': [
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=CustomFuzzySearch
                ),
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=whoosh.qparser.query.Prefix
                ),
            ],
            'strict': [
                whoosh.qparser.MultifieldParser(
                    ["label", "content"], schema=self.index.schema,
                    termclass=whoosh.query.Term
                ),
            ],
        }

    def _close(self):
        LOGGER.info("Closing Whoosh index")
        if self.index is not None:
            self.index.close()
        self.index = None

    def _destroy(self):
        self._close()
        if os.path.exists(self.index_dir):
            LOGGER.warning("Destroying the index ...")
            shutil.rmtree(self.index_dir)
            LOGGER.warning("Index destroyed")

    def doc_transaction_start(self, out: list, total_expected=-1):
        out.append(WhooshTransaction(self, total_expected))

    def index_search(self, out: list, query, limit=None, search_type='fuzzy'):
        query = query.strip()
        query = strip_accents(query)
        if query == "":
            queries = [whoosh.query.Every()]
        else:
            queries = []
            for parser in self.query_parsers[search_type]:
                queries.append(parser.parse(query))

        with self.index.searcher() as searcher:
            for query in queries:
                results = searcher.search(query, limit=limit, sortedby='docid')
                has_results = False
                for result in results:
                    has_results = True
                    out.append(result['docid'])
                    if limit is not None and len(out) >= limit:
                        return
                if has_results:
                    return

    def index_get_doc_id_by_hash(self, doc_hash):
        doc_hash = "%X" % doc_hash
        with self.index.searcher() as searcher:
            results = searcher.search(
                whoosh.query.Term('docfilehash', doc_hash)
            )
            if len(results) <= 0:
                return None
            return results[0]

    def sync(self, promises: list):
        """
        Requests the document list from the document storage plugin
        and updates the index accordingly.

        This call is asynchronous and use the main loop to do its job.
        """
        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        storage_all_docs.sort()
        storage_all_docs = [
            sync.StorageDoc(self.core, doc[0], doc[1])
            for doc in storage_all_docs
        ]

        with self.index.searcher() as searcher:
            index_all_docs = searcher.search(whoosh.query.Every(), limit=None)
            index_all_docs = [
                (result['docid'], result['last_read'])
                for result in index_all_docs
            ]

        class IndexDoc(object):
            def __init__(self, index_result):
                (self.key, self.extra) = index_result

        index_all_docs = [IndexDoc(r) for r in index_all_docs]

        transaction = WhooshTransaction(
            self, abs(len(storage_all_docs) - len(index_all_docs))
        )

        promises.append(sync.Syncer(
            self.core, "whoosh", storage_all_docs, index_all_docs, transaction
        ).get_promise())
