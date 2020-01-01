import io
import logging
import time

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps

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
        gi.require_version('Poppler', '0.18')
        GI_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)


def surface2image(surface):
    """
    Convert a cairo surface into a PIL image
    """
    # XXX(Jflesch): Python 3 problem
    # cairo.ImageSurface.get_data() raises NotImplementedYet ...

    # import PIL.ImageDraw
    #
    # if surface is None:
    #     return None
    # dimension = (surface.get_width(), surface.get_height())
    # img = PIL.Image.frombuffer("RGBA", dimension,
    #                            surface.get_data(), "raw", "BGRA", 0, 1)
    #
    # background = PIL.Image.new("RGB", img.size, (255, 255, 255))
    # background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    # return background

    img_io = io.BytesIO()
    surface.write_to_png(img_io)
    img_io.seek(0)
    img = PIL.Image.open(img_io)
    img.load()

    if "A" not in img.getbands():
        return img

    img_no_alpha = PIL.Image.new("RGB", img.size, (255, 255, 255))
    img_no_alpha.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return img_no_alpha


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSION = ".pdf"

    def get_interfaces(self):
        return [
            'chkdeps',
            'page_img_size',
            'pillow',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'pdf_cairo_url',
                'defaults': ['paperwork_backend.cairo.poppler'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

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

        start = time.time()
        gio_file = Gio.File.new_for_uri(file_url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
        page = doc.get_page(page_idx)

        base_size = page.get_size()
        size = (  # scale up because default size if too small for reading
            int(base_size[0]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
            int(base_size[1]) * paperwork_backend.model.pdf.PDF_RENDER_FACTOR,
        )

        stop = time.time()
        LOGGER.info(
            "Took %dms to get %s p%d size: %s",
            (stop - start) * 1000, file_url, page_idx, size
        )
        return pillow

    def url_to_pillow(self, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None

        pillow = self.core.call_one(  # Poppler is not really thread safe
            "mainloop_execute", self._url_to_pillow, file_url, page_idx
        )
        return pillow

    def _url_to_pillow(self, file_url, page_idx):
        surface = self.core.call_success(
            "pdf_page_to_cairo_surface", file_url, page_idx
        )

        start = time.time()
        img = surface2image(surface)
        img.load()
        stop = time.time()
        LOGGER.info(
            "Took %dms to convert %s p%d"
            " from Cairo ImageSurface to a pillow image",
            (stop - start) * 1000, file_url, page_idx
        )
        return img

    def url_to_pillow_promise(self, file_url):
        return openpaperwork_core.promise.Promise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, *args, **kwargs):
        # It could be implemented, but there is no known use-case.
        return None

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'].update(openpaperwork_core.deps.POPPLER)
