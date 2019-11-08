"""
This plugin is an helper for other plugins. It provides an easy way to
detect deleted, modified or added documents when synchronizing with the work
directory.
"""

import datetime
import os
import sqlite3

import openpaperwork_core

from . import sync


# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)

CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS documents ("
        " doc_id TEXT PRIMARY KEY,"
        " text TEXT NULL,"
        " mtime INTEGER NOT NULL"
        ")"
    ),
]


class DocTrackerTransaction(object):
    def __init__(self, plugin, sql):
        self.priority = plugin.PRIORITY

        self.core = plugin.core

        self.sql = self.core.call_success(
            "mainloop_execute", sql.cursor
        )
        self.core.call_success(
            "mainloop_execute", self.sql.execute, "BEGIN TRANSACTION"
        )

    def _get_actual_doc_data(self, doc_id, doc_url):
        if (
                    doc_url is not None
                    and self.core.call_success("fs_exists", doc_url)
                    is not None
                ):
            mtime = []
            self.core.call_all("doc_get_mtime_by_url", mtime, doc_url)
            mtime = max(mtime, default=0)

            doc_text = []
            self.core.call_all("doc_get_text_by_url", doc_text, doc_url)
            doc_text = "\n\n".join(doc_text)
        else:
            mtime = 0
            doc_text = None

        return {
            'mtime': mtime,
            'text': doc_text,
        }

    def add_obj(self, doc_id):
        self.upd_obj(doc_id)

    def upd_obj(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        actual = self._get_actual_doc_data(doc_id, doc_url)

        self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "INSERT OR REPLACE INTO documents (doc_id, text, mtime)"
            " VALUES (?, ?, ?)",
            (doc_id, actual['text'], actual['mtime'])
        )

    def del_obj(self, doc_id):
        self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "DELETE FROM documents WHERE doc_id = ?",
            (doc_id,)
        )

    def unchanged_obj(self, doc_id):
        pass

    def cancel(self):
        self.core.call_success(
            "mainloop_execute", self.sql.execute, "ROLLBACK"
        )
        self.core.call_success("mainloop_execute", self.sql.close)

    def commit(self):
        self.core.call_success("mainloop_execute", self.sql.execute, "COMMIT")
        self.core.call_success("mainloop_execute", self.sql.close)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = -10000

    def __init__(self):
        self.local_dir = os.path.expanduser("~/.local")
        self.paperwork_dir = None
        self.sql = None
        self.transaction_factories = []

    def get_interfaces(self):
        return [
            'doc_tracking',
            'syncable',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'fs',
                'defaults': ['paperwork_backend.fs.gio']
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop_asyncio'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.local_dir = os.path.expanduser("~/.local")
        if self.paperwork_dir is None:
            data_dir = os.getenv(
                "XDG_DATA_HOME", os.path.join(self.local_dir, "share")
            )
            self.paperwork_dir = os.path.join(data_dir, "paperwork")

        os.makedirs(self.paperwork_dir, mode=0o700, exist_ok=True)
        if os.name == 'nt':  # hide ~/.local on Windows
            local_dir_url = self.core.call_success("fs_safe", self.local_dir)
            self.core.call_all("fs_hide", local_dir_url)

        sql_file = os.path.join(self.paperwork_dir, 'doc_tracking.db')
        self.sql = self.core.call_success(
            "mainloop_execute", sqlite3.connect, sql_file
        )
        for query in CREATE_TABLES:
            self.core.call_success("mainloop_execute", self.sql.execute, query)

    def doc_tracker_register(self, name, transaction_factory):
        self.transaction_factories.append((name, transaction_factory))

    def doc_tracker_get_all_doc_ids(self):
        doc_ids = self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "SELECT doc_id FROM documents"
        )
        doc_ids = self.core.call_success(
            "mainloop_execute", list, doc_ids
        )
        return {doc_id[0] for doc_id in doc_ids}

    def doc_tracker_get_doc_text_by_id(self, doc_id):
        """
        Return the text of a document as last-known.
        This method is useful when a document is deleted: when a plugin
        is notified that a document has been deleted, it may still need its
        text. Since the document won't be available anymore, we pull its text
        from the database (for instance, for label guesser untraining)
        """
        text = self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "SELECT text FROM documents WHERE doc_id = ? LIMIT 1",
            (doc_id,)
        )
        text = self.core.call_success(
            "mainloop_execute", list, text
        )
        if len(text) <= 0:
            return None
        return text[0][0]

    def doc_transaction_start(self, out: list, total_expected=-1):
        for (name, transaction_factory) in self.transaction_factories:
            out.append(transaction_factory(
                sync=False, total_expected=total_expected
            ))
        out.append(DocTrackerTransaction(self, self.sql))

    def sync(self, promises: list):
        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        storage_all_docs.sort()
        storage_all_docs = [
            sync.StorageDoc(self.core, doc[0], doc[1])
            for doc in storage_all_docs
        ]

        db_all_docs = self.core.call_success(
            "mainloop_execute", self.sql.cursor
        )
        db_all_docs = self.core.call_success(
            "mainloop_execute", db_all_docs.execute,
            "SELECT doc_id, mtime FROM documents"
        )

        class DbDoc(object):
            def __init__(self, result):
                self.key = result[0]
                self.extra = datetime.datetime.fromtimestamp(result[1])

        db_docs = self.core.call_success(
            "mainloop_execute",
            lambda docs: [DbDoc(r) for r in docs],
            db_all_docs
        )

        transactions = []
        for (name, transaction_factory) in self.transaction_factories:
            transactions.append(transaction_factory(
                sync=True, total_expected=len(storage_all_docs)
            ))
        transactions.append(DocTrackerTransaction(self, self.sql))

        names = [t[0] for t in self.transaction_factories]
        names.append('doc_tracker')

        promises.append(sync.Syncer(
            self.core, names, storage_all_docs, db_docs, transactions
        ).get_promise())
