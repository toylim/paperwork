import random
import sys

import openpaperwork_core
import paperwork_backend
import paperwork_shell.main

from . import words


def get_core():
    print("Loading core ...")
    core = openpaperwork_core.Core()
    for module_name in paperwork_backend.DEFAULT_CONFIG_PLUGINS:
        core.load(module_name)
    core.init()
    core.call_all("init_logs", "docgenerator", 'debug')

    core.call_all(
        "config_load", "paperwork2", "labelgenerator",
        paperwork_shell.main.DEFAULT_CLI_PLUGINS
    )
    print("Core loaded")
    return core


def main():
    if len(sys.argv) <= 2:
        print("Usage:")
        print("  {} <work_dir> <nb_labels>".format(sys.argv[0]))
        sys.exit(1)

    work_dir = sys.argv[1]
    nb_labels = int(sys.argv[2])

    dictionary = words.WordDict()
    core = get_core()

    print("Generating labels ...")
    labels = []
    for _ in range(0, nb_labels):
        label = dictionary.pick_word()
        print("  - {}".format(label))
        labels.append(label)
    print()

    core.call_all("cmd_set_interactive", False)
    work_dir = core.call_success("fs_safe", work_dir)

    print("Switching work directory to {} ...".format(work_dir))
    core.call_all("config_put", "workdir", work_dir)

    promises = []
    core.call_all("sync", promises)
    promise = promises[0]
    for p in promises[1:]:
        promise = promise.then(p)
    core.call_one("mainloop_schedule", promise.schedule)
    core.call_all("mainloop_quit_graceful")
    core.call_one("mainloop")

    docs = []
    core.call_all("storage_get_all_docs", docs)
    docs.sort()
    print("{} documents found".format(len(docs)))

    transactions = []
    core.call_all("doc_transaction_start", transactions, len(docs))
    transactions.sort(key=lambda t: -t.priority)

    for (doc_id, doc_url) in docs:
        nb_labels_to_add = random.randint(0, max(1, int(nb_labels / 2)))
        print("{} <-- {} labels".format(doc_id, nb_labels_to_add))
        for _ in range(0, nb_labels_to_add):
            label = labels[random.randint(0, len(labels) - 1)]
            print("{} <- {}".format(doc_id, label))
            core.call_success("doc_add_label_by_url", doc_url, label)

        specials = [
            ('doc.pdf', '_PDF'),
            ('paper.1.jpg', '_IMG'),
            ('paper.1.words', '_HOCR'),
        ]
        for (file_name, label) in specials:
            file_path = core.call_success("fs_join", doc_url, file_name)
            if core.call_success("fs_exists", file_path) is not None:
                core.call_success("doc_add_label_by_url", doc_url, label)

        for t in transactions:
            t.upd_obj(doc_id)

    for t in transactions:
        t.commit()

    print("All done")
