"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- simplebayes caches
- sqlite database

Simplebayes caches store the training of bayes filters.
The sqlite database allows the plugin to keep track of which documents have
been used for training and which haven't and which labels were already
on which documents. It also keeps a copy of document texts. This copy is
used when a document is removed so the bayes filter can be untrained.
"""

import base64
import hashlib
import logging
import sqlite3

import simplebayes

import openpaperwork_core
import openpaperwork_core.promise

from ... import (_, sync, util)


# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


LOGGER = logging.getLogger(__name__)
ID = "label_guesser"
CREATE_TABLES = [
    (
        "CREATE TABLE IF NOT EXISTS labels ("
        " doc_id TEXT NOT NULL,"
        " label TEXT NOT NULL,"
        " PRIMARY KEY (doc_id, label)"
        ")"
    ),
]


class LabelGuesserTransaction(sync.BaseTransaction):
    def __init__(self, plugin, guess_labels=False, total_expected=-1):
        super().__init__(plugin.core, total_expected)
        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.guess_labels = guess_labels
        LOGGER.info("Transaction start: Guessing labels: %s", guess_labels)

        # use a dedicated connection to ensure thread-safety regarding
        # SQL transactions
        self.cursor = self.core.call_success(
            "mainloop_execute", plugin.sql.cursor
        )
        self.core.call_one(
            "mainloop_execute", self.cursor.execute, "BEGIN TRANSACTION"
        )

        self.nb_changes = 0

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

    def add_obj(self, doc_id):
        if self.guess_labels:
            doc_url = self.core.call_success("doc_id_to_url", doc_id)
            # we have a higher priority than index plugins, so it is a good
            # time to update the document labels
            self.plugin._set_guessed_labels(doc_url)

        self.notify_progress(
            ID, _("Training label guesser with added document %s") % doc_id
        )
        self._upd_doc(doc_id)
        super().add_obj(doc_id)

    def del_obj(self, doc_id):
        self.notify_progress(
            ID,
            _("Untraining label guesser due to deleted document %s") % doc_id
        )
        self._upd_doc(doc_id)
        super().del_obj(doc_id)

    def upd_obj(self, doc_id):
        self.notify_progress(
            ID, _("Training label guesser with updated document %s") % doc_id
        )
        self._upd_doc(doc_id)
        super().upd_obj(doc_id)

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
            doc_text = []
            self.core.call_all("doc_get_text_by_url", doc_text, doc_url)
            doc_text = "\n\n".join(doc_text)
        else:
            doc_text = None

        doc_labels = set()
        if doc_url is not None:
            self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
        doc_labels = {label[0] for label in doc_labels}

        return {
            'text': doc_text,
            'labels': doc_labels,
        }

    def _get_db_doc_data(self, doc_id, doc_url):
        db_text = self.core.call_success(
            "doc_tracker_get_doc_text_by_id", doc_id
        )

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

    def _check_for_new_labels(self, todo, doc_id, doc_url, actual, db):
        for doc_label in actual['labels']:
            if doc_label in db['labels']:
                continue
            LOGGER.debug(
                "Label '%s' added on document '%s'", doc_label, doc_id
            )
            # check if this label is a new one
            if not self._check_label_exists_in_db(doc_label):
                LOGGER.info(
                    "New label '%s' detected on document '%s'",
                    doc_label, doc_id
                )
                # we need to figure out the known documents at this very
                # moment to train first on those documents only.
                doc_ids = self.core.call_success("doc_tracker_get_all_doc_ids")
                todo.append({
                    "action": "new",
                    "label": doc_label,
                    "doc_ids": doc_ids,
                })
                self.all_labels.add(doc_label)
            else:
                todo.append({
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

    def _check_for_removed_labels(self, todo, doc_id, doc_url, actual, db):
        for db_label in db['labels']:
            if db_label in actual['labels']:
                continue
            LOGGER.debug(
                "Label '%s' removed from document '%s'", db_label, doc_id
            )
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "DELETE FROM labels WHERE doc_id = ? AND label = ?",
                (doc_id, db_label)
            )
            todo.append({
                "action": "remove",
                "doc_id": doc_id,
                "text": db['text'],
                "labels": [db_label],
            })

    def _get_all_labels_from_db(self):
        all_labels = self.core.call_success(
            "mainloop_execute", self.cursor.execute,
            "SELECT DISTINCT label FROM labels"
        )
        all_labels = self.core.call_success(
            "mainloop_execute",
            lambda all_labels: {l[0] for l in all_labels},
            all_labels
        )
        return all_labels

    def _apply_changes(self, todos):
        if len(todos) <= 0:
            return

        for todo in todos:
            if todo['action'] != "new":
                continue
            LOGGER.debug(
                "Training from all already-known docs for new label '%s'",
                todo['label']
            )
            self.notify_progress(
                ID, _(
                    "Training label guessing training for label '{}'"
                    " with all known documents ..."
                ).format(todo['label'])
            )
            baye = self.plugin._get_baye(todo['label'])

            for doc_id in todo['doc_ids']:
                text = self.core.call_success(
                    "doc_tracker_get_doc_text_by_id", doc_id
                )
                if text is None or len(text) <= 0:
                    continue
                baye.train("no", text)

        for todo in todos:
            if todo['action'] != "remove":
                continue
            for label in self.all_labels:
                LOGGER.debug(
                    "Untraining label '%s' from doc '%s'",
                    label, todo['doc_id']
                )
                baye = self.plugin._get_baye(label)
                baye.untrain(
                    "yes" if label in todo['labels'] else "no",
                    todo['text']
                )

        for todo in todos:
            if todo['action'] != "add":
                continue
            for label in self.all_labels:
                LOGGER.debug(
                    "Training label '%s' from doc '%s'",
                    label, todo['doc_id']
                )
                baye = self.plugin._get_baye(label)
                baye.train(
                    "yes" if label in todo['labels'] else "no",
                    todo['text']
                )

    def _upd_doc(self, doc_id):
        # collect data about the document from the document itself and from
        # the sqlite database and compare them
        # --> deduce the actions that must be done when running commit()
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        actual = self._get_actual_doc_data(doc_id, doc_url)
        db = self._get_db_doc_data(doc_id, doc_url)

        todos = []
        self._check_for_new_labels(todos, doc_id, doc_url, actual, db)
        self._check_for_removed_labels(todos, doc_id, doc_url, actual, db)
        self._apply_changes(todos)
        self.nb_changes += len(todos)

    def cancel(self):
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_label_guesser_canceled"
        )
        for label in self.all_labels:
            self.plugin._get_baye(label, force_reload=True)
        if self.cursor is not None:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute, "ROLLBACK"
            )
            self.core.call_one("mainloop_execute", self.cursor.close)
            self.cursor = None
        self.notify_done(ID)

    def commit(self):
        LOGGER.info("Updating training ...")
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_label_guesser_commit_start"
        )
        if self.nb_changes <= 0:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute, "ROLLBACK"
            )
            self.core.call_one("mainloop_execute", self.cursor.close)
            self.cursor = None
            self.notify_done(ID)
            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                'on_label_guesser_commit_end'
            )
            LOGGER.info("Nothing to do. Training left unchanged.")
            return

        self.notify_progress(
            ID, _("Training label guessing ...")
        )

        for label in self.all_labels:
            baye = self.plugin._get_baye(label)
            baye.cache_persist()

        self.core.call_one("mainloop_execute", self.cursor.execute, "COMMIT")

        for label in self.all_labels:
            if self._check_label_exists_in_db(label):
                continue
            LOGGER.warning("Dropping baye training for label '%s'", label)
            self.plugin._delete_baye(label)

        if self.cursor is not None:
            self.core.call_one("mainloop_execute", self.cursor.close)
        self.cursor = None
        self.notify_done(ID)
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            'on_label_guesser_commit_end'
        )
        LOGGER.info("Training updated")


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    # XXX(Jflesch):
    # Threshold found after many many many many tests. Works with my documents.
    # I can only hope it will work as nicely for other people.
    THRESHOLD_YES_NO_RATIO = 0.195

    def __init__(self):
        self.bayes_dir = None
        self.bayes = None
        self.sql = None

    def get_interfaces(self):
        return [
            'sync',  # actually implemented by doctracker
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker'],
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
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'paths',
                'defaults': ['openpaperwork_core.paths.xdg'],
            },
        ]

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
        return self.core.call_success("fs_join", self.bayes_dir, label_hash)

    def init(self, core):
        super().init(core)

        if self.bayes_dir is None:
            data_dir = self.core.call_success("paths_get_data_dir")
            self.bayes_dir = self.core.call_success(
                "fs_join", data_dir, "bayes"
            )

        self.core.call_all("fs_mkdir_p", self.bayes_dir)

        sql_file = self.core.call_success(
            "fs_join", self.bayes_dir, 'labels.db'
        )
        self.sql = sqlite3.connect(
            self.core.call_success("fs_unsafe", sql_file)
        )
        for query in CREATE_TABLES:
            self.sql.execute(query)

        self.core.call_all(
            "doc_tracker_register",
            "label_guesser",
            lambda sync, total_expected: LabelGuesserTransaction(
                self, guess_labels=not sync, total_expected=total_expected
            )
        )

    def _load_all_bayes(self):
        self.bayes = {}
        labels = self.core.call_success(
            "mainloop_execute",
            self.sql.execute, "SELECT DISTINCT label FROM labels"
        )
        labels = self.core.call_success(
            "mainloop_execute",
            lambda labels: [l[0] for l in labels],
            labels
        )
        for label in labels:
            self._get_baye(label)

    def _get_baye(self, label, force_reload=False):
        if self.bayes is None:
            self._load_all_bayes()

        if label in self.bayes and not force_reload:
            return self.bayes[label]

        LOGGER.info("Loading training for label '%s'", label)
        baye_dir = self._get_baye_dir(label)
        self.core.call_all("fs_mkdir_p", baye_dir)
        self.bayes[label] = simplebayes.SimpleBayes(
            cache_path=self.core.call_success("fs_unsafe", baye_dir)
        )
        self.bayes[label].cache_train()
        return self.bayes[label]

    def _delete_baye(self, label):
        if label in self.bayes:
            self.bayes.pop(label)
        baye_dir = self._get_baye_dir(label)
        util.rm_rf(baye_dir)

    def _score(self, doc_url):
        LOGGER.info("Guessing labels on %s", doc_url)
        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt)
        if doc_txt == u"":
            return
        if self.bayes is None:
            self._load_all_bayes()
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
        has_labels = self.core.call_success("doc_has_labels_by_url", doc_url)
        if has_labels is not None:
            LOGGER.info(
                "Document %s already has labels. Won't guess labels", doc_url
            )
            return
        labels = self._guess(doc_url)
        labels = list(labels)
        for label in labels:
            self.core.call_success("doc_add_label_by_url", doc_url, label)

    def tests_cleanup(self):
        self.sql.close()
