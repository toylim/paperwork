import gettext
import logging

import pyocr
import pyocr.builders

import openpaperwork_core

from ... import sync


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

ID = "ocr"


class OcrTransaction(sync.BaseTransaction):
    def __init__(self, plugin, sync, total_expected=-1):
        super().__init__(plugin.core, total_expected)

        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync

        # for each document, we need to track which pages have already been
        # OCR-ed, which have been modified (cropping, rotation, ...)
        # and must be re-OCRed, and which have not been changed.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _run_ocr_on_page(self, doc_id, doc_url, page_idx, wordless_only=False):
        if wordless_only:
            has_text = self.core.call_success(
                "page_has_text_by_url", doc_url, page_idx
            )
            if has_text:
                # there is already some text on this page
                LOGGER.info(
                    "Page %s p%d has already some text. No OCR run",
                    doc_id, page_idx
                )
                self.notify_progress(
                    ID,
                    _("Document %s p%d has already some text. No OCR run") % (
                        doc_id, page_idx
                    )
                )
                return

        self.notify_progress(
            ID, _("Running OCR on document %s page %d") % (
                doc_id, page_idx
            )
        )
        self.plugin.ocr_page_by_url(doc_url, page_idx)

    def _run_ocr_on_modified_pages(self, doc_id, wordless_only=False):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        modified_pages = self.page_tracker.find_changes(doc_id, doc_url)

        for (change, page_idx) in modified_pages:
            # Run OCR on modified pages, but only if we are not synchronizing
            # with the work directory (--> if the user just added or modified
            # a document)
            if not self.sync and (change == 'new' or change == 'upd'):
                self._run_ocr_on_page(doc_id, doc_url, page_idx, wordless_only)
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

    def add_obj(self, doc_id):
        self._run_ocr_on_modified_pages(doc_id, wordless_only=True)
        super().add_obj(doc_id)

    def upd_obj(self, doc_id):
        self._run_ocr_on_modified_pages(doc_id, wordless_only=False)
        super().upd_obj(doc_id)

    def del_obj(self, doc_id):
        self.page_tracker.delete_doc(doc_id)
        super().del_obj(doc_id)

    def cancel(self):
        self.page_tracker.cancel()
        self.notify_done(ID)

    def commit(self):
        self.page_tracker.commit()
        self.notify_done(ID)


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return [
            "ocr",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return [
            {
                'interface': 'doc_tracking',
                'defaults': ['paperwork_backend.doctracker'],
            },
            {
                'interface': 'document_storage',
                'defaults': ['paperwork_backend.model.workdir'],
            },
            {
                'interface': 'ocr_settings',
                'defaults': ['paperwork_backend.pyocr'],
            },
            {
                'interface': 'page_boxes',
                'defaults': [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ],
            },
            {
                'interface': 'page_tracking',
                'defaults': ['paperwork_backend.pagetracker'],
            },
            {
                'interface': 'pillow',
                'defaults': [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ],
            },
        ]

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "doc_tracker_register", ID,
            lambda sync, total_expected=-1: OcrTransaction(
                self, sync, total_expected
            )
        )

    def ocr_page_by_url(self, doc_url, page_idx):
        LOGGER.info("Running OCR on page %d of %s", page_idx, doc_url)

        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        if doc_id is not None:
            self.core.call_one(
                "mainloop_schedule", self.core.call_all,
                "on_ocr_start", doc_id, page_idx
            )

        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        ocr_tool = pyocr.get_available_tools()[0]
        LOGGER.info("Will use tool '%s'", ocr_tool.get_name())

        ocr_langs = self.core.call_success("ocr_get_active_langs")

        img = self.core.call_success("url_to_pillow", page_img_url)

        boxes = ocr_tool.image_to_string(
            img, lang="+".join(ocr_langs),
            builder=pyocr.builders.LineBoxBuilder()
        )
        self.core.call_all("page_set_boxes_by_url", doc_url, page_idx, boxes)

        if doc_id is not None:
            self.core.call_one(
                "mainloop_schedule", self.core.call_all,
                "on_ocr_end", doc_id, page_idx
            )

        return True
