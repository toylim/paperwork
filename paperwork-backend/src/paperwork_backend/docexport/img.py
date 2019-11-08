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

    def get_promise(self, result='final', target_file_url=None):
        def to_img_urls_and_boxes(input_data):
            if isinstance(input_data, str):
                doc_url = input_data
                nb_pages = self.core.call_success(
                    "doc_get_nb_pages_by_url", doc_url
                )
                pages = [
                    (
                        self.core.call_success(
                            "page_get_img_url", doc_url, page_idx
                        ),
                        self.core.call_success(
                            "page_get_boxes_by_url", doc_url, page_idx
                        )
                    )
                    for page_idx in range(0, nb_pages)
                ]
            else:
                if isinstance(input_data[1], int):
                    (doc_url, page_idx) = input_data
                    page_indexes = [page_idx]
                else:
                    (doc_url, page_indexes) = input_data
                pages = [
                    (
                        self.core.call_success(
                            "page_get_img_url", doc_url, page_idx
                        ),
                        self.core.call_success(
                            "page_get_boxes_by_url", doc_url, page_idx
                        ) or []
                    )
                    for page_idx in page_indexes
                ]

            for page in pages:
                assert(page[0] is not None)
                assert(page[1] is not None)
            return pages

        def load_pillow(img_urls_and_boxes):
            pages = [
                (
                    self.core.call_success("url_to_pillow", page[0]),
                    page[1],
                )
                for page in img_urls_and_boxes
            ]
            for page in pages:
                assert(page[0] is not None)
                assert(page[1] is not None)
            return pages

        promise = openpaperwork_core.promise.Promise(
            self.core, to_img_urls_and_boxes
        )
        return promise.then(
            openpaperwork_core.promise.ThreadedPromise(
                self.core, func=load_pillow
            )
        )

    def __str__(self):
        _("Page(s) to image(s) and text(s)")


class PageToImageExportPipe(AbstractExportPipe):
    def __init__(self, core, name, format, file_extension):
        super().__init__(
            name=name,
            input_types=['pages'],
            output_type='file_url'
        )
        self.can_change_quality = True
        self.format = format
        self.file_extension = file_extension
        self.core = core

    def get_promise(self, result='final', target_file_url=None):
        def page_to_image(input_data, target_file_url):
            pages = input_data

            if target_file_url is None:
                (target_file_url, file_desc) = self.core.call_success(
                    "fs_mktemp", prefix="paperwork-export-",
                    suffix=self.file_extension,
                    mode="w"
                )
                file_desc.close()

            if result != 'final':
                pages = [pages[0]]

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
        _("Black & White")


class GrayscaleExportPipe(AbstractSimpleTransformExportPipe):
    def __init__(self, core):
        super().__init__(core, "grayscale")

    def transform(self, pil_img):
        return pil_img.convert("L")

    def __str__(self):
        _("Grayscale")


class Plugin(AbstractExportPipePlugin):
    def init(self, core):
        super().init(core)
        self.pipes = [
            BlackAndWhiteExportPipe(core),
            DocToPillowBoxesExportPipe(core),
            GrayscaleExportPipe(core),
            PageToImageExportPipe(core, "bmp", "BMP", ".bmp"),
            PageToImageExportPipe(core, "gif", "GIF", ".gif"),
            PageToImageExportPipe(core, "jpeg", "JPEG", ".jpeg"),
            PageToImageExportPipe(core, "png", "PNG", ".png"),
            PageToImageExportPipe(core, "tiff", "TIFF", ".tiff"),
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
                'defaults': ['openpaperwork_core.mainloop_asyncio'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]
