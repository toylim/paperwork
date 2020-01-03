import io
import logging

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps


LOGGER = logging.getLogger(__name__)


def surface2image(core, surface):
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

    core.call_all("on_perfcheck_start", "surface2image")

    img_io = io.BytesIO()
    surface.write_to_png(img_io)
    img_io.seek(0)
    img = PIL.Image.open(img_io)
    img.load()

    if "A" not in img.getbands():
        core.call_all("on_perfcheck_stop", "surface2image", size=img.size)
        return img

    img_no_alpha = PIL.Image.new("RGB", img.size, (255, 255, 255))
    img_no_alpha.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    core.call_all(
        "on_perfcheck_stop", "surface2image", size=img_no_alpha.size
    )
    return img_no_alpha


class Plugin(openpaperwork_core.PluginBase):
    FILE_EXTENSION = ".pdf"

    def get_interfaces(self):
        return [
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

    def url_to_pillow(self, file_url):
        (file_url, page_idx) = self._check_is_pdf(file_url)
        if file_url is None:
            return None

        pillow = self.core.call_one(  # Poppler is not really thread safe
            "mainloop_execute", self._url_to_pillow, file_url, page_idx
        )
        return pillow

    def cairo_surface_to_pillow(self, surface):
        return surface2image(self.core, surface)

    def _url_to_pillow(self, file_url, page_idx):
        surface = self.core.call_success(
            "pdf_page_to_cairo_surface", file_url, page_idx
        )

        img = surface2image(self.core, surface)
        img.load()
        return img

    def url_to_pillow_promise(self, file_url):
        return openpaperwork_core.promise.Promise(
            self.core, self.url_to_pillow, args=(file_url,)
        )

    def pillow_to_url(self, *args, **kwargs):
        # It could be implemented, but there is no known use-case.
        return None
