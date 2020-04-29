import logging
import re

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.jpg"
PAGE_FILENAME_REGEX = re.compile(r"paper\.(\d+)\.jpg")
PAGE_FILE_FORMAT = 'JPEG'
PAGE_QUALITY = 90


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return [
            "doc_type",
            "page_img",
            'pages',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                # to provide doc_get_nb_pages_by_url()
                'interface': 'nb_pages',
                'defaults': ['paperwork_backend.model'],
            },
        ]

    def is_doc(self, doc_url):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        return True

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

    def doc_internal_get_nb_pages_by_url(self, out: list, doc_url):
        nb_pages = util.get_nb_pages(self.core, doc_url, PAGE_FILENAME_REGEX)
        if nb_pages is None:
            return
        out.append(nb_pages)

    def page_get_img_url(self, doc_url, page_idx, write=False):
        if write:
            self.core.call_success("fs_mkdir_p", doc_url)
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if not write and self.core.call_success("fs_exists", page_url) is None:
            return None
        return page_url

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
