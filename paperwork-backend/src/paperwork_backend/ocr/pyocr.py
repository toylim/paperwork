import gettext
import glob
import locale
import logging
import os

import pycountry
import pyocr
import pyocr.builders

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext


class OcrTransaction(object):
    def __init__(self, plugin, total_expected=-1):
        self.plugin = plugin
        self.core = plugin.core
        self.total_expected = total_expected
        self.count = 0

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def add_obj(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        for page_idx in range(0, nb_pages):
            current_boxes = self.core.call_success(
                "page_get_boxes_by_url", doc_url, page_idx
            )
            if current_boxes is not None:
                current_boxes = list(current_boxes)
            if current_boxes is not None and len(current_boxes) > 0:
                # there is already some text on this page
                LOGGER.info(
                    "Page %s p%d has already some text. No OCR run",
                    doc_id, page_idx
                )
                self.core.call_one(
                    "schedule", self.core.call_all,
                    "on_progress", "ocr", self._get_progression(),
                    _("Document %s p%d has already some text. No OCR run") % (
                        doc_id, page_idx
                    )
                )
                continue
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_progress", "ocr", self._get_progression(),
                _("Running OCR on document %s page %d") % (
                    doc_id, page_idx
                )
            )
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_start", doc_id, page_idx
            )
            self.plugin.ocr_page_by_url(doc_url, page_idx)
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_end", doc_id, page_idx
            )

        self.count += 1

    def upd_obj(self, doc_id):
        # not used here
        self.count += 1

    def del_obj(self, doc_id):
        # not used here
        self.count += 1

    def unchanged_obj(self, doc_id):
        # not used here
        self.count += 1

    def cancel(self):
        pass

    def commit(self):
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", "ocr", 1.0
        )


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return [
            "chkdeps",
            "ocr",
            "syncable",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('document_storage', ['paperwork_backend.model.workdir',]),
                ('mainloop', ['openpaperwork_core.mainloop_asyncio',]),
                ('ocr_settings', ['paperwork_backend.pyocr',]),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]),
                ('page_boxes', [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ]),
            ]
        }

    def ocr_page_by_url(self, doc_url, page_idx):
        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        ocr_tool = pyocr.get_available_tools()[0]
        LOGGER.info("Will use tool '%s'" % (ocr_tool.get_name()))

        ocr_lang = self.core.call_success("ocr_get_lang")

        img = self.core.call_success("url_to_pillow", page_img_url)

        boxes = ocr_tool.image_to_string(
            img, lang=ocr_lang,
            builder=pyocr.builders.LineBoxBuilder()
        )
        self.core.call_all("page_set_boxes_by_url", doc_url, page_idx, boxes)

    def doc_transaction_start(self, out: list, total_expected=-1):
        # we monitor document transactions just so we can OCR freshly
        # added documents.
        out.append(OcrTransaction(self, total_expected))

    def sync(self, promises):
        # Nothing to do in that case, just here to satisfy the interface
        # 'syncable'
        pass
