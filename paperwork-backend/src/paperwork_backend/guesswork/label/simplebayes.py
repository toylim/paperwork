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
import datetime
import gettext
import hashlib
import logging
import os
import sqlite3
import time

import simplebayes

import openpaperwork_core
import openpaperwork_core.promise

from ... import sync
from ... import util


# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

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
    def __init__(self, plugin, guess_labels=False, total_expected=-1):
        self.plugin = plugin
        self.core = plugin.core
        self.guess_labels = guess_labels
        self.total_expected = total_expected

        # use a dedicated connection to ensure thread-safety regarding
        # SQL transactions
        self.cursor = self.core.call_success(
            "mainloop_execute", plugin.sql.cursor
        )
        self.core.call_one(
            "mainloop_execute", self.cursor.execute, "BEGIN TRANSACTION"
        )

        # Training bayesian filter is quite fast, but there is no
        # rollback command --> we track from what documents we have to train
        # and only train once `commit()` has been called.
        self.todo = []
        self.count = 0

        all_labels = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT DISTINCT label FROM labels"
        )
        self.all_labels = self.core.call_success(
            "mainloop_execute",
            lambda all_labels: {l[0] for l in all_labels},
            all_labels
        )

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def add_obj(self, doc_id):
        self.count += 1

        if self.guess_labels:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            # we have a higher priority than index plugins, so it is a good
            # time to update the document labels
            self.plugin._set_guessed_labels(doc_url)

        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "label_guesser_update", self._get_progression(),
            _("Updating label guesser with added document %s") % doc_id
        )
        self._upd_doc(doc_id)

    def del_obj(self, doc_id):
        self.count += 1

        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "label_guesser_update", self._get_progression(),
            _("Updating label guesser due to deleted document %s") % doc_id
        )
        self._upd_doc(doc_id)

    def upd_obj(self, doc_id):
        self.count += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "label_guesser_update", self._get_progression(),
            _("Updating label guesser with updated document %s") % doc_id
        )
        self._upd_doc(doc_id)

    def _check_label_exists_in_db(self, label):
        r = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT COUNT(label) FROM labels WHERE label = ? LIMIT 1",
            (label,)
        )
        r = self.core.call_success("mainloop_execute", next, r)[0]
        return r > 0

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

        doc_labels = set()
        self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
        doc_labels = {label[0] for label in doc_labels}

        return {
            'mtime': mtime,
            'text': doc_text,
            'labels': doc_labels,
        }

    def _get_db_doc_data(self, doc_id, doc_url):
        db_text = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT text FROM documents WHERE doc_id = ? LIMIT 1", (doc_id,)
        )
        db_text = self.core.call_success("mainloop_execute", list, db_text)
        if len(db_text) <= 0:
            db_text = None
        else:
            db_text = db_text[0]

        db_labels = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT label FROM labels WHERE doc_id = ?", (doc_id,)
        )
        db_labels = self.core.call_success("mainloop_execute", list, db_labels)
        db_labels = {l[0] for l in db_labels}

        return {
            'text': db_text,
            'labels': db_labels,
        }

    def _check_for_new_labels(self, doc_id, doc_url, actual, db):
        for doc_label in actual['labels']:
            if doc_label in db['labels']:
                continue
            LOGGER.info("Label '%s' added on document '%s'", doc_label, doc_id)
            # check if this label is a new one
            if not self._check_label_exists_in_db(doc_label):
                LOGGER.info(
                    "New label '%s' detected on document '%s'",
                    doc_label, doc_id
                )
                # we need to figure out the known documents at this very
                # moment to train first on those documents only.
                doc_ids = self.core.call_success(
                    "mainloop_execute", self.cursor.execute,
                    "SELECT doc_id FROM documents"
                )
                doc_ids = self.core.call_success(
                    "mainloop_execute", list, doc_ids
                )
                doc_ids = [d[0] for d in doc_ids]
                self.todo.append({
                    "action": "new",
                    "label": doc_label,
                    "doc_ids": doc_ids,
                })
            else:
                self.todo.append({
                    "action": "add",
                    "doc_id": doc_id,
                    "text": actual['text'],
                    "labels": [doc_label],
                })
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "INSERT OR REPLACE INTO labels (doc_id, label)"
                " VALUES (?, ?)",
                (doc_id, doc_label)
            )

    def _check_for_removed_labels(self, doc_id, doc_url, actual, db):
        for db_label in db['labels']:
            if db_label in actual['labels']:
                continue
            LOGGER.info(
                "Label '%s' removed from document '%s'", db_label, doc_id
            )
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "DELETE FROM labels WHERE doc_id = ? AND label = ?",
                (doc_id, db_label)
            )
            self.todo.append({
                "action": "remove",
                "doc_id": doc_id,
                "text": db['text'],
                "labels": [db_label],
            })

    def _upd_doc(self, doc_id):
        # collect data about the document from the document itself and from
        # the sqlite database and compare them
        # --> deduce the actions that must be done when running commit()

        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        actual = self._get_actual_doc_data(doc_id, doc_url)
        db = self._get_db_doc_data(doc_id, doc_url)

        if actual['text'] is not None:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "INSERT OR REPLACE INTO documents(doc_id, text, mtime)"
                " VALUES (?, ?, ?)",
                (doc_id, actual['text'], actual['mtime'])
            )

        self._check_for_new_labels(doc_id, doc_url, actual, db)
        self._check_for_removed_labels(doc_id, doc_url, actual, db)

        if actual['text'] is None:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "DELETE FROM documents WHERE doc_id = ?", (doc_id,)
            )

    def unchanged_obj(self, doc_id):
        self.count += 1
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "label_guesser_update", self._get_progression(),
            _("Document %s unchanged") % doc_id
        )

    def cancel(self):
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_label_guesser_canceled"
        )
        self.core.call_one("mainloop_execute", self.cursor.execute, "ROLLBACK")
        if self.cursor is not None:
            self.core.call_one("mainloop_execute", self.cursor.close)
        self.cursor = None

    def commit(self):
        self.core.call_all(
            "schedule", self.core.call_all,
            "on_label_guesser_commit_start"
        )

        all_labels = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT DISTINCT label FROM labels"
        )
        all_labels = self.core.call_success(
            "mainloop_execute",
            lambda all_labels: {l[0] for l in all_labels},
            all_labels
        )
        self.all_labels.update(all_labels)
        del all_labels

        for todo in self.todo:
            if todo['action'] != "new":
                continue
            LOGGER.info(
                "Training from all already-known docs for new label '%s'",
                todo['label']
            )
            baye = self.plugin._get_baye(todo['label'])

            for doc_id in todo['doc_ids']:
                text = self.core.call_success(
                    "mainloop_execute", self.cursor.execute,
                    "SELECT text FROM documents WHERE doc_id = ?",
                    (doc_id,)
                )
                text = self.core.call_success("mainloop_execute", list, text)
                if len(text) <= 0:
                    continue
                text = text[0]
                baye.train("no", text)

        for todo in self.todo:
            if todo['action'] != "remove":
                continue
            for label in self.all_labels:
                LOGGER.info(
                    "Untraining label '%s' from doc '%s'",
                    label, todo['doc_id']
                )
                baye = self.plugin._get_baye(label)
                baye.untrain(
                    "yes" if label in todo['labels'] else "no",
                    todo['text']
                )

        for todo in self.todo:
            if todo['action'] != "add":
                continue
            for label in self.all_labels:
                LOGGER.info(
                    "Training label '%s' from doc '%s'",
                    label, todo['doc_id']
                )
                baye = self.plugin._get_baye(label)
                baye.train(
                    "yes" if label in todo['labels'] else "no",
                    todo['text']
                )

        for label in self.all_labels:
            baye = self.plugin._get_baye(label)
            baye.cache_persist()

        self.core.call_one("mainloop_execute", self.cursor.execute, "COMMIT")

        for label in self.all_labels:
            if self._check_label_exists_in_db(label):
                continue
            LOGGER.warning(
                "Dropping baye training for label '%s'", label
            )
            self.plugin._delete_baye(label)

        if self.cursor is not None:
            self.core.call_one("mainloop_execute", self.cursor.close)
        self.cursor = None
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "label_guesser_update", 1.0
        )
        self.core.call_one(
            "schedule", self.core.call_all,
            'on_label_guesser_commit_end'
        )


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
        label_bytes = ("label_" + label_name).encode("utf-8")
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
            self.bayes_dir = os.path.join(data_dir, "paperwork", "bayes")

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

    def _delete_baye(self, label):
        if label in self.bayes:
            self.bayes.pop(label)
        baye_dir = self._get_baye_dir(label)
        util.rm_rf(baye_dir)

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
        has_labels = (
            self.core.call_success("doc_has_labels_by_url", doc_url)
            is not None
        )
        if has_labels:
            return
        labels = self._guess(doc_url)
        labels = list(labels)
        for label in labels:
            self.core.call_all("doc_add_label_by_url", doc_url, label)

    def doc_transaction_start(self, out: list, total_expected=-1):
        out.append(LabelGuesserTransaction(
            self, guess_labels=True, total_expected=total_expected
        ))

    def sync(self, promises: list):
        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        storage_all_docs.sort()
        storage_all_docs = [
            sync.StorageDoc(self.core, doc[0], doc[1])
            for doc in storage_all_docs
        ]

        bayes_all_docs = self.core.call_success(
            "mainloop_execute", self.sql.cursor
        )
        bayes_all_docs.execute("SELECT doc_id, mtime FROM documents")

        class BayesDoc(object):
            def __init__(self, result):
                self.key = result[0]
                self.extra = datetime.datetime.fromtimestamp(result[1])

        bayes_docs = self.core.call_success(
            "mainloop_execute",
            lambda docs: [BayesDoc(r) for r in docs],
            bayes_all_docs
        )

        transaction = LabelGuesserTransaction(
            self, guess_labels=False, total_expected=len(storage_all_docs)
        )

        promises.append(sync.Syncer(
            self.core, "label_guesser", storage_all_docs, bayes_docs,
            transaction
        ).get_promise())
