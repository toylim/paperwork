import gettext
import logging

import pyocr
import pyocr.builders

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

ID = "orientation_guesser"


class OrientationTransaction(object):
    def __init__(self, plugin, sync, total_expected=-1):
        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync
        self.core = plugin.core
        self.total_expected = total_expected
        self.count = 0

        # for each document, we need to track on which pages we have already
        # guessed the orientation and on which page we didn't yet.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def _guess_page_orientation(self, doc_id, doc_url, page_idx):
        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", ID, self._get_progression(),
            _("Guessing orientation on document %s page %d") % (
                doc_id, page_idx
            )
        )
        self.plugin.guess_page_orientation_by_url(doc_url, page_idx)

    def _guess_new_page_orientations(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        modified_pages = self.page_tracker.find_changes(doc_id, doc_url)

        for (change, page_idx) in modified_pages:
            # Guess page orientation on new pages, but only if we are
            # not synchronizing with the work directory
            if not self.sync and change == 'new':
                self._guess_page_orientation(doc_id, doc_url, page_idx)
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

    def add_obj(self, doc_id):
        self._guess_new_page_orientations(doc_id)
        self.count += 1

    def upd_obj(self, doc_id):
        self._guess_new_page_orientations(doc_id)
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
    PRIORITY = 2000

    def get_interfaces(self):
        return [
            "orientation_guesser",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_tracking', ['paperwork_backend.doctracker']),
                ('ocr_settings', ['paperwork_backend.pyocr']),
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
            lambda sync, total_expected=-1: OrientationTransaction(
                self, sync, total_expected
            )
        )

    def guess_page_orientation_by_url(self, doc_url, page_idx):
        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_orientation_guess_start", doc_id, page_idx
            )

        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )

        for ocr_tool in pyocr.get_available_tools():
            LOGGER.info(
                "Orientation guessing: Will use tool '%s'",
                ocr_tool.get_name()
            )
            if ocr_tool.can_detect_orientation():
                break
            LOGGER.warning(
                "Orientation guessing: Tool '%s' cannot detect orientation",
                ocr_tool.get_name()
            )
        else:
            LOGGER.warning(
                "Orientation guessing: No tool found able to detect"
                " orientation"
            )
            return None

        ocr_lang = self.core.call_success("ocr_get_lang")

        img = self.core.call_success("url_to_pillow", page_img_url)

        try:
            r = ocr_tool.detect_orientation(img, lang=ocr_lang)
        except pyocr.PyocrException as exc:
            LOGGER.warning(
                "Orientation guessing: Failed to guess orientation",
                exc_info=exc
            )
            return None

        angle = r['angle']
        img = img.rotate(angle)

        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx, write=True
        )
        self.core.call_success("pillow_to_url", img, page_img_url)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_orientation_guess_end", doc_id, page_idx
            )

        return angle
