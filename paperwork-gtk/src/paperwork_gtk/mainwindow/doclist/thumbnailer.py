import logging

import PIL

import openpaperwork_core

from paperwork_backend.model.thumbnail import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH
)

from ... import _


LOGGER = logging.getLogger(__name__)
DELAY = 0.01

# placeholders size must include borders
PLACEHOLDER_HEIGHT = THUMBNAIL_HEIGHT + 2
PLACEHOLDER_WIDTH = THUMBNAIL_WIDTH + 2


class ThumbnailTask(object):
    def __init__(self, plugin, doc_id, gtk_image):
        self.plugin = plugin
        self.core = plugin.core

        self.doc_id = doc_id
        self.gtk_image = gtk_image

    def set_thumbnail(self, img=None):
        if img is None:
            LOGGER.warning(
                "Failed to get thumbnail for document %s", self.doc_id
            )
            return
        pixbuf = self.core.call_success("pillow_to_pixbuf", img)
        self.gtk_image.set_from_pixbuf(pixbuf)

    def get_promise(self):
        doc_url = self.core.call_success("doc_id_to_url", self.doc_id)
        if doc_url is None:
            return openpaperwork_core.promise.Promise(self.core)

        promise = openpaperwork_core.promise.Promise(
            self.core,
            LOGGER.debug, args=("Thumbnailing of document %s", self.doc_id,)
        )
        promise = promise.then(lambda *args: None)  # drop logger return value
        promise = promise.then(
            self.core.call_success("thumbnail_get_doc_promise", doc_url)
        )
        promise = promise.then(self.set_thumbnail)
        return promise


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.default_thumbnail = None
        self.running = False

        self.nb_loaded = 0
        self.nb_to_load = 0
        self._progress_str = None

    def get_interfaces(self):
        return [
            'gtk_doclist_listener',
            'gtk_thumbnailer',
        ]

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
                'defaults': ['openpaperwork_core.pillow.util'],
            },
            {
                'interface': 'pixbuf_pillow',
                'defaults': ['openpaperwork_gtk.pixbuf.pillow'],
            },
            {
                'interface': 'thumbnail',
                'defaults': ['paperwork_backend.model.thumbnail'],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def init(self, core):
        super().init(core)
        img = PIL.Image.new(
            "RGB",
            (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT),
            color="#EEEEEE"
        )
        self.default_thumbnail = self.core.call_success(
            "pillow_to_pixbuf", img
        )
        self.core.call_all(
            "work_queue_create", "thumbnailer", stop_on_quit=True
        )
        self._progress_str = _("Loading document thumbnails")

    def doclist_show(self, docs):
        self.core.call_all("work_queue_cancel_all", "thumbnailer")

    def on_doc_box_creation(self, doc_id, gtk_row, gtk_custom_flowlayout):
        gtk_img = gtk_row.get_object("doc_thumbnail")
        gtk_img.set_size_request(PLACEHOLDER_WIDTH, PLACEHOLDER_HEIGHT)
        gtk_img.set_visible(True)

        self.nb_to_load += 1

        task = ThumbnailTask(self, doc_id, gtk_img)
        promise = task.get_promise()

        def _when_loaded():
            self.nb_loaded += 1
            self._update_progress()

        promise = promise.then(_when_loaded)

        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.DelayPromise(
            self.core, DELAY
        ))

        self.core.call_success(
            "work_queue_add_promise", "thumbnailer", promise
        )

    def _update_progress(self):
        assert(self.nb_to_load > 0)
        if self.nb_loaded > self.nb_to_load:
            self.nb_loaded = 0
            self.nb_to_load = 0
            self.core.call_all("on_progress", "thumbnailing", 1.0)
            return

        self.core.call_all(
            "on_progress", "thumbnailing", self.nb_loaded / self.nb_to_load,
            self._progress_str
        )
