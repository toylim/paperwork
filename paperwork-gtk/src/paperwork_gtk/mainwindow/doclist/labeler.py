import logging

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core
import openpaperwork_gtk.deps


LOGGER = logging.getLogger(__name__)


class LabelingTask(object):
    def __init__(self, plugin, doc_id, flowlayout):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.flowlayout = flowlayout

    def show_labels(self, labels):
        labels = list(labels)
        labels.sort()
        for label in labels:
            color = self.core.call_success("label_color_to_rgb", label[1])
            widget = self.core.call_success(
                "gtk_widget_label_new", label[0], color
            )
            widget.set_visible(True)
            self.flowlayout.add(widget)
            self.flowlayout.set_alignment(widget, Gtk.Align.END)

    def get_promise(self):
        doc_url = self.core.call_success("doc_id_to_url", self.doc_id)

        promise = openpaperwork_core.promise.Promise(
            self.core,
            LOGGER.debug, args=("Loading labels of document %s", self.doc_id,)
        )
        promise = promise.then(lambda *args: None)  # drop logger return value

        promises = []
        self.core.call_all("doc_get_labels_by_url_promise", promises, doc_url)
        for p in promises:
            promise = promise.then(p)

        return promise.then(self.show_labels)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.default_thumbnail = None
        self.running = False

    def get_interfaces(self):
        return ['gtk_thumbnailer']

    def get_deps(self):
        return [
            {
                'interface': 'doc_labels',
                'defaults': ['paperwork_backend.model.labels'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.maindow.doclist'],
            },
            {
                'interface': 'gtk_widget_label',
                'defaults': ['paperwork_gtk.widget.label'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all("work_queue_create", "labeler", stop_on_quit=True)

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk'].update(openpaperwork_gtk.deps.GTK)

    def doclist_show(self, docids):
        self.core.call_all("work_queue_cancel_all", "labeler")

    def on_doc_box_creation(self, doc_id, gtk_row, gtk_custom_flowlayout):
        task = LabelingTask(self, doc_id, gtk_custom_flowlayout)
        self.core.call_success(
            "work_queue_add_promise", "labeler", task.get_promise()
        )
