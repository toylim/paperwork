import logging

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

# TODO(Jflesch): bad
import paperwork_backend.model.pdf


CAIRO_AVAILABLE = False
GI_AVAILABLE = False
GLIB_AVAILABLE = False
POPPLER_AVAILABLE = False

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    pass

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        from gi.repository import GObject
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        # dummy so chkdeps can still be called
        class GObject(object):
            class GObject(object):
                pass

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)
DELAY = 0.01
POPPLER_DOCS = {}


class ImgSurface(object):
    # wrapper so it can be weakref
    def __init__(self, surface):
        self.surface = surface


class CairoRenderer(GObject.GObject):
    __gsignals__ = {
        'getting_size': (GObject.SignalFlags.RUN_LAST, None, ()),
        'size_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
        'img_obtained': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, core, work_queue_name, file_url, page_idx):
        global POPPLER_DOCS

        super().__init__()
        self.core = core
        self.work_queue_name = work_queue_name
        self.file_url = file_url
        self.page_idx = page_idx
        self.visible = False
        self.size = (0, 0)
        self.zoom = 1.0

        if file_url in POPPLER_DOCS:
            (doc, refcount) = POPPLER_DOCS[file_url]
        else:
            LOGGER.info("Opening PDF file {}".format(file_url))
            gio_file = Gio.File.new_for_uri(file_url)
            doc = Poppler.Document.new_from_gfile(gio_file, password=None)
            self.core.call_all("on_objref_track", doc)
            refcount = 0
        POPPLER_DOCS[file_url] = (doc, refcount + 1)

        self.page = doc.get_page(page_idx)

        promise = openpaperwork_core.promise.Promise(
            self.core, self.emit, args=("getting_size",)
        )
        promise = promise.then(openpaperwork_core.promise.Promise(
            self.core, self.page.get_size
        ))
        promise = promise.then(lambda size: (
            size[0] * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            size[1] * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        ))
        promise.then(self._set_size)

        if page_idx % 25 == 0:
            # Gives back a bit of CPU time to GTK so the GUI remains
            # usable, but not too much so we don't recompute the layout too
            # often
            promise = promise.then(openpaperwork_core.promise.DelayPromise(
                core, DELAY
            ))

        self.get_size_promise = promise

    def __str__(self):
        return "CairoRenderer({} p{})".format(self.file_url, self.page_idx)

    def _set_size(self, size):
        if self.page is None:
            # Document has been closed while we looked for its size
            return
        self.size = size
        self.emit('size_obtained')
        if self.visible:
            self.render(force=True)

    def start(self):
        self.core.call_success(
            "work_queue_add_promise",
            self.work_queue_name, self.get_size_promise
        )

    def render(self, force=False):
        if self.visible and not force:
            return
        self.visible = True
        if self.size == (0, 0):
            return
        self.emit('img_obtained')

    def hide(self):
        self.visible = False

    def close(self):
        global POPPLER_DOCS
        self.hide()
        self.page = None
        self.size = (0, 0)
        (doc, refcount) = POPPLER_DOCS[self.file_url]
        refcount -= 1
        if refcount > 0:
            POPPLER_DOCS[self.file_url] = (doc, refcount)
            return
        LOGGER.info("Closing PDF file {}".format(self.file_url))
        POPPLER_DOCS.pop(self.file_url)

    def draw(self, cairo_ctx):
        if not self.visible or self.page is None or self.size[0] == 0:
            return

        task = "pdf_to_cairo_draw({}, p{})".format(
            self.file_url, self.page_idx
        )
        self.core.call_all("on_perfcheck_start", task)

        cairo_ctx.save()
        try:
            cairo_ctx.set_source_rgb(1.0, 1.0, 1.0)
            cairo_ctx.rectangle(0, 0, self.size[0], self.size[1])
            cairo_ctx.clip()
            cairo_ctx.paint()

            cairo_ctx.scale(
                paperwork_backend.model.pdf.PDF_RENDER_FACTOR *
                self.zoom,
                paperwork_backend.model.pdf.PDF_RENDER_FACTOR *
                self.zoom,
            )
            self.page.render(cairo_ctx)
        finally:
            cairo_ctx.restore()

        self.core.call_all("on_perfcheck_stop", task, size=self.size)


if GLIB_AVAILABLE:
    GObject.type_register(CairoRenderer)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000
    FILE_EXTENSION = ".pdf"

    def get_interfaces(self):
        return [
            'cairo_url',
            'chkdeps',
            'page_img_size',
            'pdf_cairo_url',
        ]

    def get_deps(self):
        return []

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GI_AVAILABLE:
            out['gi'] = openpaperwork_core.deps.GI
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'] = openpaperwork_core.deps.POPPLER

    def _check_is_pdf(self, file_url):
        if (self.FILE_EXTENSION + "#page=") not in file_url.lower():
            return (None, None)
        if "#" in file_url:
            (file_url, page_idx) = file_url.rsplit("#page=", 1)
            page_idx = int(page_idx) - 1
        else:
            page_idx = 0
        return (file_url, page_idx)

    def url_to_img_size(self, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None

        task = "url_to_img_size({})".format(file_url)
        self.core.call_all("on_perfcheck_start", task)
        gio_file = Gio.File.new_for_uri(file_url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
        page = doc.get_page(page_idx)

        base_size = page.get_size()
        size = (  # scale up because default size if too small for reading
            int(base_size[0]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            int(base_size[1]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        )

        self.core.call_all("on_perfcheck_stop", task, size=size)
        return size

    def url_to_img_size_promise(self, file_url):
        (_file_url, page_idx) = self._check_is_pdf(file_url)
        if _file_url is None:
            return None

        return openpaperwork_core.promise.Promise(
            self.core, self.url_to_img_size, args=(file_url,)
        )

    def pdf_page_to_cairo_surface(self, file_url, page_idx):
        task = "pdf_page_to_cairo_surface({})".format(file_url, page_idx)

        self.core.call_all("on_perfcheck_start", task)

        gio_file = Gio.File.new_for_uri(file_url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
        self.core.call_all("on_objref_track", doc)
        page = doc.get_page(page_idx)

        base_size = page.get_size()
        size = (  # scale up because default size if too small for reading
            int(base_size[0]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            int(base_size[1]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        )

        width = int(size[0])
        height = int(size[1])
        factor_w = width / base_size[0]
        factor_h = height / base_size[1]

        surface = ImgSurface(cairo.ImageSurface(
            cairo.FORMAT_ARGB32, width, height
        ))
        self.core.call_all("on_objref_track", surface)
        ctx = cairo.Context(surface.surface)

        ctx.save()
        try:
            ctx.set_source_rgb(1.0, 1.0, 1.0)
            ctx.rectangle(0, 0, width, height)
            ctx.clip()
            ctx.paint()

            ctx.scale(factor_w, factor_h)
            page.render(ctx)
        finally:
            ctx.restore()

        self.core.call_all("on_perfcheck_stop", task, size=(width, height))
        return surface

    def url_to_cairo_surface(self, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return self.pdf_page_to_cairo_surface(file_url, page_idx)

    def url_to_cairo_surface_promise(self, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return openpaperwork_core.promise.Promise(
            self.core, self.pdf_page_to_cairo_surface,
            args=(file_url, page_idx)
        )

    def cairo_renderer_by_url(self, work_queue_name, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None
        return CairoRenderer(self.core, work_queue_name, file_url, page_idx)
