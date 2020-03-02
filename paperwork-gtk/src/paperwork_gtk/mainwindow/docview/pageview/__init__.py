import gettext
import logging

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise


try:
    from gi.repository import GObject
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

    # workaround so chkdeps can still be called
    class GObject(object):
        class GObject(object):
            pass


LOGGER = logging.getLogger(__name__)

_ = gettext.gettext


class Page(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'visibility_changed': (GObject.SignalFlags.RUN_LAST, None, (
            GObject.TYPE_BOOLEAN,
        )),
    }

    def __init__(self, core, doc_id, doc_url, page_idx, nb_pages):
        super().__init__()
        self.core = core
        self.doc_id = doc_id
        self.doc_url = doc_url
        self.page_idx = page_idx
        self.nb_pages = nb_pages
        self.visible = False

        self.zoom = 1.0

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageview", "pageview.glade"
        )
        self.widget = self.widget_tree.get_object("pageview_area")
        self.widget.set_visible(False)  # visible in the GTK sense
        self.widget.connect("draw", self._on_draw)

        self.renderer = None
        self._load_renderer()

    def _load_renderer(self):
        page_img_url = self.core.call_success(
            "page_get_img_url", self.doc_url, self.page_idx
        )
        assert(page_img_url is not None)

        self.renderer = self.core.call_success(
            "cairo_renderer_by_url", "page_loader", page_img_url
        )
        self.renderer.connect("getting_size", self._on_renderer_getting_size)
        self.renderer.connect("size_obtained", self._on_renderer_size)
        self.renderer.connect("img_obtained", self._on_renderer_img)

    def __str__(self):
        return "{} p{}".format(self.doc_id, self.page_idx)

    def _on_renderer_getting_size(self, renderer):
        self.core.call_all(
            "on_progress", "loading_page_sizes",
            self.page_idx / self.nb_pages,
            _("Loading page {}/{} ...").format(self.page_idx, self.nb_pages)
        )
        self.emit('getting_size')

    def _on_renderer_size(self, renderer):
        LOGGER.info(
            "Page %d: size %d x %d",
            self.page_idx, self.renderer.size[0], self.renderer.size[1]
        )
        self.widget.set_visible(True)
        self.resize()
        self.core.call_all("on_page_size_obtained", self)
        self.emit('size_obtained')

    def _on_renderer_img(self, renderer):
        assert(self.visible)
        self.refresh()
        self.core.call_all("on_page_img_obtained", self)
        self.emit('img_obtained')

    def load(self):
        self.renderer.start()

    def close(self):
        self.renderer.close()

    def get_zoom(self):
        return self.zoom

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.resize()

    def get_full_size(self):
        return self.renderer.size

    def get_size(self):
        return (
            int(self.renderer.size[0] * self.zoom),
            int(self.renderer.size[1] * self.zoom)
        )

    def resize(self):
        if self.renderer.size[0] == 0:
            return
        self.renderer.zoom = self.zoom
        size = self.get_size()
        self.widget.set_size_request(size[0], size[1])

    def refresh(self, reload=False):
        if reload:
            if self.visible:
                self.close()
                self._load_renderer()
        elif self.widget is not None:
            self.widget.queue_draw()

    def hide(self):
        self.visible = False
        self.renderer.hide()

    def show(self):
        self.visible = True
        self.renderer.render()

    def set_visible(self, visible):
        if self.visible == visible:
            return

        if visible:
            self.show()

        self.core.call_all("on_page_visibility_changed", self, visible)
        self.emit('visibility_changed', visible)

        if not visible:
            self.hide()

    def _on_draw(self, widget, cairo_ctx):
        self.renderer.draw(cairo_ctx)
        self.core.call_all("on_page_draw", cairo_ctx, self)


if GLIB_AVAILABLE:
    GObject.type_register(Page)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 10000

    def __init__(self):
        super().__init__()
        self.pages = []
        self.nb_loaded = 0

    def get_interfaces(self):
        return [
            'gtk_pageview',
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

    def chkdeps(self, out: dict):
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "work_queue_create", "page_loader", stop_on_quit=True
        )

    def doc_close(self):
        self.core.call_success("work_queue_cancel_all", "page_loader")

        for page in self.pages:
            page.close()
        self.pages = []

    def doc_reload_page_component(self, doc_id, doc_url, page_idx):
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if page_idx >= nb_pages:
            return None
        page = Page(self.core, doc_id, doc_url, page_idx, nb_pages)
        if page_idx < len(self.pages):
            self.pages[page_idx] = page
        elif page_idx == len(self.pages):
            self.pages.append(page)
        else:
            assert()
        return page

    def doc_open_components(self, out: list, doc_id, doc_url):
        self.doc_close()

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        LOGGER.info("Number of pages displayed: %s", nb_pages)
        if nb_pages is None:
            LOGGER.warning("Failed to get the number of pages in %s", doc_id)
            nb_pages = 0

        self.core.call_all("on_objref_graph")

        self.core.call_all(
            "on_perfcheck_start",
            "pageview->doc_open_components({})".format(doc_id)
        )

        self.pages = [
            Page(
                self.core, doc_id, doc_url, page_idx, nb_pages
            ) for page_idx in range(0, nb_pages)
        ]
        self.nb_loaded = 0
        for page in self.pages:
            self.core.call_all("on_new_page", page)
            page.connect("size_obtained", self._on_page_img_size_obtained)
            out.append(page)

        self.core.call_all(
            "on_perfcheck_stop",
            "pageview->doc_open_components({})".format(doc_id),
            nb_pages=nb_pages
        )

    def _on_page_img_size_obtained(self, page):
        self.nb_loaded += 1
        if self.nb_loaded < len(self.pages):
            return
        self.core.call_all("on_progress", "loading_page_sizes", 1.0)

    def pageview_refresh_all(self):
        for page in self.pages:
            page.refresh()
