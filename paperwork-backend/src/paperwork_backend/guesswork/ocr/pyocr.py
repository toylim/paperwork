import gettext
import logging

import pyocr
import pyocr.builders

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

ID = "ocr"


class OcrTransaction(object):
    def __init__(self, plugin, sync, total_expected=-1):
        self.plugin = plugin
        self.sync = sync
        self.core = plugin.core
        self.total_expected = total_expected
        self.count = 0

        # for each document, we need to track which pages have already been
        # OCR-ed, which have been modified (cropping, rotation, ...)
        # and must be re-OCRed, and which have not been changed.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def _run_ocr_on_page(self, doc_id, doc_url, page_idx, wordless_only=False):
        if wordless_only:
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
                    "on_progress", ID, self._get_progression(),
                    _("Document %s p%d has already some text. No OCR run") % (
                        doc_id, page_idx
                    )
                )
                return

        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", ID, self._get_progression(),
            _("Running OCR on document %s page %d") % (
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
        self.count += 1

    def upd_obj(self, doc_id):
        self._run_ocr_on_modified_pages(doc_id, wordless_only=False)
        self.count += 1

    def del_obj(self, doc_id):
        self.page_tracker.delete_doc(doc_id)
        self.count += 1

    def unchanged_obj(self, doc_id):
        # not used here
        self.count += 1

    def cancel(self):
        self.page_tracker.cancel()

    def commit(self):
        self.page_tracker.commit()
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", ID, 1.0
        )


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000

    def get_interfaces(self):
        return [
            "ocr",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_tracking', ['paperwork_backend.doctracker']),
                ('document_storage', ['paperwork_backend.model.workdir']),
                ('ocr_settings', ['paperwork_backend.pyocr']),
                ('page_boxes', [
                    'paperwork_backend.model.hocr',
                    'paperwork_backend.model.pdf',
                ]),
                ('page_tracking', ['paperwork_backend.pagetracker']),
                ('pillow', [
                    'paperwork_backend.pillow.img',
                    'paperwork_backend.pillow.pdf',
                ]),
            ]
        }

    def init(self, core):
        super().init(core)
        self.core.call_all(
            "doc_tracker_register", ID,
            lambda sync, total_expected=-1: OcrTransaction(
                self, sync, total_expected
            )
        )

    def ocr_page_by_url(self, doc_url, page_idx):
        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_start", doc_id, page_idx
            )

        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )
        ocr_tool = pyocr.get_available_tools()[0]
        LOGGER.info("Will use tool '%s'", ocr_tool.get_name())

        ocr_lang = self.core.call_success("ocr_get_lang")

        img = self.core.call_success("url_to_pillow", page_img_url)

        boxes = ocr_tool.image_to_string(
            img, lang=ocr_lang,
            builder=pyocr.builders.LineBoxBuilder()
        )
        self.core.call_all("page_set_boxes_by_url", doc_url, page_idx, boxes)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_ocr_end", doc_id, page_idx
            )

        return True
