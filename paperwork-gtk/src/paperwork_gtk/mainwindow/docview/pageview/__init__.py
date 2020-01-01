import gettext
import logging
import time

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext

DELAY = 0.01


class Page(object):
    DEFAULT_BACKGROUND = (0.5, 0.5, 0.5)

    def __init__(self, core, flow_layout, doc_id, doc_url, page_idx, nb_pages):
        self.core = core
        self.flow_layout = flow_layout
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_idx = page_idx
        self.nb_pages = nb_pages

        self.height = 1.0
        self.page_img_load_promise = None
        self.page_img_url = self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx
        )

        self.img_size = None
        self.widget_tree = None
        self.widget = None

        self.cairo_surface = None

        flow_layout.connect("widget_visible", self._on_widget_visible)
        flow_layout.connect("widget_hidden", self._on_widget_hidden)

        promise = openpaperwork_core.promise.Promise(
            core, core.call_all,
            args=(
                "on_progress", "loading_page_sizes",
                self.page_idx / self.nb_pages,
                _("Loading page {}/{} ...").format(
                    self.page_idx, self.nb_pages
                ),
            )
        )
        promise = promise.then(lambda nb_calls: None)
        promise = promise.then(self.core.call_success(
            "url_to_img_size_promise", self.page_img_url
        ))
        promise = promise.then(self._set_img_size)
        # Gives back a bit of CPU time to GTK so the GUI remains
        # usable
        promise = promise.then(openpaperwork_core.promise.ThreadedPromise(
            core, time.sleep, args=(DELAY,)
        ))
        self.core.call_success(
            "work_queue_add_promise", "page_loader", promise
        )

    def __str__(self):
        return "{} p{}".format(self.doc_id, self.page_idx)

    def _set_img_size(self, size):
        self.img_size = size

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageview", "pageview.glade"
        )
        self.widget = self.widget_tree.get_object("pageview_area")
        self.widget.set_size_request(size[0], size[1])
        self.widget.connect("draw", self._on_draw)
        self.flow_layout.add(self.widget)
        self.resize()

    def get_stage(self):
        return self.embed.get_stage()

    def set_height(self, height):
        self.height = height
        self.resize()

    def get_size_factor(self):
        if self.img_size is None:
            return 0
        return self.height / self.img_size[1]

    def get_size(self):
        if self.img_size is None:
            return (0, 0)
        factor = self.get_size_factor()
        return (int(self.img_size[0]) * factor, self.height)

    def resize(self):
        if self.img_size is None:
            return
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])

    def hide(self):
        if self.page_img_load_promise is not None:
            self.core.call_success(
                "work_queue_cancel", "page_loader", self.page_img_load_promise
            )
            self.page_img_load_promise = None

    def refresh(self, reload=False):
        if reload:
            self.hide()
            self.show()
        else:
            self.widget.queue_draw()

    def show(self):
        promise = openpaperwork_core.promise.ThreadedPromise(
            # Gives back a bit of CPU time to GTK so the GUI remains
            # usable
            self.core, time.sleep, args=(DELAY,)
        )
        promise = promise.then(self.core.call_success(
            "url_to_cairo_surface_promise", self.page_img_url
        ))
        promise = promise.then(self._on_pageview_page_loaded)
        self.page_img_load_promise = promise

        self.core.call_success(
            "work_queue_add_promise", "page_loader", promise, priority=100
        )

    def _on_widget_visible(self, flowlayout, widget):
        if widget != self.widget:
            return
        self.show()

    def _on_widget_hidden(self, flowlayout, widget):
        if widget != self.widget:
            return
        self.hide()

    def _on_pageview_page_loaded(self, cairo_surface):
        self.cairo_surface = cairo_surface
        self.refresh()

    def _on_draw(self, widget, cairo_ctx):
        if self.cairo_surface is None:
            cairo_ctx.save()
            try:
                size = self.get_size()
                (r, g, b) = self.DEFAULT_BACKGROUND
                cairo_ctx.set_source_rgb(r, g, b)
                cairo_ctx.rectangle(0, 0, size[0], size[1])
                cairo_ctx.clip()
                cairo_ctx.paint()
            finally:
                cairo_ctx.restore()
        else:
            cairo_ctx.save()
            try:
                cairo_ctx.scale(
                    self.get_size_factor(),
                    self.get_size_factor(),
                )
                cairo_ctx.set_source_surface(self.cairo_surface)
                cairo_ctx.paint()
            finally:
                cairo_ctx.restore()


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def get_interfaces(self):
        return [
            'gtk_docview',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'cairo_url',
                'defaults': [
                    'paperwork_backend.cairo.pillow',
                    'paperwork_backend.cairo.poppler',
                ],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'page_img',
                'defaults': [
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'work_queue',
                'defaults': ['openpaperwork_core.work_queue.default'],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all("work_queue_create", "page_loader")

    def doc_open_components(self, doc_id, doc_url, page_container):
        self.core.call_success("work_queue_cancel_all", "page_loader")

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            LOGGER.warning("Failed to get the number of pages in %s", doc_id)
            nb_pages = 0

        self.core.call_all(
            "on_perfcheck_start",
            "pageview->doc_open_components({})".format(doc_id)
        )
        for page_idx in range(0, nb_pages):
            page = Page(
                self.core, page_container, doc_id, doc_url, page_idx, nb_pages
            )
            page.set_height(400)  # default

        promise = openpaperwork_core.promise.Promise(
            self.core, self.core.call_one,
            args=(
                "mainloop_schedule", self.core.call_all,
                "on_progress", "loading_page_sizes", 1.0
            ),
        )
        self.core.call_success(
            "work_queue_add_promise", "page_loader", promise
        )

        self.core.call_all(
            "on_perfcheck_stop",
            "pageview->doc_open_components({})".format(doc_id),
            nb_pages=nb_pages
        )
