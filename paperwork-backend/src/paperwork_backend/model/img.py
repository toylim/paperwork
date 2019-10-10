import logging

import PIL.Image

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.jpg"
PAGE_FILE_FORMAT = 'JPEG'
PAGE_QUALITY = 90


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return [
            "doc_img_import",
            "doc_type",
            "page_img",
            'pages',
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

    def doc_get_mtime_by_url(self, out: list, doc_url):
        page_idx = 0
        while self.page_get_img_url(doc_url, page_idx) is not None:
            out.append(self.core.call_success(
                "fs_get_mtime",
                self.core.call_success(
                    "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
                )
            ))
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

    def doc_img_import_file_by_id(self, src_file_url, doc_id=None):
        # make sure the image is valid before making a mess in the work
        # directory
        with self.core.call_success("fs_open", src_file_url, 'rb') as fd:
            img = PIL.Image.open(fd)
            img.load()
            del img

        if doc_id is None:
            # new document
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
        else:
            # update existing one
            doc_url = self.core.call_success("doc_id_to_url", doc_id)

        self.core.call_success("fs_mkdir_p", doc_url)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0

        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(nb_pages + 1)
        )
        self.core.call_success("fs_copy", src_file_url, page_url)
        return (doc_id, doc_url)

    def doc_img_import_img_by_id(self, img, doc_id=None):
        if doc_id is None:
            # new document
            (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
        else:
            # update existing one
            doc_url = self.core.call_success("doc_id_to_url", doc_id)

        self.core.call_success("fs_mkdir_p", doc_url)

        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            nb_pages = 0

        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(nb_pages + 1)
        )
        with self.core.call_success("fs_open", page_url, mode='wb') as fd:
            img.save(fd, format=PAGE_FILE_FORMAT, quality=PAGE_QUALITY)
        return (doc_id, doc_url)

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
