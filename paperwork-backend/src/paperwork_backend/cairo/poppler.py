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
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


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

    def pdf_page_to_cairo_surface(self, file_url, page_idx):
        task = "pdf_page_to_cairo_surface({})".format(file_url, page_idx)

        self.core.call_all("on_perfcheck_start", task)

        gio_file = Gio.File.new_for_uri(file_url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
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

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)

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
