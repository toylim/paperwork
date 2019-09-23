"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- simplebayes caches
- sqlite database

Simplebayes caches store the training of bayes filters.
The sqlite database allows the plugin to keep track of which documents have
been used for training and which haven't. It also keeps a copy of document
texts. This copy is used when a document is removed so the bayes filter
can be untrained.
"""

import base64
import hashlib
import logging
import os
import sqlite3
import time

import simplebayes

import openpaperwork_core
import openpaperwork_core.promise

from .. import sync


LOGGER = logging.getLogger(__name__)

CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS documents ("
        " doc_id TEXT PRIMARY KEY,"
        " text TEXT NOT NULL,"
        " mtime INTEGER NOT NULL"
        ")"
    ),
    (
        "CREATE TABLE IF NOT EXISTS labels ("
        " doc_id TEXT NOT NULL,"
        " label TEXT NOT NULL,"
        " PRIMARY KEY (doc_id, label),"
        " FOREIGN KEY (doc_id)"
        "   REFERENCES documents (doc_id)"
        "   ON DELETE CASCADE"
        "   ON UPDATE CASCADE"
        ")"
    ),
]


class LabelGuesserTransaction(object):
    def __init__(self, plugin, guess_labels=False):
        self.plugin = plugin
        self.core = plugin.core
        self.guess_labels = guess_labels

        # use a dedicated connection to ensure thread-safety regarding
        # SQL transactions
        self.sql = plugin.sql.cursor()

        # Training bayesian filter is quite fast, but there is no
        # rollback command --> we track from what documents we have to train
        # and only train once `commit()` has been called.
        self.todo = []

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def add_obj(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        if self.guess_labels:
            # we have a higher priority than index plugins, so it is a good
            # time to update the document labels
            self.plugin._set_guessed_labels(doc_url)

        mtime = []
        self.core.call_all("doc_get_mtime_by_url", mtime, doc_url)
        mtime = max(mtime)

        text = []
        self.core.call_all("doc_get_text_by_url", text, doc_url)
        text = "\n\n".join(text)

        labels = set()
        self.core.call_all("doc_get_labels_by_url", labels, doc_url)
        labels = [label[0] for label in labels]

        LOGGER.info("Will train label '%s' from doc '%s'", labels, doc_id)
        self.todo.append({
            "action": "add",
            "doc_id": doc_id,
            "text": text,
            "labels": labels,
            "mtime": mtime
        })

    def del_obj(self, doc_id):
        text = self.sql.execute(
            "SELECT text FROM documents WHERE doc_id = ? LIMIT 1", (doc_id,)
        )
        text = next(text)[0]

        labels = self.sql.execute(
            "SELECT label FROM labels WHERE doc_id = ?", (doc_id,)
        )
        labels= [l[0] for l in labels]

        LOGGER.info("Will untrain label '%s' from doc '%s'", labels, doc_id)
        self.todo.append({
            "action": "del",
            "doc_id": doc_id,
            "text": text,
            "labels": labels,
        })

    def upd_obj(self, doc_id):
        self.del_obj(doc_id)
        self.add_obj(doc_id)

    def cancel(self):
        self.sql = None

    def commit(self):
        all_labels = set()
        self.core.call_all("labels_get_all", all_labels)
        all_labels = [l[0] for l in all_labels]

        self.sql.execute("BEGIN TRANSACTION")
        for todo in self.todo:
            if todo['action'] == "add":
                for label in all_labels:
                    LOGGER.info(
                        "Training label '%s' from doc '%s'",
                        label, todo['doc_id']
                    )
                    baye = self.plugin._get_baye(label)
                    baye.train(
                        "yes" if label in todo['labels'] else "no",
                        todo['text']
                    )
                self.sql.execute(
                    "INSERT INTO documents(doc_id, text, mtime)"
                    " VALUES (?, ?, ?)",
                    (todo['doc_id'], todo['text'], todo['mtime'])
                )
                self.sql.executemany(
                    "INSERT INTO labels (doc_id, label) VALUES (?, ?)",
                    ((todo['doc_id'], label) for label in todo['labels'])
                )
            elif todo['action'] == "del":
                for label in all_labels:
                    LOGGER.info(
                        "Untraining label '%s' from doc '%s'",
                        label, todo['doc_id']
                    )
                    baye = self.plugin._get_baye(label)
                    baye.untrain(
                        "yes" if label in todo['labels'] else "no",
                        todo['text']
                    )
                # thanks to 'ON DELETE CASCADE', only SQL query is required
                self.sql.execute(
                    "DELETE FROM documents WHERE doc_id = ?",
                    (todo['doc_id'],)
                )

        for label in all_labels:
            baye = self.plugin._get_baye(label)
            baye.cache_persist()
        self.sql.execute("COMMIT")
        self.sql = None
        self.core.call_all('on_label_guesser_updated')


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    # XXX(Jflesch):
    # Threshold found after many many many many tests. Works with my documents.
    # I can only hope it will work as nicely for other people.
    THRESHOLD_YES_NO_RATIO = 0.195

    def __init__(self):
        self.local_dir = os.path.expanduser("~/.local")
        self.bayes_dir = None
        self.bayes = {}
        self.sql = None
        self.sql_file = None

    def get_interfaces(self):
        return [
            "doc_autocompleter",
            "syncable",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_labels', ['paperwork_backend.model.labels',]),
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('fs', ['paperwork_backend.fs.gio',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
            ]
        }

    def _get_baye_dir(self, label_name):
        """
        Label names may contain weird or forbidden characters ('/' for
        instance). --> we use the hash of the label name instead of the label
        name.
        """
        label_bytes = label_name.encode("utf-8")
        label_hash = hashlib.sha1(label_bytes).digest()
        label_hash = base64.encodebytes(label_hash).decode('utf-8').strip()
        label_hash = label_hash.replace('/', '_')
        return os.path.join(self.bayes_dir, label_hash)

    def init(self, core):
        super().init(core)

        if self.bayes_dir is None:
            data_dir = os.getenv(
                "XDG_DATA_HOME", os.path.join(self.local_dir, "share")
            )
            self.bayes_dir = os.path.join(data_dir, "paperwork", "index")

        os.makedirs(self.bayes_dir, mode=0o700, exist_ok=True)
        if os.name == 'nt':  # hide ~/.local on Windows
            local_dir_url = self.core.call_success("fs_safe", self.local_dir)
            self.core.call_all("fs_hide", local_dir_url)

        self.sql_file = os.path.join(self.bayes_dir, 'labels.db')
        self.sql = sqlite3.connect(self.sql_file)
        for query in CREATE_TABLES:
            self.sql.execute(query)

        labels = self.sql.execute("SELECT DISTINCT label FROM labels")
        for label in labels:
            label = label[0]
            LOGGER.info("Loading training for label '%s'", label)
            self._get_baye(label)

    def _get_baye(self, label):
        if label in self.bayes:
            return self.bayes[label]

        baye_dir = self._get_baye_dir(label)
        os.makedirs(baye_dir, mode=0o700, exist_ok=True)
        self.bayes[label] = simplebayes.SimpleBayes(cache_path=baye_dir)
        self.bayes[label].cache_train()
        return self.bayes[label]

    def _score(self, doc_url):
        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt)
        if doc_txt == u"":
            return
        for (label_name, guesser) in self.bayes.items():
            scores = guesser.score(doc_txt)
            yes = scores['yes'] if 'yes' in scores else 0.0
            no = scores['no'] if 'no' in scores else 0.0
            LOGGER.info("Score for %s: Yes: %f", label_name, yes)
            LOGGER.info("Score for %s: No: %f", label_name, no)
            yield (label_name, {"yes": yes, "no": no})

    def _guess(self, doc_url):
        for (label_name, scores) in self._score(doc_url):
            yes = scores['yes']
            no = scores['no']
            total = yes + no
            if total == 0:
                continue
            if (yes / total) > self.THRESHOLD_YES_NO_RATIO:
                yield label_name

    def _set_guessed_labels(self, doc_url):
        labels = self._guess(doc_url)
        labels = list(labels)
        for label in labels:
            self.core.call_all("doc_add_label", doc_url, label)

    def doc_transaction_start(self, out: list, total_expected=-1):
        out.append(LabelGuesserTransaction(self, guess_labels=True))

    def sync(self, promises: list):
        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        storage_all_docs = [
            sync.StorageDoc(self.core, doc[0], doc[1])
            for doc in storage_all_docs
        ]

        bayes_all_docs = self.sql.cursor()
        bayes_all_docs.execute("SELECT doc_id, mtime FROM documents")

        class BayesDoc(object):
            def __init__(self, result):
                self.key = result[0]
                self.extra = result[1]

        bayes_docs = (BayesDoc(r) for r in bayes_all_docs)

        transaction = LabelGuesserTransaction(self, guess_labels=False)

        promises.append(sync.Syncer(
            self.core, storage_all_docs, bayes_docs, transaction
        ).get_promise())
