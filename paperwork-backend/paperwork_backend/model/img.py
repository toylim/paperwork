import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.jpg"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return [
            "doc_type",
            "page_img",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio']),
            ]
        }

    def is_doc(self, doc_url):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        return True

    def doc_get_mtime_by_url(self, out, doc_url):
        page_idx = 0
        while self.page_get_img_url(doc_url, page_idx) is not None:
            out.append(self.core.call_success(
                "fs_get_mtime",
                doc_url + "/" + PAGE_FILENAME_FMT.format(page_idx + 1)
            ))
            page_idx += 1

    def doc_get_nb_pages_by_url(self, doc_url):
        page_idx = 0
        while self.page_get_img_url(doc_url, page_idx) is not None:
            page_idx += 1
        if page_idx <= 0:
            return None
        return page_idx

    def page_get_img_url(self, doc_url, page_idx):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        return page_url
