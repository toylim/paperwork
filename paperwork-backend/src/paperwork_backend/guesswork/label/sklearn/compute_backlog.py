"""
To use it:

```sh
paperwork-cli plugins add \
    paperwork_backend.guesswork.label.sklearn.compute_backlog
paperwork-cli compute_sklearn_label_guessing_backlog
```
"""

import functools
import itertools
import time

import sklearn.naive_bayes
import sklearn.feature_extraction.text

import openpaperwork_core


def pairwise(iterable):
    (a, b) = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class Baye(object):
    def __init__(self):
        self.data = []
        self.targets = []

        self.sklearn_count_vectorizer = None
        self.sklearn_tfid_transformer = None
        self.sklearn_classifier = None

        self.reset()

    def reset(self):
        self.sklearn_count_vectorizer = \
            sklearn.feature_extraction.text.CountVectorizer()
        self.sklearn_tfid_transformer = \
            sklearn.feature_extraction.text.TfidfTransformer(use_idf=False)
        self.sklearn_classifier = sklearn.naive_bayes.GaussianNB()

    def fit(self, category, text):
        text = text.strip()
        if len(text) <= 0:
            return

        category = (1 if category == 'yes' else 0)
        self.data.append(text)
        self.targets.append(category)

    def seal(self):
        counts = self.sklearn_count_vectorizer.fit_transform(self.data)
        tfid = self.sklearn_tfid_transformer.fit_transform(counts)
        self.sklearn_classifier.fit(tfid.toarray(), self.targets)

    def score(self, text, label):
        counts = self.sklearn_count_vectorizer.transform([text])
        tfid = self.sklearn_tfid_transformer.transform(counts)
        predicted = self.sklearn_classifier.predict_proba(tfid.toarray())
        r = {
            "no": predicted[0][0],
            "yes": predicted[0][1],
        }
        return r


class Bayes(object):
    def __init__(self, labels):
        self.bayes = {
            label: Baye()
            for label in labels
        }

    def reset(self):
        for v in self.bayes.values():
            v.reset()

    def fit(self, label, present, text):
        self.bayes[label].fit("yes" if present else "no", text)

    def seal(self):
        for v in self.bayes.values():
            v.seal()

    def score(self, label, text):
        score = self.bayes[label].score(text, label)
        return {
            "yes": score['yes'] if 'yes' in score else 0,
            "no": score['no'] if 'no' in score else 0,
        }


@functools.total_ordering
class Document(object):
    def __init__(self, core, doc_id, text, labels):
        self.core = core
        self.doc_id = doc_id
        self.text = text
        self.labels = labels
        self.scores = {}

    def __lt__(self, other):
        return self.doc_id < other.doc_id

    def __eq__(self, other):
        return self.doc_id == self.doc_id

    def __hash__(self):
        return hash(self.doc_id)

    def fit(self, bayes, all_labels):
        for label in all_labels:
            bayes.fit(label, label in self.labels, self.text)

    def compute_scores(self, bayes, all_labels):
        for label in all_labels:
            self.scores[label] = bayes.score(label, self.text)

    def compute_accuracy(self, all_labels):
        success = 0
        for label in all_labels:
            score = self.scores[label]
            guessed_has_label = (score['yes'] > score['no'])
            if guessed_has_label == (label in self.labels):
                success += 1
        return success / len(all_labels)


class Corpus(object):
    """
    All the texts of all the documents, and their labels.
    """
    def __init__(self, core):
        self.core = core
        self.all_documents = []
        self.documents = []
        self.labels = set()
        self.bayes = None

    def reset(self):
        self.bayes.reset()

    def load_all(self):
        self.all_documents = []
        docs = []
        self.core.call_all("storage_get_all_docs", docs)
        total = len(docs)
        for (idx, (doc_id, doc_url)) in enumerate(docs):
            self.core.call_all(
                "on_progress", "load_docs",
                idx / total, "Loading document %s" % doc_id
            )
            text = []
            self.core.call_all("doc_get_text_by_url", text, doc_url)
            text = "\n\n".join(text)

            labels = set()
            self.core.call_all("doc_get_labels_by_url", labels, doc_url)
            labels = [label[0] for label in labels]
            labels.sort()
            for label in labels:
                self.labels.add(label)

            self.all_documents.append(
                Document(self.core, doc_id, text, labels)
            )

        self.all_documents.sort()
        self.all_documents.reverse()
        self.core.call_all("on_progress", "load_docs", 1.0)

        self.bayes = Bayes(self.labels)

    def _get_doc_with_label(self, label, backlog):
        nb = 0
        for doc in self.all_documents:
            if label in doc.labels:
                yield doc
                nb += 1
                if nb >= backlog:
                    break

    def _get_doc_without_label(self, label, backlog):
        nb = 0
        for doc in self.all_documents:
            if label not in doc.labels:
                yield doc
                nb += 1
                if nb >= backlog:
                    break

    def fit(self, backlog):
        docs = set()
        for label in self.labels:
            docs.update(self._get_doc_with_label(label, backlog))
            docs.update(self._get_doc_without_label(label, backlog))

        self.documents = set(self.all_documents)
        for doc in docs:
            self.documents.remove(doc)
        self.documents = list(self.documents)
        self.documents.sort()
        self.documents.reverse()
        self.documents = self.documents[:200]
        if len(self.documents) < 200:
            print("Not enough documents left ({})".format(
                len(self.documents)
            ))
            return False

        for (idx, doc) in enumerate(docs):
            self.core.call_all(
                "on_progress", "training",
                idx / len(docs),
                "Extracting features from %d documents" % len(docs)
            )
            doc.fit(self.bayes, self.labels)
        self.core.call_all("on_progress", "training", 1.0)
        print("Extracted features from %d documents" % len(docs))
        return True

    def seal(self):
        print("Training...")
        self.bayes.seal()
        print("Training done")

    def compute_scores(self):

        total = len(self.documents)
        for (idx, doc) in enumerate(self.documents):
            self.core.call_all(
                "on_progress", "scoring",
                idx / total, "computing label scores on %s" % doc.doc_id
            )
            doc.compute_scores(self.bayes, self.labels)
        self.core.call_all("on_progress", "scoring", 1.0)

    def compute_accuracy(self):
        accuracy_sum = 0

        total = len(self.documents)
        for doc in self.documents:
            accuracy_sum += doc.compute_accuracy(self.labels)
        return accuracy_sum / total


class Plugin(openpaperwork_core.PluginBase):
    """
    Add a command to search for the best backlog for
    paperwork_backend.guesswork.label.sklearn
    heuristically and based on the user's documents.
    """
    def get_interfaces(self):
        return [
            'shell',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'doc_text',
                'defaults': [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'i18n',
                'defaults': ['openpaperwork_core.i18n.python'],
            },
        ]

    def cmd_complete_argparse(self, parser):
        parser.add_parser('compute_sklearn_label_guessing_backlog')

    def cmd_run(self, console, args):
        if args.command != 'compute_sklearn_label_guessing_backlog':
            return None

        corpus = Corpus(self.core)
        corpus.load_all()

        for backlog in (1, 10, 25, 50, 75, 100, 150, 200, 250, 300, 500, 2500):
            console.print("")
            console.print("Backlog {}:".format(backlog))
            corpus.reset()
            if not corpus.fit(backlog):
                return {}
            start = time.time()
            corpus.seal()
            stop = time.time()
            corpus.compute_scores()
            accuracy = corpus.compute_accuracy()
            console.print(
                "Backlog: {} ; Accuracy: {} ; Training time: {}s".format(
                    backlog, accuracy, int(stop - start)
                )
            )
        return {}
