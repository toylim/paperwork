"""
Automatic page cropping using libpillowfight.find_scan_borders().
May or may not work.
"""


import gettext
import logging

import pillowfight

import openpaperwork_core


LOGGER = logging.getLogger(__name__)
_ = gettext.gettext

ID = "cropping"


class PillowfightTransaction(object):
    def __init__(self, plugin, sync, total_expected=-1):
        self.priority = plugin.PRIORITY

        self.plugin = plugin
        self.sync = sync
        self.core = plugin.core
        self.total_expected = total_expected
        self.count = 0

        # for each document, we need to track on which pages we have already
        # guessed the page borders and on which page we didn't yet.
        self.page_tracker = self.core.call_success("page_tracker_get", ID)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()

    def _get_progression(self):
        if self.total_expected <= 0:
            return 0
        return self.count / self.total_expected

    def _guess_page_borders(self, doc_id, doc_url, page_idx):
        paper_size = self.core.call_success(
            "page_get_paper_size_by_url", doc_url, page_idx
        )
        if paper_size is not None:
            # We don't want to guess page borders on PDF files since they
            # are usually already well-cropped. Also the page borders won't
            # appear in the document, so libpillowfight algorithm can only
            # fail.
            LOGGER.info(
                "Paper size for new page %d (document %s) is known."
                " --> Assuming we don't need to crop automatically the page",
                doc_id, page_idx
            )
            return

        self.core.call_one(
            "schedule", self.core.call_all,
            "on_progress", ID, self._get_progression(),
            _("Guessing page borders of document %s page %d") % (
                doc_id, page_idx
            )
        )
        self.plugin.crop_page_borders_by_url(doc_url, page_idx)

    def _guess_new_pages_borders(self, doc_id):
        doc_url = self.core.call_success("doc_id_to_url", doc_id)

        modified_pages = self.page_tracker.find_changes(doc_id, doc_url)

        for (change, page_idx) in modified_pages:
            # Guess page borders on new pages, but only if we are
            # not synchronizing with the work directory
            if not self.sync and change == 'new':
                self._guess_page_borders(doc_id, doc_url, page_idx)
            self.page_tracker.ack_page(doc_id, doc_url, page_idx)

    def add_obj(self, doc_id):
        self._guess_new_pages_borders(doc_id)
        self.count += 1

    def upd_obj(self, doc_id):
        self._guess_new_pages_borders(doc_id)
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
    PRIORITY = 4000

    def get_interfaces(self):
        return [
            "cropping",
            "syncable",  # actually satisfied by the plugin 'doctracker'
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('doc_tracking', ['paperwork_backend.doctracker']),
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
            lambda sync, total_expected=-1: PillowfightTransaction(
                self, sync, total_expected
            )
        )

    def crop_page_borders_by_url(self, doc_url, page_idx):
        doc_id = self.core.call_success("doc_url_to_id", doc_url)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_page_borders_guess_start", doc_id, page_idx
            )

        page_img_url = self.core.call_success(
            "page_get_img_url", doc_url, page_idx
        )

        img = self.core.call_success("url_to_pillow", page_img_url)

        frame = pillowfight.find_scan_borders(img)
        img = img.crop(frame)

        self.core.call_success("pillow_to_url", img, page_img_url)

        if doc_id is not None:
            self.core.call_one(
                "schedule", self.core.call_all,
                "on_page_borders_guess_end", doc_id, page_idx
            )
        return frame
