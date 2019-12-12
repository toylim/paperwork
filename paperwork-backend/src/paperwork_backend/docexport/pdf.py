import gettext
import io
import logging

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.promise

from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin
)


CAIRO_AVAILABLE = False
GDK_AVAILABLE = False
GI_AVAILABLE = False
GLIB_AVAILABLE = False
PANGO_AVAILABLE = False

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
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import Gdk
        from gi.repository import GdkPixbuf
        GDK_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        from gi.repository import GLib
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Pango', '1.0')
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import Pango
        from gi.repository import PangoCairo
        PANGO_AVAILABLE = True
    except (ImportError, ValueError):
        pass


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


def image2surface(img, intermediate="pixbuf", quality=90):
    """
    Convert a PIL image into a Cairo surface
    """
    # TODO(Jflesch): Python 3 problem
    # cairo.ImageSurface.create_for_data() raises NotImplementedYet ...

    # img.putalpha(256)
    # (width, height) = img.size
    # imgd = img.tobytes('raw', 'BGRA')
    # imga = array.array('B', imgd)
    # stride = width * 4
    #  return cairo.ImageSurface.create_for_data(
    #      imga, cairo.FORMAT_ARGB32, width, height, stride)

    # So we fall back to those methods:

    if intermediate == "pixbuf" and (
                not hasattr(GdkPixbuf.Pixbuf, 'new_from_bytes') or
                img.getbands() != ('R', 'G', 'B')
            ):
        intermediate = "png"

    if intermediate == "pixbuf":

        data = GLib.Bytes.new(img.tobytes())
        (width, height) = img.size
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            data, GdkPixbuf.Colorspace.RGB, False, 8,
            width, height, width * 3
        )
        image_surface = cairo.ImageSurface(
            cairo.FORMAT_RGB24, width, height
        )
        ctx = cairo.Context(image_surface)
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0.0, 0.0)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()
        return image_surface

    elif intermediate == "jpeg":

        if not hasattr(cairo.ImageSurface, 'set_mime_data'):
            LOGGER.warning(
                "Cairo %s does not support yet 'set_mime_data'."
                " Cannot include image as JPEG in the PDF."
                " Image will be included as PNG (much bigger)",
                cairo.version
            )
            intermediate = 'png'
        else:
            # IMPORTANT: The actual surface will be empty.
            # but mime-data will have attached the correct data
            # to the surface that supports it
            img_surface = cairo.ImageSurface(
                cairo.FORMAT_RGB24, img.size[0], img.size[1]
            )
            img_io = io.BytesIO()
            img.save(img_io, format="JPEG", quality=quality)
            img_io.seek(0)
            data = img_io.read()
            img_surface.set_mime_data(
                cairo.MIME_TYPE_JPEG, data
            )
            return img_surface

    if intermediate == "png":

        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        return cairo.ImageSurface.create_from_png(img_io)

    else:
        raise Exception(
            "image2surface(): unknown intermediate: {}".format(intermediate)
        )


class PdfDocUrlToPdfUrlExportPipe(AbstractExportPipe):
    """
    Simply copy the PDF we have.
    """
    def __init__(self, core):
        super().__init__(
            name="unmodified_pdf",
            input_types=['doc_url'],
            output_type='file_url'
        )
        self.core = core

    def can_export_doc(self, doc_url):
        pdf_url = self.core.call_success("doc_get_pdf_url_by_url", doc_url)
        return pdf_url is not None

    def get_promise(self, result='final', target_file_url=None):
        def do(doc_url):
            target = target_file_url
            if target is None:
                (target, file_desc) = self.core.call_success(
                    "fs_mktemp", prefix="paperwork-export-", suffix=".pdf",
                    mode="w"
                )
                file_desc.close()

            pdf_url = self.core.call_success("doc_get_pdf_url_by_url", doc_url)
            self.core.call_success("fs_copy", pdf_url, target)
            return target

        return openpaperwork_core.promise.Promise(self.core, do)

    def __str__(self):
        _("Original PDF")


class PdfCreator(object):
    def __init__(self, core, target_file_url, page_format, quality):
        self.page_format = page_format
        self.quality = quality

        self.file_descriptor = core.call_success(
            "fs_open", target_file_url, 'wb'
        )

        self.pdf_surface = cairo.PDFSurface(
            self.file_descriptor, self.page_format[0], self.page_format[1]
        )
        self.pdf_context = cairo.Context(self.pdf_surface)

    def set_page_size(self, img):
        img_size = img.size

        # portrait or landscape
        if (img_size[0] < img_size[1]):
            self.pdf_size = (
                min(self.page_format[0], self.page_format[1]),
                max(self.page_format[0], self.page_format[1])
            )
        else:
            self.pdf_size = (
                max(self.page_format[0], self.page_format[1]),
                min(self.page_format[0], self.page_format[1])
            )
        self.pdf_surface.set_size(self.pdf_size[0], self.pdf_size[1])

        self.img_size = (
            int(self.quality * img.size[0]),
            int(self.quality * img.size[1])
        )

        scale_factor_x = self.pdf_size[0] / self.img_size[0]
        scale_factor_y = self.pdf_size[1] / self.img_size[1]
        self.scale_factor = min(scale_factor_x, scale_factor_y)

    def paint_txt(self, boxes):
        for line in boxes:
            for word in line.word_boxes:
                box_size = (
                    (word.position[1][0] - word.position[0][0])
                    * self.scale_factor,
                    (word.position[1][1] - word.position[0][1])
                    * self.scale_factor
                )
                if 0 in box_size:
                    continue

                layout = PangoCairo.create_layout(self.pdf_context)
                layout.set_text(word.content, -1)

                txt_size = layout.get_size()
                if 0 in txt_size:
                    continue

                txt_factors = (
                    float(box_size[0]) * Pango.SCALE / txt_size[0],
                    float(box_size[1]) * Pango.SCALE / txt_size[1],
                )

                self.pdf_context.save()
                try:
                    self.pdf_context.set_source_rgb(0, 0, 0)
                    self.pdf_context.translate(
                        word.position[0][0] * self.scale_factor,
                        word.position[0][1] * self.scale_factor
                    )

                    # make the text use the whole box space
                    self.pdf_context.scale(txt_factors[0], txt_factors[1])

                    PangoCairo.update_layout(self.pdf_context, layout)
                    PangoCairo.show_layout(self.pdf_context, layout)
                finally:
                    self.pdf_context.restore()
        return self

    def paint_img(self, img):
        img = img.resize(self.img_size, PIL.Image.ANTIALIAS)

        img_surface = image2surface(
            img, intermediate="jpeg", quality=int(self.quality * 100)
        )

        self.pdf_context.save()
        try:
            self.pdf_context.identity_matrix()
            self.pdf_context.scale(self.scale_factor, self.scale_factor)
            self.pdf_context.set_source_surface(img_surface)
            self.pdf_context.paint()
        finally:
            self.pdf_context.restore()

    def next_page(self):
        self.pdf_context.show_page()

    def finish(self):
        self.pdf_surface.flush()
        self.pdf_surface.finish()
        self.file_descriptor.close()


class PagesToPdfUrlExportPipe(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="generated_pdf",
            input_types=['pages'],
            output_type='file_url'
        )
        self.core = core
        self.can_change_quality = True
        self.can_change_page_format = True

    def set_page_format(self, page_format):
        self.page_format = page_format

    def get_promise(self, result='final', target_file_url=None):
        def do(pages, target_file_url):
            if target_file_url is None:
                (target_file_url, file_desc) = self.core.call_success(
                    "fs_mktemp", prefix="paperwork-export-", suffix=".pdf",
                    mode="w"
                )
                # we need the file name, not the file descriptor
                file_desc.close()

            if result != 'final':
                pages = [pages[0]]

            creator = PdfCreator(
                self.core, target_file_url, self.page_format, self.quality
            )
            for (img, boxes) in pages:
                creator.set_page_size(img)
                creator.paint_txt(boxes)
                creator.paint_img(img)
                creator.next_page()
            creator.finish()

            return target_file_url

        return openpaperwork_core.promise.ThreadedPromise(
            self.core, do, kwargs={'target_file_url': target_file_url}
        )

    def __str__(self):
        _("Generated PDF")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            PdfDocUrlToPdfUrlExportPipe(core),
            PagesToPdfUrlExportPipe(core),
        ]

    def get_interfaces(self):
        return super().get_interfaces() + ['chkdeps']

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo']['debian'] = 'python3-gi-cairo'
            out['cairo']['fedora'] = 'python3-pycairo'
            out['cairo']['gentoo'] = 'dev-python/pycairo'  # Python 3 ?
            out['cairo']['linuxmint'] = 'python-gi-cairo'  # Python 3 ?
            out['cairo']['ubuntu'] = 'python3-gi-cairo'
            out['cairo']['suse'] = 'python-cairo'  # Python 3 ?
        if not GDK_AVAILABLE:
            out['gdk-pixbuf']['debian'] = 'gir1.2-gdkpixbuf-2.0'
            out['gdk-pixbuf']['ubuntu'] = 'gir1.2-gdkpixbuf-2.0'
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
        if not PANGO_AVAILABLE:
            out['gi.repository.Pango']['debian'] = 'gir1.2-pango-1.0'
            out['gi.repository.Pango']['ubuntu'] = 'gir1.2-pango-1.0'
