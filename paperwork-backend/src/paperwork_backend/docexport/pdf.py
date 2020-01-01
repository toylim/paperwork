import gettext
import io
import logging

import PIL
import PIL.Image

import openpaperwork_core
import openpaperwork_core.deps
import openpaperwork_core.promise

from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin
)


CAIRO_AVAILABLE = False
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
        gi.require_version('Pango', '1.0')
        gi.require_version('PangoCairo', '1.0')
        from gi.repository import Pango
        from gi.repository import PangoCairo
        PANGO_AVAILABLE = True
    except (ImportError, ValueError):
        pass


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)



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
        self.core = core
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

        img_surface = self.core.call_success(
            "pillow_to_surface", img,
            intermediate="jpeg", quality=int(self.quality * 100)
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

    def get_deps(self):
        return super().get_deps() + [
            {
                'interface': 'pillow_to_surface',
                'defaults': ['paperwork_backend.cairo.pillow'],
            },
        ]

    def chkdeps(self, out: dict):
        if not CAIRO_AVAILABLE:
            out['cairo'].update(openpaperwork_core.deps.CAIRO)
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not PANGO_AVAILABLE:
            out['pango'].update(openpaperwork_core.deps.PANGO)
