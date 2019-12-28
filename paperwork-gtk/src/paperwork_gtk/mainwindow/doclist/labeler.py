import collections
import logging

import PIL

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False

import openpaperwork_core

from paperwork_backend.model.thumbnail import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH
)


LOGGER = logging.getLogger(__name__)


class LabelingTask(object):
    def __init__(self, plugin, doc_id, flowbox):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.flowbox = flowbox

    def show_labels(self, labels):
        for label in labels:
            color = self.core.call_success("label_color_to_rgb", label[1])
            widget = self.core.call_success(
                "gtk_widget_label_new", label[0], color
            )
            widget.set_visible(True)
            self.flowbox.add(widget)
            self.flowbox.set_alignment(widget, Gtk.Align.END)

    def do(self):
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

        promise = promise.then(self.show_labels)
        promise = promise.then(self.plugin._do_next_labeling)
        promise.schedule()


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.default_thumbnail = None
        self.work_queue = collections.deque()
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
        ]

    def chkdeps(self, out: dict):
        if not GTK_AVAILABLE:
            out['gtk']['debian'] = 'gir1.2-gtk-3.0'
            out['gtk']['fedora'] = 'gtk3'
            out['gtk']['gentoo'] = 'x11-libs/gtk+'
            out['gtk']['linuxmint'] = 'gir1.2-gtk-3.0'
            out['gtk']['ubuntu'] = 'gir1.2-gtk-3.0'
            out['gtk']['suse'] = 'python-gtk'

    def on_doc_box_creation(self, doc_id, gtk_row, gtk_custom_flowbox):
        task = LabelingTask(self, doc_id, gtk_custom_flowbox)
        self.work_queue.append(task)

        if not self.running:
            self._do_next_labeling()

    def _do_next_labeling(self):
        self.running = True
        try:
            task = self.work_queue.popleft()
            task.do()
        except IndexError:
            self.running = False
            LOGGER.debug("All thumbnails have been generated")
