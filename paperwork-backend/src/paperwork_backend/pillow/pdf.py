import io
import logging

try:
    import cairo
    CAIRO_AVAILABLE = True
except (ImportError, ValueError):
    CAIRO_AVAILABLE = False

try:
    import gi
    gi.require_version('Poppler', '0.18')
    GI_AVAILABLE = True
except (ImportError, ValueError):
    GI_AVAILABLE = False

try:
    from gi.repository import Gio
    GLIB_AVAILABLE = True
except (ImportError, ValueError):
    GLIB_AVAILABLE = False

try:
    from gi.repository import Poppler
    POPPLER_AVAILABLE = True
except (ImportError, ValueError):
    POPPLER_AVAILABLE = False

import PIL
import PIL.Image

import openpaperwork_core

# TODO(Jflesch): bad
import paperwork_backend.model.pdf


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
            'pillow',
        ]

    def url_to_pillow(self, file_url):
        if (self.FILE_EXTENSION + "#page=") not in file_url.lower():
            return None

        (file_url, page_idx) = file_url.rsplit("#page=", 1)
        page_idx = int(page_idx) - 1

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
        ctx.scale(factor_w, factor_h)
        page.render(ctx)

        return surface2image(surface)

    def pillow_to_url(self, *args, **kwargs):
        # It could be implemented, but there is no known use-case.
        return None

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo']['debian'] = 'python3-gi-cairo'
            out['cairo']['fedora'] = 'python3-pycairo'
            out['cairo']['gentoo'] = 'dev-python/pycairo'  # Python 3 ?
            out['cairo']['linuxmint'] = 'python-gi-cairo'  # Python 3 ?
            out['cairo']['ubuntu'] = 'python3-gi-cairo'
            out['cairo']['suse'] = 'python-cairo'  # Python 3 ?
        if not GI_AVAILABLE:
            out['gi']['debian'] = 'python3-gi'
            out['gi']['fedora'] = 'python3-gobject-base'
            out['gi']['gentoo'] = 'dev-python/pygobject'  # Python 3 ?
            out['gi']['linuxmint'] = 'python3-gi'
            out['gi']['ubuntu'] = 'python3-gi'
            out['gi']['suse'] = 'python-gobject'  # Python 3 ?
        if not GLIB_AVAILABLE:
            out['gi.repository.GLib']['debian'] = 'gir1.2-glib-2.0'
            out['gi.repository.GLib']['ubuntu'] = 'gir1.2-glib-2.0'
        if not POPPLER_AVAILABLE:
            out['gi.repository.Poppler']['debian'] = 'gir1.2-poppler-0.18'
            out['gi.repository.Poppler']['fedora'] = 'poppler-glib'
            out['gi.repository.Poppler']['gentoo'] = 'app-text/poppler'
            out['gi.repository.Poppler']['linuxmint'] = 'gir1.2-poppler-0.18'
            out['gi.repository.Poppler']['ubuntu'] = 'gir1.2-poppler-0.18'
            out['gi.repository.Poppler']['suse'] = 'typelib-1_0-Poppler-0_18'
