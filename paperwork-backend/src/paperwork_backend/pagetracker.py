"""
This plugin is an helper for other plugins. It provides an easy way
to track pages that have not yet being treated in each document.

For instance, when a document is notified as updated (see transactions), the
OCR plugin needs to know which pages of this document have already been
OCR-ed and which haven't.
"""
import functools
import logging
import os
import sqlite3

import openpaperwork_core


# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


LOGGER = logging.getLogger(__name__)

CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS pages ("
        " doc_id TEXT NOT NULL,"
        " page INTEGER NOT NULL,"
        " hash TEXT NOT NULL,"
        " PRIMARY KEY (doc_id, page)"
        ")"
    ),
]


class PageTracker(object):
    def __init__(self, core, sql_file):
        self.core = core
        self.sql = self.core.call_success(
            "mainloop_execute", sqlite3.connect, sql_file
        )
        for query in CREATE_TABLES:
            self.core.call_success("mainloop_execute", self.sql.execute, query)
        self.core.call_success(
            "mainloop_execute", self.sql.execute, "BEGIN TRANSACTION"
        )

    def _close(self):
        self.core.call_success("mainloop_execute", self.sql.close)

    def cancel(self):
        self.core.call_success(
            "mainloop_execute", self.sql.execute, "ROLLBACK"
        )
        self._close()

    def commit(self):
        self.core.call_success("mainloop_execute", self.sql.execute, "COMMIT")
        self._close()

    def find_changes(self, doc_id, doc_url):
        """
        Examine a document. Return page that haven't been handled yet
        or that have been modified since.
        Don't forget to call ack_page() once you've handled each page.
        """

        out = []

        db_pages = self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "SELECT page, hash FROM pages"
            " WHERE doc_id = ?",
            (doc_id,)
        )
        db_pages = self.core.call_success(
            "mainloop_execute",
            lambda pages: {r[0]: int(r[1], 16) for r in pages}, db_pages
        )
        db_hashes = set(db_pages.values())

        fs_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", doc_url
        )
        fs_pages = {}
        for page_idx in range(0, fs_nb_pages):
            h = []
            self.core.call_success(
                "page_get_hash_by_url", h, doc_url, page_idx
            )
            fs_pages[page_idx] = functools.reduce(lambda x, y: x ^ y, h)

        for (page_idx, fs_page_hash) in fs_pages.items():
            if page_idx not in db_pages:
                out.append(('new', page_idx))
            else:
                db_page_hash = db_pages.pop(page_idx)
                if db_page_hash != fs_page_hash:
                    if fs_page_hash in db_hashes:
                        # this page existed before
                        out.append(('moved', page_idx))
                    else:
                        out.append(('upd', page_idx))

        for (db_page_idx, h) in db_pages.items():
            self.core.call_success(
                "mainloop_execute", self.sql.execute,
                "DELETE FROM pages"
                " WHERE doc_id = ? AND page = ?",
                (doc_id, db_page_idx)
            )

        return out

    def ack_page(self, doc_id, doc_url, page_idx):
        """
        Mark the page update has handled.
        """
        page_hash = []
        self.core.call_success(
            "page_get_hash_by_url", page_hash, doc_url, page_idx
        )
        page_hash = functools.reduce(lambda x, y: x ^ y, page_hash)
        self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "INSERT OR REPLACE"
            " INTO pages (doc_id, page, hash)"
            " VALUES (?, ?, ?)",
            (doc_id, page_idx, format(page_hash, 'x'))
        )

    def delete_doc(self, doc_id):
        self.core.call_success(
            "mainloop_execute", self.sql.execute,
            "DELETE FROM pages WHERE doc_id = ?",
            (doc_id,)
        )


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.local_dir = os.path.expanduser("~/.local")
        self.paperwork_dir = None
        self.sql_file = None

    def get_interfaces(self):
        return ['page_tracking']

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['paperwork_backend.fs.gio']
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_core.mainloop_asyncio'],
            },
            {
                'interface': 'page_boxes',
                'defaults': ['paperwork_backend.model.hocr'],
            },
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
        ]

    def init(self, core):
        super().init(core)

        if self.paperwork_dir is None:
            data_dir = os.getenv(
                "XDG_DATA_HOME", os.path.join(self.local_dir, "share")
            )
            self.paperwork_dir = os.path.join(data_dir, "paperwork")

        os.makedirs(self.paperwork_dir, mode=0o700, exist_ok=True)
        if os.name == 'nt':  # hide ~/.local on Windows
            local_dir_url = self.core.call_success("fs_safe", self.local_dir)
            self.core.call_all("fs_hide", local_dir_url)

        self.sql_file = os.path.join(self.paperwork_dir, 'page_tracking_{}.db')

    def page_tracker_get(self, tracking_id):
        sql_file = self.sql_file.format(tracking_id)
        return PageTracker(self.core, sql_file)
