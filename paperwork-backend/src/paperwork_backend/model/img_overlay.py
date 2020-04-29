"""
Let other plugins replace a page image without actually smashing the original
image. Also provide a method to drop the modified version of a page and revert
to the original only.
"""

import logging
import re

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.edited.jpg"
PAGE_FILENAME_REGEX = re.compile(r"paper\.(\d+)\.edited.jpg")
PAGE_FILE_FORMAT = 'JPEG'
PAGE_QUALITY = 90


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 1000  # must have a higher priority than model.img / model.pdf

    def get_interfaces(self):
        return [
            "page_img",
            "page_reset",
            'pages',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def doc_internal_get_mtime_by_url(self, out: list, doc_url):
        mtime = util.get_doc_mtime(self.core, doc_url, PAGE_FILENAME_REGEX)
        if mtime is None:
            return
        out.append(mtime)

    def page_internal_get_mtime_by_url(self, out: list, doc_url, page_idx):
        mtime = util.get_page_mtime(
            self.core, doc_url, page_idx, PAGE_FILENAME_FMT
        )
        if mtime is None:
            return
        out.append(mtime)

    def page_internal_get_hash_by_url(self, out: list, doc_url, page_idx):
        h = util.get_page_hash(self.core, doc_url, page_idx, PAGE_FILENAME_FMT)
        if h is None:
            return
        out.append(h)

    def page_get_img_url(self, doc_url, page_idx, write=False):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is not None:
            return page_url

        if not write:
            return None

        # caller wants to modify or create a page
        # check if we already have an original image. If so, we return our
        # URL. Otherwise, we let the caller write the original image first.
        if self.core.call_success(
                    "page_get_img_url", doc_url, page_idx, write=False
                ) is not None:
            # has already an original page (or even an edited one)
            # --> return our URL
            return page_url

        # let the caller write an original page (see model.img)
        return None

    def page_delete_by_url(self, doc_url, page_idx):
        return util.delete_page_file(
            self.core, PAGE_FILENAME_FMT, doc_url, page_idx
        )

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        return util.move_page_file(
            self.core, PAGE_FILENAME_FMT,
            source_doc_url, source_page_idx,
            dest_doc_url, dest_page_idx
        )

    def page_reset_by_url(self, doc_url, page_idx):
        """
        Reset a page image to its original content. In other word, we simply
        delete the edited image so the original one takes over again
        (see model.img).
        """
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url):
            self.core.call_all("fs_unlink", page_url, trash=False)
