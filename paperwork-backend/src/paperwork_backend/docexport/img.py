import gettext
import logging

import openpaperwork_core
import openpaperwork_core.promise


from . import (
    AbstractExportPipe,
    AbstractExportPipePlugin,
    AbstractSimpleTransformExportPipe
)


_ = gettext.gettext
LOGGER = logging.getLogger(__name__)


class DocToPillowBoxesExportPipe(AbstractExportPipe):
    def __init__(self, core):
        super().__init__(
            name="img_boxes",
            input_types=['doc_url', 'page_url'],
            output_type='pages'
        )
        self.core = core

    def can_export_doc(self, doc_url):
        return True

    def can_export_page(self, doc_url, page_nb):
        return True

    def get_estimated_size_factor(self, input_data):
        if isinstance(input_data, str):
            return self.core.call_success(
                "doc_get_nb_pages_by_url", input_data
            )
        if isinstance(input_data[1], int):
            return 1
        return len(input_data[1])

    def get_promise(self, result='final', target_file_url=None):
        def _to_img_urls_to_boxes(doc_url, page_indexes):
            page_indexes = list(page_indexes)

            self.core.call_success(
                "mainloop_schedule", self.core.call_all,
                "on_progress", "export", 0.0,
                _("Exporting %s to %s ...") % (doc_url, target_file_url)
            )
            try:
                for (idx, page_idx) in enumerate(page_indexes):
                    self.core.call_success(
                        "mainloop_schedule", self.core.call_all,
                        "on_progress", "export", idx / len(page_indexes),
                        _("Exporting %s p%d to %s ...") % (
                            doc_url, page_idx + 1, target_file_url
                        )
                    )
                    r = (
                        self.core.call_success(
                            "page_get_img_url", doc_url, page_idx
                        ),
                        (doc_url, page_idx)
                    )
                    assert(r[0] is not None)
                    yield r
            finally:
                self.core.call_success(
                    "mainloop_schedule", self.core.call_all,
                    "on_progress", "export", 1.0
                )

        def to_img_urls_and_boxes(input_data):
            if isinstance(input_data, str) and result == 'preview':
                input_data = (input_data, 0)

            if isinstance(input_data, str):
                doc_url = input_data
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                return _to_img_urls_to_boxes(doc_url, range(0, nb_pages))
            else:
                if isinstance(input_data[1], int):
                    (doc_url, page_idx) = input_data
                    page_indexes = [page_idx]
                elif result == 'preview':
                    doc_url = input_data[0]
                    page_indexes = [input_data[1][0]]
                else:
                    (doc_url, page_indexes) = input_data
                return _to_img_urls_to_boxes(doc_url, page_indexes)

        def load_pillow(img_urls_and_boxes):
            for page in img_urls_and_boxes:
                yield (
                    self.core.call_success("url_to_pillow", page[0]),
                    self.core.call_success(
                        "page_get_boxes_by_url", *page[1]
                    ) or [],
                )

        promise = openpaperwork_core.promise.Promise(
            self.core, to_img_urls_and_boxes
        )
        promise = promise.then(load_pillow)
        return promise

    def __str__(self):
        return _("Page(s) to image(s) and text(s)")


class PageToImageExportPipe(AbstractExportPipe):
    def __init__(self, core, name, format, file_extensions, mime, has_quality):
        super().__init__(
            name=name,
            input_types=['pages'],
            output_type='file_url'
        )
        self.can_change_quality = has_quality
        self.format = format
        self.file_extensions = file_extensions
        self.mime = mime
        self.core = core

    def get_promise(self, result='final', target_file_url=None):
        def page_to_image(input_data, target_file_url):
            pages = input_data

            if target_file_url is None:
                (target_file_url, file_desc) = self.core.call_success(
                    "fs_mktemp", prefix="paperwork-export-",
                    suffix="." + self.file_extensions[0],
                    mode="w"
                )
                file_desc.close()

            for (page_idx, (pil_img, boxes)) in enumerate(pages):
                out = target_file_url
                if page_idx != 0:
                    out = out.rsplit(".", 1)
                    out = "{}_{}.{}".format(out[0], page_idx, out[1])

                self.core.call_success(
                    "pillow_to_url", pil_img, out, format=self.format,
                    quality=self.quality
                )

            return target_file_url

        return openpaperwork_core.promise.ThreadedPromise(
            self.core, page_to_image,
            kwargs={'target_file_url': target_file_url}
        )

    def get_output_mime(self):
        return (self.mime, self.file_extensions)

    def __str__(self):
        return _("Image file ({})".format(self.format))


class BlackAndWhiteExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "bw")

    def transform(self, pil_img):
        pil_img = pil_img.convert("L")  # to grayscale
        pil_img = pil_img.point(lambda x: 0 if x < 128 else 255, '1')
        return pil_img

    def __str__(self):
        return _("Black & White")


class GrayscaleExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "grayscale")

    def transform(self, pil_img):
        return pil_img.convert("L")

    def __str__(self):
        return _("Grayscale")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            BlackAndWhiteExportPipe(core),
            DocToPillowBoxesExportPipe(core),
            GrayscaleExportPipe(core),
            PageToImageExportPipe(
                core, "bmp", "BMP", ("bmp",), "image/x-ms.bmp", False
            ),
            PageToImageExportPipe(
                core, "gif", "GIF", ("gif",), "image/gif", False
            ),
            PageToImageExportPipe(
                core, "jpeg", "JPEG", ("jpeg", "jpg"), "image/jpeg", True
            ),
            PageToImageExportPipe(
                core, "png", "PNG", ("png",), "image/png", False
            ),
            PageToImageExportPipe(
                core, "tiff", "TIFF", ("tiff",), "image/tiff", False
            ),
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_text',
                'defaults': [
                    # load also model.img because model.pdf will
                    # satisfy the interface 'page_img' anyway
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'page_img',
                'defaults': [
                    # load also model.hocr because model.pdf will
                    # satisfy the interface 'doc_text' anyway
                    'paperwork_backend.model.img',
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]
