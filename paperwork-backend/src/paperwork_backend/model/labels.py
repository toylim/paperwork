import logging
import random

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

    def get_promise(self):
        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_all, args=("on_label_loading_start",)
        )
        promise = promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, self.load_labels
            )
        )
        promise = promise.then(self.notify_done)
        return promise

    def load_labels(self, *args, **kwargs):
        for (doc_id, doc_url) in self.all_docs:
            labels = set()
            self.plugin.doc_get_labels_by_url(labels, doc_url)
            for label in labels:
                self.plugin.all_labels[label[0]] = label[1]

    def notify_done(self):
        self.core.call_one(
            "schedule",
            self.core.call_all, "on_label_loading_end"
        )


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
                ('document_storage', ['paperwork_backend.model.workdir']),
                ('fs', ['paperwork_backend.fs.gio']),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio']),
            ]
        }

    def doc_get_mtime_by_url(self, out: list, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return
        out.append(self.core.call_success("fs_get_mtime", labels_url))

    def doc_has_labels_by_url(self, doc_url):
        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        if self.core.call_success("fs_exists", labels_url) is None:
            return True
        return None

    def doc_get_labels_by_url(self, out: set, doc_url):
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
                out.add(tuple(x.strip() for x in line.split(",", 1)))

    def label_generate_color(self):
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )

    def doc_add_label_by_url(self, doc_url, label, color=None):
        assert("," not in label)
        assert(color is None or "," not in color)

        current = set()
        self.doc_get_labels_by_url(current, doc_url)
        current = {k: v for (k, v) in current}
        if label in current:
            LOGGER.warning(
                "Label '%s' already on document '%s'", label, doc_url
            )
            return

        if color is not None:
            assert(
                label not in self.all_labels
                or self.all_labels[label] == color
            )
            self.all_labels[label] = color
        else:
            color = self.label_generator_color()

        LOGGER.info("Adding label '%s' on document '%s'", label, doc_url)

        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )
        with self.core.call_success("fs_open", labels_url, 'a') as file_desc:
            file_desc.write("{},{}\n".format(label, color))

        if label not in self.all_labels:
            self.all_labels[label] = color

    def doc_remove_label_by_url(self, doc_url, label):
        LOGGER.info("Removing label '%s' from document '%s'", label, doc_url)

        labels_url = self.core.call_success(
            "fs_join", doc_url, LABELS_FILENAME
        )

        with self.core.call_success("fs_open", labels_url, 'r') as file_desc:
            labels = file_desc.readlines()

        labels = [l.split(",", 1) for l in labels if len(l.strip()) > 0]
        labels = {l: c for (l, c) in labels}
        try:
            labels.pop(label)
        except KeyError:
            LOGGER.warning(
                "Tried to remove label '%s' from document '%s', but label"
                " was not found on the document"
            )

        with self.core.call_success("fs_open", labels_url, "w") as file_desc:
            for (label, color) in labels.items():
                file_desc.write("{},{}\n".format(label, color))

    def labels_get_all(self, out: set):
        for (label, color) in self.all_labels.items():
            out.add((label, color))

    def label_color_to_rgb(self, color):
        if color[0] == '#':
            if len(color) == 13:
                return (
                    int(color[1:5], 16) / 0xFFFF,
                    int(color[5:9], 16) / 0xFFFF,
                    int(color[9:13], 16) / 0xFFFF,
                )
            else:
                return (
                    int(color[1:3], 16) / 0xFF,
                    int(color[3:5], 16) / 0xFF,
                    int(color[5:7], 16) / 0xFF,
                )
        elif color.startswith("rgb("):
            color = color[len("rgb("):-1]
            color = color.split(",")
            color = tuple([int(x) for x in color])
            color = (color[0] / 0xFF, color[1] / 0xFF, color[2] / 0xFF)
            return color

    def label_color_from_rgb(self, color):
        return (
            "#"
            + format(int(color[0] * 0xFF), 'x') + "00"
            + format(int(color[1] * 0xFF), 'x') + "00"
            + format(int(color[2] * 0xFF), 'x') + "00"
        )

    def label_load_all(self, promises: list):
        self.all_labels = {}

        storage_all_docs = []
        self.core.call_all("storage_get_all_docs", storage_all_docs)
        promises.append(LabelLoader(self, storage_all_docs).get_promise())

    def sync(self, promises: list):
        self.label_load_all(promises)
