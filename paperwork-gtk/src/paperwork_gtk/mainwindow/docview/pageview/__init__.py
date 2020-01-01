import gettext
import logging
import time

import openpaperwork_core
import openpaperwork_core.promise


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext


class Page(object):
    def __init__(self, core, flow_layout, doc_id, doc_url, page_idx, nb_pages):
        self.core = core
        self.flow_layout = flow_layout
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_idx = page_idx
        self.nb_pages = nb_pages

        self.height = 1.0

        page_img_url = self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx
        )

        self.widget_tree = None
        self.widget = None

        flow_layout.connect("widget_visible", self._on_widget_visible)
        flow_layout.connect("widget_hidden", self._on_widget_hidden)

        self.renderer = core.call_success(
            "cairo_renderer_by_url", "page_loader", page_img_url
        )
        self.renderer.connect("getting_size", self._on_renderer_getting_size)
        self.renderer.connect("size_obtained", self._on_renderer_size)
        self.renderer.connect("img_obtained", self._on_renderer_img)
        self.renderer.start()

    def __str__(self):
        return "{} p{}".format(self.doc_id, self.page_idx)

    def _on_renderer_getting_size(self, renderer):
        self.core.call_all(
            "on_progress", "loading_page_sizes",
            self.page_idx / self.nb_pages,
            _("Loading page {}/{} ...").format(self.page_idx, self.nb_pages)
        )

    def _on_renderer_size(self, renderer):
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageview", "pageview.glade"
        )
        self.widget = self.widget_tree.get_object("pageview_area")
        self.widget.connect("draw", self._on_draw)
        self.flow_layout.add(self.widget)
        self.resize()

    def _on_renderer_img(self, renderer):
        return self.refresh()

    def set_height(self, height):
        self.height = height
        self.resize()

    def get_size_factor(self):
        if self.renderer.size[0] == 0:
            return 0
        return self.height / self.renderer.size[1]

    def get_size(self):
        factor = self.get_size_factor()
        return (int(self.renderer.size[0]) * factor, self.height)

    def resize(self):
        if self.renderer.size[0] == 0:
            return
        self.renderer.size_factor = self.get_size_factor()
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])

    def refresh(self, reload=False):
        if reload:
            self.hide()
            self.show()
        else:
            self.widget.queue_draw()

    def hide(self):
        self.renderer.hide()

    def show(self):
        self.renderer.render()

    def _on_widget_visible(self, flowlayout, widget):
        if widget != self.widget:
            return
        self.show()

    def _on_widget_hidden(self, flowlayout, widget):
        if widget != self.widget:
            return
        self.hide()

    def _on_draw(self, widget, cairo_ctx):
        self.renderer.draw(cairo_ctx)


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
            "work_queue_add_promise", "page_loader", promise, priority=-100
        )

        self.core.call_all(
            "on_perfcheck_stop",
            "pageview->doc_open_components({})".format(doc_id),
            nb_pages=nb_pages
        )
