"""
To use it:

```sh
paperwork-cli plugins add \
    paperwork_backend.guesswork.label.simplebayes.compute_threshold
paperwork-cli compute_label_guessing_threshold
```
"""

import functools
import itertools
import time

import simplebayes

import openpaperwork_core


NB_ITERATIONS = 16  # beware complexity will increase exponentionnally


def pairwise(iterable):
    (a, b) = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class Bayes(object):
    def __init__(self, labels):
        self.bayes = {
            label: simplebayes.SimpleBayes()
            for label in labels
        }

    def train(self, label, present, text):
        self.bayes[label].train("yes" if present else "no", text)

    def score(self, label, text):
        score = self.bayes[label].score(text)
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

    def train(self, bayes, all_labels):
        for label in all_labels:
            bayes.train(label, label in self.labels, self.text)

    def compute_scores(self, bayes, all_labels):
        for label in all_labels:
            self.scores[label] = bayes.score(label, self.text)

    def compute_accuracy(self, threshold, all_labels):
        success = 0
        for label in all_labels:
            score = self.scores[label]
            total = score['yes'] + score['no']
            if total == 0:
                score = 0
            else:
                score = score['yes'] / total
            guessed_has_label = score > threshold
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

            text = self.core.call_success("page_get_text_by_url", doc_url, 0)
            if text is None:
                continue

            labels = set()
            self.core.call_all("doc_get_labels_by_url", labels, doc_url)
            labels = [label[0] for label in labels]
            labels.sort()
            for label in labels:
                self.labels.add(label)

            self.documents.append(Document(self.core, doc_id, text, labels))

        self.documents.sort()
        self.core.call_all("on_progress", "load_docs", 1.0)

        self.bayes = Bayes(self.labels)

    def train(self):
        total = len(self.documents)
        for (idx, doc) in enumerate(self.documents):
            self.core.call_all(
                "on_progress", "training",
                idx / total, "Training from %s" % doc.doc_id
            )
            doc.train(self.bayes, self.labels)
        self.core.call_all("on_progress", "training", 1.0)

    def compute_scores(self):
        total = len(self.documents)
        for (idx, doc) in enumerate(self.documents):
            self.core.call_all(
                "on_progress", "scoring",
                idx / total, "computing label scores on %s" % doc.doc_id
            )
            doc.compute_scores(self.bayes, self.labels)
        self.core.call_all("on_progress", "scoring", 1.0)

    def compute_accuracy(self, threshold):
        accuracy_sum = 0

        total = len(self.documents)
        for doc in self.documents:
            accuracy_sum += doc.compute_accuracy(threshold, self.labels)
        return accuracy_sum / total


class Plugin(openpaperwork_core.PluginBase):
    """
    Add a command to search for the best threshold for
    paperwork_backend.guesswork.label.simplebayes (see THRESHOLD_YES_NO_RATIO)
    heuristically and based on the user's documents.
    """
    def __init__(self):
        super().__init__()
        self.interactive = False

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

    def cmd_set_interactive(self, interactive):
        self.interactive = interactive

    def cmd_complete_argparse(self, parser):
        parser.add_parser('compute_label_guessing_threshold')

    @staticmethod
    def _get_next_thresholds(thresholds):
        """
        Heuristic figuring out the next thresholds to try to estimate
        """
        middles = []
        for (threshold, next_threshold) in pairwise(thresholds):
            middles.append(
                (
                    (threshold[0] + next_threshold[0]) / 2,
                    (threshold[1] + next_threshold[1]) / 2,
                )
            )
        return [m[0] for m in middles]

    def cmd_run(self, args):
        if args.command != 'compute_label_guessing_threshold':
            return None

        corpus = Corpus(self.core)
        corpus.load_all()
        corpus.train()
        corpus.compute_scores()

        iterations = NB_ITERATIONS
        thresholds = [
            (threshold, corpus.compute_accuracy(threshold))
            for threshold in (0.0, 1.0)
        ]

        for iteration in range(0, iterations):
            print("")
            best = max(thresholds, key=lambda x: x[1])
            print("Iteration {}: best accuracy={}, best threshold={}".format(
                iteration, best[1], best[0]
            ))

            start = time.time()
            next_thresholds = self._get_next_thresholds(thresholds)
            total = len(next_thresholds)
            for (idx, next_threshold) in enumerate(next_thresholds):
                self.core.call_all(
                    "on_progress", "iteration",
                    idx / total, "Iteration %d" % iteration
                )
                thresholds.append(
                    (next_threshold, corpus.compute_accuracy(next_threshold)),
                )
            thresholds.sort()
            self.core.call_all("on_progress", "iteration", 1.0)
            stop = time.time()

            s = int(stop - start)
            ms = int(((stop - start) * 1000) % 1000)
            print("Iteration took {}s {}ms".format(s, ms))

        print("")
        best = max(thresholds, key=lambda x: x[1])
        print("RESULT: best accuraccy={}, best threshold={}".format(
            best[1], best[0]
        ))

        return {
            "all": thresholds,
            "best": best,
        }
