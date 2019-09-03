import logging

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)

LABELS_FILENAME = "labels"


class LabelLoader(object):
    """
    Go through all the documents to figure out what labels exist.
    """
    def __init__(self, plugin, all_docs):
        self.plugin = plugin
        self.core = plugin.core
        self.all_docs = all_docs
        self.promise = openpaperwork_core.promise.Promise(self.core)

        for (doc_id, doc_url) in all_docs:
            self.promise = self.promise.then(self.load_labels, doc_url)

        self.promise.then(self.notify_done)

    def run(self):
        self.core.call_all("on_label_loading_start")
        self.promise.schedule()

    def load_labels(self, doc_url):
        labels = set()
        self.plugin.doc_get_labels_by_url(labels, doc_url)
        for label in labels:
            self.plugin.all_labels[label[0]] = label[1]

    def notify_done(self):
        self.core.call_all("on_label_loading_end")


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        # {label_name: color, label_name: color, ...}
        self.all_labels = {}

    def get_interfaces(self):
        return [
            "doc_labels",
            "syncable",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('fs', ['paperwork_backend.fs.gio']),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
            ]
        }

    def doc_get_labels_by_url(self, out, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return
        with self.core.call_success("fs_open", labels_url, 'r') as file_desc:
            for line in file_desc.readlines():
                line = line.strip()
                if line == "":
                    continue
                # Expected: ('label', '#rrrrggggbbbb')
                out.add(tuple(x.strip() for x in line.split(",")))

    def doc_add_label(self, doc_url, label, color=None):
        assert("," not in label)
        assert(color is None or "," not in color)

        if color is not None:
            assert(
                label not in self.all_labels
                or self.all_labels[label] == color
            )
            self.all_labels[label] = color
        else:
            color = self.all_labels[label]

        LOGGER.info("Adding label '%s' on document '%s'", label, doc_url)

        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        with self.core.call_success("fs_open", labels_url, 'a') as file_desc:
            file_desc.write("{},{}".format(label, color))

    def labels_get_all(self, out):
        for (label, color) in self.all_labels.items():
            out.add((label, color))

    def sync(self):
        self.all_labels = {}

        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        LabelLoader(self, storage_all_docs).run()
