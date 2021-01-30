"""
Label guesser guesses label based on document text and bayes filters.
It adds the guessed labels on new documents (in other words, freshly
added documents).

It stores data in 2 ways:
- sklearn pickling of TfidVectorizer
- sqlite database
"""
import collections
import gc
import logging
import os
import sqlite3
import time

import numpy
import scipy.sparse
import sklearn.feature_extraction.text
import sklearn.naive_bayes

import openpaperwork_core
import openpaperwork_core.promise

from .... import (_, sync)


# Limit the number of words used for performance reasons
MAX_WORDS = os.getenv("PAPERWORK_LABEL_GUESSING_MAX_WORDS", 15000)
# Limit the number of documents used for performance reasons
MAX_DOC_BACKLOG = os.getenv("PAPERWORK_LABEL_GUESSING_MAX_BACKLOG", 100)

BATCH_SIZE = os.getenv("PAPERWORK_LABEL_GUESSING_BATCH_SIZE", 200)


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
    (  # see sklearn.feature_extraction.text.CountVectorizer.vocabulary_
        "CREATE TABLE IF NOT EXISTS vocabulary ("
        " word TEXT NOT NULL,"
        " feature INTEGER NOT NULL,"
        " PRIMARY KEY (feature)"
        " UNIQUE (word)"
        ")"
    ),
    (
        "CREATE TABLE IF NOT EXISTS features ("
        " doc_id TEXT NOT NULL,"
        " vector NUMPY_ARRAY NOT NULL,"
        " PRIMARY KEY (doc_id)"
        ")"
    )
]


class SqliteNumpyArrayHandler(object):
    @staticmethod
    def _to_sqlite(np_array):
        return np_array.tobytes()

    @staticmethod
    def _from_sqlite(raw):
        return numpy.frombuffer(raw)

    @classmethod
    def register(cls):
        sqlite3.register_adapter(numpy.array, cls._to_sqlite)
        sqlite3.register_converter("NUMPY_ARRAY", cls._from_sqlite)


class UpdatableVectorizer(object):
    """
    Vectorizer that we can update over time with new features
    (word identifiers). Store the word->features in the SQLite database.
    We only add words to the database, we never remove them, otherwise we
    wouldn't be able to read the feature vectors correctly anymore.

    No need to take deleted documents into account. Worst case scenario is
    that we will end up with a lot of useless words in the vocabulary.
    """
    def __init__(self, core, db_cursor):
        self.core = core
        self.db_cursor = db_cursor

        vocabulary = self.core.call_one(
            "mainloop_execute", self.db_cursor.execute,
            "SELECT word, feature FROM vocabulary"
        )
        vocabulary = self.core.call_one(
            "mainloop_execute",
            lambda r: {k: v for (k, v) in r},
            vocabulary
        )
        self.updatable_vocabulary = vocabulary
        self.last_feature_id = max(vocabulary.values(), default=-1)

    def partial_fit_transform(self, corpus):
        # A bit hackish: We just need the analyzer, so instantiating a full
        # TfidVectorizer() is probably overkill, but meh.
        tokenizer = sklearn.feature_extraction.text.TfidfVectorizer(
        ).build_analyzer()
        for doc_txt in corpus:
            for word in tokenizer(doc_txt):
                if word in self.updatable_vocabulary:
                    continue
                self.last_feature_id += 1
                self.core.call_one(
                    "mainloop_execute", self.db_cursor.execute,
                    "INSERT INTO vocabulary (word, feature)"
                    " SELECT ?, ?"
                    "  WHERE NOT EXISTS("
                    "   SELECT 1 FROM vocabulary WHERE word = ?"
                    "  )",
                    (word, self.last_feature_id, word)
                )
                self.updatable_vocabulary[word] = self.last_feature_id

        return self.transform(corpus)

    def transform(self, corpus):
        # IMPORTANT: we must use use_idf=False here because we want the values
        # in each feature vector to be independant from other vectors.
        vectorizer = sklearn.feature_extraction.text.TfidfVectorizer(
            use_idf=False, vocabulary=self.updatable_vocabulary
        )
        return vectorizer.fit_transform(corpus)

    def copy(self):
        r = UpdatableVectorizer(self.core, self.db_cursor)
        r.updatable_vocabulary = dict(self.updatable_vocabulary)
        r.last_feature_id = self.last_feature_id
        return r


class BatchIterator(object):
    def __init__(self, features, targets):
        self.features = features
        self.targets = targets
        self.b = 0

    def __iter__(self):
        self.b = 0
        return self

    def __next__(self):
        batch_corpus = self.features[self.b:self.b + BATCH_SIZE]
        if len(batch_corpus) <= 0:
            raise StopIteration()
        batch_corpus = scipy.sparse.vstack(batch_corpus).toarray()
        batch_targets = self.targets[self.b:self.b + BATCH_SIZE]
        self.b += BATCH_SIZE
        return (batch_corpus, batch_targets)


class WordReductor(object):
    def __init__(self, to_drop):
        self.features_to_drop = to_drop

    def reduce_features(self, features):
        return numpy.delete(features, self.features_to_drop)


class DummyWordReductor(object):
    def reduce_features(self, features):
        return features


class Corpus(object):
    """
    Handles doc_ids and their associate feature vectors.
    Make sure we train the document in the best order possible, so even
    if the training is interrupted (time limit), we still have some training
    for most labels.
    """
    def __init__(self, doc_ids, features, targets):
        self.doc_ids = doc_ids
        self.features = features
        self.targets = targets

    def standardize_feature_vectors(self, vectorizer):
        for idx in range(0, len(self.features)):
            doc_vector = self.features[idx]
            required_padding = (
                vectorizer.last_feature_id + 1 - doc_vector.shape[0]
            )
            assert(required_padding >= 0)
            if required_padding > 0:
                doc_vector = scipy.sparse.hstack([
                    doc_vector, numpy.zeros((required_padding,))
                ])
            else:
                doc_vector = scipy.sparse.csr_matrix(doc_vector)
            self.features[idx] = doc_vector

    def reduce_corpus_words(self):
        """
        We may end up with a lot of different words (about 76000 in my case).
        But most of them are actually too rare to be useful and they use
        a lot memory and CPU time.
        """
        word_freq_sums = sum(self.features).toarray()[0]
        word_count = word_freq_sums.shape[0]
        LOGGER.info("Total word count before reduction: %d", word_count)
        if word_count <= MAX_WORDS:
            LOGGER.info("No reduction to do")
            return DummyWordReductor()

        threshold = sorted(word_freq_sums, reverse=True)[MAX_WORDS]
        LOGGER.info("Word frequency threshold: %f", threshold)

        features_to_drop = []
        for (idx, freq) in enumerate(word_freq_sums):
            if freq > threshold:
                continue
            features_to_drop.append(idx)

        reductor = WordReductor(features_to_drop)

        for idx in range(0, len(self.features)):
            self.features[idx] = scipy.sparse.csr_matrix(
                reductor.reduce_features(
                    self.features[idx].toarray()[0]
                )
            )

        LOGGER.info(
            "Total word count after reduction: %d",
            word_count - len(reductor.features_to_drop)
        )
        return reductor

    def get_doc_count(self):
        return len(self.features)

    def get_labels(self):
        return self.targets.keys()

    def get_batches(self, label):
        return BatchIterator(self.features, self.targets[label])

    @staticmethod
    def _add_doc_ids(doc_weights, doc_ids):
        # Assumes doc_ids are in reverse order (most recent first)
        # Also assumes most recent documents are the most useful
        assert(len(doc_ids) <= MAX_DOC_BACKLOG)
        weigth = MAX_DOC_BACKLOG + 1
        for doc_id in doc_ids:
            doc_weights[doc_id] += weigth
            weigth -= 1

    @staticmethod
    def load(cursor):
        start = time.time()

        # doc_id --> weigth
        doc_weights = collections.defaultdict(lambda: 0)

        all_labels = cursor.execute("SELECT DISTINCT label FROM labels")
        all_labels = {l[0] for l in all_labels}
        all_docs = cursor.execute(
            "SELECT doc_id FROM features ORDER BY doc_id DESC"
        )
        all_docs = [l[0] for l in all_docs]

        for label in all_labels:
            ds = cursor.execute(
                "SELECT doc_id FROM labels WHERE label = ?"
                " ORDER BY doc_id DESC LIMIT {}".format(
                    MAX_DOC_BACKLOG
                ),
                (label,)
            )
            Corpus._add_doc_ids(doc_weights, [d[0] for d in ds])

        # label --> number of doc without this label
        no_label_counts = {l: 0 for l in all_labels}
        no_label_docids = {l: [] for l in all_labels}
        for doc_id in all_docs:
            if len(no_label_counts) <= 0:
                break
            doc_labels = cursor.execute(
                "SELECT label FROM labels WHERE doc_id = ?", (doc_id,)
            )
            for label in list(no_label_counts.keys()):
                if label in doc_labels:
                    continue
                no_label_docids[label].append(doc_id)
                no_label_counts[label] += 1
                if no_label_counts[label] >= MAX_DOC_BACKLOG:
                    no_label_counts.pop(label)
        for doc_ids in no_label_docids.values():
            doc_ids.sort(reverse=True)
            Corpus._add_doc_ids(doc_weights, doc_ids)

        LOGGER.info(
            "Loading features of %d documents for %d labels",
            len(doc_ids), len(all_labels)
        )

        all_features = {}
        for doc_id in doc_weights.keys():
            vectors = cursor.execute(
                "SELECT vector FROM features WHERE doc_id = ? LIMIT 1",
                (doc_id,)
            )
            for vector in vectors:
                all_features[doc_id] = vector[0]

        all_features = [
            [weight, doc_id, all_features[doc_id]]
            for (doc_id, weight) in doc_weights.items()
        ]
        all_features.sort(reverse=True)
        doc_ids = [
            doc_id
            for (weight, doc_id, features) in all_features
        ]
        features = [
            features
            for (weight, doc_id, features) in all_features
        ]

        # Load labels
        targets = collections.defaultdict(list)
        for (idx, doc_id) in enumerate(doc_ids):
            doc_labels = cursor.execute(
                "SELECT label FROM labels WHERE doc_id = ?",
                (doc_id,)
            )
            doc_labels = [label[0] for label in doc_labels]
            for label in all_labels:
                present = label in doc_labels
                targets[label].append(1 if present else 0)

        corpus = Corpus(
            doc_ids=doc_ids,
            features=features,
            targets=targets
        )

        stop = time.time()

        LOGGER.info(
            "Took %dms to load features of %d documents",
            int((stop - start) * 1000), len(doc_ids)
        )

        return corpus


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

        self.vectorizer = UpdatableVectorizer(self.core, self.cursor)

        # If we load the classifiers, we keep the vectorizer that goes with
        # them, because the vectorizer must return vectors that have the size
        # that the classifiers expect. If we would train the vectorizer with
        # new documents, the vector sizes could increase
        # Since loading the classifiers is a fairly long operations, we only
        # do it when we actually need them.
        self.original_vectorizer = None
        self.reductor = None
        self.classifiers = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def add_obj(self, doc_id):
        if self.guess_labels:
            # we have a higher priority than index plugins, so it is a good
            # time to update the document labels

            doc_url = self.core.call_success("doc_id_to_url", doc_id)

            has_labels = self.core.call_success(
                "doc_has_labels_by_url", doc_url
            )
            if has_labels is not None:
                LOGGER.info(
                    "Document %s already has labels. Won't guess labels",
                    doc_url
                )
                return

            if self.classifiers is None:
                self.original_vectorizer = self.vectorizer.copy()
                (self.word_reductor, self.classifiers) = \
                    self.plugin._load_classifiers(
                        self.original_vectorizer
                    )

            self.plugin._set_guessed_labels(
                doc_url, self.original_vectorizer,
                self.word_reductor, self.classifiers
            )

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
        self.core.call_one(
            "mainloop_execute", self.cursor.execute,
            "DELETE FROM features WHERE doc_id = ?", (doc_id,)
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

        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt).strip()

        vector = self.vectorizer.partial_fit_transform([doc_txt])[0].toarray()
        self.core.call_one(
            "mainloop_execute", self.cursor.execute,
            "INSERT INTO features (doc_id, vector) VALUES (?, ?)",
            (doc_id, vector)
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
        SqliteNumpyArrayHandler.register()

    def get_interfaces(self):
        return [
            'sync',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'data_versioning',
                'defaults': ['openpaperwork_core.data_versioning'],
            },
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

    def _load_classifiers(self, vectorizer):
        # Jflesch> This is a very memory-intensive process. The Glib may try
        # to allocate memory before the GC runs and AFAIK the Glib
        # is not aware of Python GC, and so won't trigger it if required
        # (instead it will abort).
        # --> free as much memory as possible now
        # (Remember that there may be 32bits version of Paperwork out there)
        gc.collect()

        msg = _("Label guessing: Training ...")

        cursor = self.core.call_one(
            "mainloop_execute", self.sql.cursor
        )

        try:
            self.core.call_all("on_progress", "classifiers", 0.0, msg)

            corpus = self.core.call_one(
                "mainloop_execute", Corpus.load, cursor
            )

            LOGGER.info("Training classifiers ...")
            start = time.time()

            if corpus.get_doc_count() <= 1:
                return (None, None)

            corpus.standardize_feature_vectors(vectorizer)
            # no need to train on all the words. Only the most used words
            reductor = corpus.reduce_corpus_words()

            # Jflesch> This is a very memory-intensive process. The Glib may
            # try to allocate memory before the GC runs and AFAIK the Glib
            # is not aware of Python GC, and so won't trigger it if required
            # (instead it will abort).
            # --> free as much memory as possible now
            gc.collect()

            classifiers = collections.defaultdict(
                sklearn.naive_bayes.GaussianNB
            )

            batch_iterators = [
                (label, corpus.get_batches(label))
                for label in corpus.get_labels()
            ]
            done = 0
            total = len(batch_iterators) * corpus.get_doc_count()

            try:
                while True:
                    for (label, batch_iterator) in batch_iterators:
                        (batch_corpus, batch_targets) = next(batch_iterator)
                        self.core.call_all(
                            "on_progress", "classifiers", done / total,
                            _("Label guessing: Training ...")
                        )
                        classifiers[label].partial_fit(
                            batch_corpus, batch_targets,
                            classes=[0, 1]
                        )
                        done += len(batch_corpus)
            except StopIteration:
                pass

            stop = time.time()
            LOGGER.info(
                "Training took %dms",
                int((stop - start) * 1000)
            )

            # Jflesch> This is a very memory-intensive process. The Glib may
            # try to allocate memory before the GC runs and AFAIK the Glib
            # is not aware of Python GC, and so won't trigger it if required
            # (instead it will abort).
            # --> free as much memory as possible now
            gc.collect()

            return (reductor, classifiers)
        finally:
            self.core.call_all("on_progress", "classifiers", 1.0, msg)
            self.core.call_one("mainloop_execute", cursor.close)

    def _guess(self, vectorizer, reductor, classifiers, doc_url):
        LOGGER.info("Guessing labels on %s", doc_url)
        doc_txt = []
        self.core.call_all("doc_get_text_by_url", doc_txt, doc_url)
        doc_txt = "\n\n".join(doc_txt).strip()
        if doc_txt == u"":
            return

        vector = vectorizer.transform([doc_txt])
        vector = vector.toarray()[0]
        vector = reductor.reduce_features(vector)

        for (label, classifier) in classifiers.items():
            predicted = classifier.predict([vector])[0]
            if predicted:
                yield label

    def _set_guessed_labels(self, doc_url, vectorizer, reductor, classifiers):
        labels = self._guess(vectorizer, reductor, classifiers, doc_url)
        labels = list(labels)
        for label in labels:
            self.core.call_success("doc_add_label_by_url", doc_url, label)

    def tests_cleanup(self):
        self.sql.close()
