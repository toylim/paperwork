"""
To use it:

```sh
paperwork-cli plugins add \
    paperwork_backend.guesswork.label.sklearn.gaussian_with_hashes
paperwork-cli test_sklearn_gaussian_with_hashes
```
"""
import time
import functools

import sklearn.naive_bayes

import openpaperwork_core


samples = 5


class Baye(object):
    def __init__(self, core, label, n_features):
        self.core = core
        self.label = label
        self.data = []
        self.counts = []
        self.tfid = []
        self.targets = []

        self.sklearn_hash_vectorizer = \
            sklearn.feature_extraction.text.HashingVectorizer(
                n_features=n_features
            )
        self.sklearn_tfid_transformer = \
            sklearn.feature_extraction.text.TfidfTransformer(use_idf=False)

        # Best accuracy: ~0.9991
        self.sklearn_classifier = sklearn.naive_bayes.GaussianNB()

    def fit(self, category, text):
        text = text.strip()
        if len(text) <= 0:
            return

        category = (1 if category == 'yes' else 0)
        self.data.append(text)
        self.targets.append(category)

    def seal(self):
        r = 0
        self.core.call_all(
            "on_progress", "fitting", 0.0,
            "Fitting training of label {} ...".format(self.label)
        )
        for pos in range(0, len(self.data), 50):
            self.core.call_all(
                "on_progress", "fitting", pos / len(self.data),
                "Fitting training of label {} ...".format(self.label)
            )
            counts = self.sklearn_hash_vectorizer.fit_transform(
                self.data[pos:pos + 50]
            )
            tfid = self.sklearn_tfid_transformer.fit_transform(
                counts
            ).toarray()

            start = time.time()
            self.sklearn_classifier.partial_fit(
                tfid, self.targets[pos:pos + 50],
                classes=[0, 1]
            )
            stop = time.time()
            r += stop - start
        self.core.call_all("on_progress", "fitting", 1.0)
        return r

    def score(self, text, label):
        global samples

        counts = self.sklearn_hash_vectorizer.transform([text])
        tfid = self.sklearn_tfid_transformer.transform(counts)
        predicted = self.sklearn_classifier.predict_proba(tfid.toarray())
        r = {
            "no": predicted[0][0],
            "yes": predicted[0][1],
        }
        if samples > 0:
            samples -= 1
            print("Prediction sample: {}={}".format(label, r))
        return r


class Bayes(object):
    def __init__(self, core, labels, n_features):
        self.core = core
        self.bayes = {
            label: Baye(core, label, n_features)
            for label in labels
        }

    def fit(self, label, present, text):
        self.bayes[label].fit("yes" if present else "no", text)

    def seal(self):
        r = 0
        for (idx, (k, v)) in enumerate(self.bayes.items()):
            print("Fitting training of label {} ({}/{}) ...".format(
                k, idx, len(self.bayes)
            ))
            r += v.seal()

        s = int(r)
        ms = int(((r) * 1000) % 1000)
        print("Fitting took {}s {}ms for {} labels".format(
            s, ms, len(self.bayes)
        ))

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
            guessed_has_label = score['yes'] > score['no']
            if guessed_has_label == (label in self.labels):
                success += 1
        return success / len(all_labels)


class Corpus(object):
    """
    All the texts of all the documents, and their labels.
    """
    def __init__(self, core):
        self.core = core
        self.documents = []
        self.labels = set()
        self.bayes = None

    def load_all(self):
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

            self.documents.append(Document(self.core, doc_id, text, labels))

        self.documents.sort()
        self.core.call_all("on_progress", "load_docs", 1.0)

    def mk_bayes(self, n_features):
        self.bayes = Bayes(self.core, self.labels, n_features)

    def fit(self):
        for (idx, doc) in enumerate(self.documents):
            doc.fit(self.bayes, self.labels)

    def seal(self):
        self.bayes.seal()

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
        parser.add_parser('test_sklearn_gaussian_with_hashes')

    def cmd_run(self, console, args):
        if args.command != 'test_sklearn_gaussian_with_hashes':
            return None

        corpus = Corpus(self.core)
        corpus.load_all()

        for two_pow in (16, 18, 20,):
            n_features = 2 ** two_pow
            corpus.mk_bayes(n_features)
            corpus.fit()
            corpus.seal()
            corpus.compute_scores()
            accuracy = corpus.compute_accuracy()

            console.print("n_features=2**{} --> accuracy={}".format(
                two_pow, accuracy
            ))

        return True
