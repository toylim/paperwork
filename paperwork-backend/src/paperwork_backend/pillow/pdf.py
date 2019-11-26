import io
import logging

import cairo
import gi
gi.require_version('Poppler', '0.18')
from gi.repository import Gio
from gi.repository import Poppler
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
        return ['pillow']

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
