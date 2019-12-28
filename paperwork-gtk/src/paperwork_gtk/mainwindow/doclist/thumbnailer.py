import collections
import logging

import PIL

import openpaperwork_core

from paperwork_backend.model.thumbnail import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH
)


LOGGER = logging.getLogger(__name__)


class ThumbnailTask(object):
    def __init__(self, plugin, doc_id, gtk_image):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.gtk_image = gtk_image

    def set_thumbnail(self, img):
        if img is None:
            LOGGER.warning(
                "Failed to get thumbnail for document %s", self.doc_id
            )
            return
        pixbuf = self.core.call_success("pillow2pixbuf", img)
        self.gtk_image.set_from_pixbuf(pixbuf)

    def do(self):
        doc_url = self.core.call_success("doc_id_to_url", self.doc_id)

        promise = openpaperwork_core.promise.Promise(
            self.core,
            LOGGER.info, args=("Thumbnailing of document %s", self.doc_id,)
        )
        promise = promise.then(lambda *args: None)  # drop logger return value
        promise = promise.then(
            self.core.call_success("thumbnail_get_doc_promise", doc_url)
        )
        promise = promise.then(self.set_thumbnail)
        promise = promise.then(self.plugin._do_next_thumbnail)
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
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'gtk_doclist',
                'defaults': ['paperwork_gtk.maindow.doclist'],
            },
            {
                'interface': 'pillow_util',
                'defaults': ['paperwork_backend.pillow.util'],
            },
            {
                'interface': 'pixbuf_pillow',
                'defaults': ['openpaperwork_gtk.pixbuf.pillow'],
            },
            {
                'interface': 'thumbnail',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
        ]

    def init(self, core):
        super().init(core)
        img = PIL.Image.new(
            "RGB",
            (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT),
            color="#EEEEEE"
        )
        img = self.core.call_success("pillow_add_border", img)
        self.default_thumbnail = self.core.call_success("pillow2pixbuf", img)

    def on_doc_box_creation(self, doc_id, gtk_row, gtk_custom_flowbox):
        gtk_img = gtk_row.get_object("doc_thumbnail")
        gtk_img.set_from_pixbuf(self.default_thumbnail)
        gtk_img.set_size_request(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        gtk_img.set_visible(True)

        task = ThumbnailTask(self, doc_id, gtk_img)
        self.work_queue.append(task)

        if not self.running:
            self._do_next_thumbnail()

    def _do_next_thumbnail(self):
        self.running = True
        try:
            task = self.work_queue.popleft()
            task.do()
        except IndexError:
            self.running = False
            LOGGER.debug("All thumbnails have been generated")
