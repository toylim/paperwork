"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- sklearn pickling of TfidVectorizer
- sqlite database
"""
import collections
import logging
import sqlite3

import sklearn.feature_extraction.text
import sklearn.naive_bayes

import openpaperwork_core
import openpaperwork_core.promise

from .... import (_, sync)


# Beware that we use Sqlite, but sqlite python module is not thread-safe
# --> all the calls to sqlite module functions must happen on the main loop,
# even those in the transactions (which are run in a thread)


LOGGER = logging.getLogger(__name__)
ID = "label_guesser"
CREATE_TABLES = [
    # we could use the labels file instead, but some people access their work
    # directory through very slow Internet connections, so we better
    # keep a copy in the DB.
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
        self.cursor = self.core.call_one(
            "mainloop_execute", plugin.sql.cursor
        )
        self.core.call_one(
            "mainloop_execute", self.cursor.execute, "BEGIN TRANSACTION"
        )

        self.nb_changes = 0

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
            ID, _("Label guesser: added document %s") % doc_id
        )
        self._upd_obj(doc_id)
        self.nb_changes += 1
        super().add_obj(doc_id)

    def upd_obj(self, doc_id):
        self.notify_progress(
            ID, _("Label guesser: updated document %s") % doc_id
        )
        self._upd_obj(doc_id)
        self.nb_changes += 1
        super().upd_obj(doc_id)

    def _del_obj(self, doc_id):
        self.core.call_one(
            "mainloop_execute", self.cursor.execute,
            "DELETE FROM labels WHERE doc_id = ?", (doc_id,)
        )

    def del_obj(self, doc_id):
        self.notify_progress(
            ID,
            _("Label guesser: deleted document %s") % doc_id
        )
        self.nb_changes += 1
        self._del_obj(doc_id)
        super().del_obj(doc_id)

    def _upd_obj(self, doc_id):
        self._del_obj(doc_id)

        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        doc_labels = set()
        if doc_url is not None:
            self.core.call_all("doc_get_labels_by_url", doc_labels, doc_url)
        doc_labels = {label[0] for label in doc_labels}
        for doc_label in doc_labels:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute,
                "INSERT INTO labels (doc_id, label)"
                " VALUES (?, ?)",
                (doc_id, doc_label)
            )

    def cancel(self):
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            "on_label_guesser_canceled"
        )
        if self.cursor is not None:
            self.core.call_one(
                "mainloop_execute", self.cursor.execute, "ROLLBACK"
            )
            self.core.call_one("mainloop_execute", self.cursor.close)
            self.cursor = None
        self.notify_done(ID)

    def commit(self):
        LOGGER.info("Committing")
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
            ID, _("Commiting changes for label guessing ...")
        )
        self.core.call_one("mainloop_execute", self.cursor.execute, "COMMIT")

        if self.cursor is not None:
            self.core.call_one("mainloop_execute", self.cursor.close)
        self.cursor = None
        self.notify_done(ID)
        self.core.call_success(
            "mainloop_schedule", self.core.call_all,
            'on_label_guesser_commit_end'
        )
        LOGGER.info("Label guessing updated")


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        self.bayes_dir = None
        self.bayes = None
        self.sql = None

    def get_interfaces(self):
        return [
            'sync',
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

    def init(self, core):
        super().init(core)

        if self.bayes_dir is None:
            data_dir = self.core.call_success("paths_get_data_dir")
            self.bayes_dir = self.core.call_success(
                "fs_join", data_dir, "bayes"
            )

        self.core.call_all("fs_mkdir_p", self.bayes_dir)

        sql_file = self.core.call_success(
            "fs_join", self.bayes_dir, 'label_guesser.db'
        )
        self.sql = sqlite3.connect(
            self.core.call_success("fs_unsafe", sql_file),
            detect_types=sqlite3.PARSE_DECLTYPES
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

    def _load_classifiers(self):
        LOGGER.info("Training classifiers ...")
        msg = _("Label guessing: Training ...")

        label_cursor = self.core.call_one(
            "mainloop_execute", self.sql.cursor
        )

        try:
            self.core.call_all("on_progress", "classifiers", 0.0, msg)

            all_labels = self.core.call_one(
                "mainloop_execute", label_cursor.execute,
                "SELECT DISTINCT label FROM labels"
            )
            all_labels = self.core.call_one(
                "mainloop_execute",
                lambda all_labels: {l[0] for l in all_labels},
                all_labels
            )

            all_docs = self.core.call_success("doc_tracker_get_all_doc_ids")

            corpus = []
            targets = collections.defaultdict(list)
            for doc_id in all_docs:
                # prefer using the DB: it's faster for people using a remote
                # work directory
                doc_txt = self.core.call_success(
                    "doc_tracker_get_doc_text_by_id", doc_id
                )
                if doc_txt is None:
                    continue
                doc_txt = doc_txt.strip()
                if doc_txt == "":
                    continue
                corpus.append(doc_txt)

                doc_labels = self.core.call_one(
                    "mainloop_execute", label_cursor.execute,
                    "SELECT label FROM labels WHERE doc_id = ?",
                    (doc_id,)
                )
                doc_labels = self.core.call_one(
                    "mainloop_execute",
                    lambda r: {label for (label,) in r},
                    doc_labels
                )

                for label in all_labels:
                    present = label in doc_labels
                    targets[label].append(1 if present else 0)

            if len(corpus) <= 1:
                return (None, None)

            vectorizer = sklearn.feature_extraction.text.TfidfVectorizer(
                use_idf=False
            )
            corpus = vectorizer.fit_transform(corpus).toarray()
            classifiers = collections.defaultdict(
                sklearn.naive_bayes.GaussianNB
            )
            total = len(targets)
            for (idx, (label, label_targets)) in enumerate(targets.items()):
                if idx % 100 == 0:
                    self.core.call_all(
                        "on_progress", "classifiers", idx / total,
                        _("Label guessing: Training ...")
                    )
                classifiers[label].fit(
                    corpus, label_targets
                )

            return (vectorizer, classifiers)
        finally:
            self.core.call_all("on_progress", "classifiers", 1.0, msg)
            self.core.call_one("mainloop_execute", label_cursor.close)

    def _guess(self, vectorizer, classifiers, doc_url):
        LOGGER.info("Guessing labels on %s", doc_url)
        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt).strip()
        if doc_txt == u"":
            return

        vector = vectorizer.transform([doc_txt]).toarray()

        for (label, classifier) in classifiers.items():
            predicted = classifier.predict(vector)[0]
            if predicted:
                yield label

    def _set_guessed_labels(self, doc_url):
        has_labels = self.core.call_success("doc_has_labels_by_url", doc_url)
        if has_labels is not None:
            LOGGER.info(
                "Document %s already has labels. Won't guess labels", doc_url
            )
            return
        (vectorizer, classifiers) = self._load_classifiers()
        if vectorizer is None or classifiers is None:
            return
        labels = self._guess(vectorizer, classifiers, doc_url)
        labels = list(labels)
        for label in labels:
            self.core.call_success("doc_add_label_by_url", doc_url, label)

    def tests_cleanup(self):
        self.sql.close()
