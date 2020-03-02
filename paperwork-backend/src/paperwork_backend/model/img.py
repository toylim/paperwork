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
            }
        ]

    def is_doc(self, doc_url):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        return True

    def doc_get_mtime_by_url(self, out: list, doc_url):
        page_idx = 0
        while self.page_get_img_url(doc_url, page_idx) is not None:
            page_url = self.core.call_success(
                "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
            )
            if self.core.call_success("fs_exists", page_url) is None:
                return
            out.append(self.core.call_success("fs_get_mtime", page_url))
            page_idx += 1

    def page_get_mtime_by_url(self, out: list, doc_url, page_idx):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return
        out.append(self.core.call_success("fs_get_mtime", page_url))

    def page_get_hash_by_url(self, out: list, doc_url, page_idx):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return
        out.append(self.core.call_success("fs_hash", page_url))

    def doc_get_nb_pages_by_url(self, doc_url):
        files = self.core.call_success("fs_listdir", doc_url)
        if files is None:
            return None
        nb_pages = -1
        for f in files:
            f = self.core.call_success("fs_basename", f)
            match = PAGE_FILENAME_REGEX.match(f)
            if match is None:
                continue
            nb_pages = max(nb_pages, int(match.group(1)))
        if nb_pages < 0:
            return None
        return nb_pages

    def page_get_img_url(self, doc_url, page_idx, write=False):
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
