import logging

import pyocr
import pyocr.builders

import openpaperwork_core

from . import util


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.words"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return [
            "doc_text",
            "page_boxes",
            'pages',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
        ]

    def doc_get_mtime_by_url(self, out: list, doc_url):
        doc_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", doc_url
        )

        page_idx = 0
        for page_idx in range(0, doc_nb_pages):
            page_url = self.core.call_success(
                "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
            )
            if self.core.call_success("fs_exists", page_url) is None:
                continue
            out.append(self.core.call_success("fs_get_mtime", page_url))

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

    def doc_get_text_by_url(self, out: list, doc_url):
        doc_nb_pages = self.core.call_success(
            "doc_get_nb_pages_by_url", doc_url
        )

        # The following is ugly to read, but generating the whole text from
        # word boxes is a CPU-expensive process that happens often when
        # Paperwork starts and therefore it deserves some optimizations.
        # The fact is that the fastest way to concatenate
        # strings together with Python is `str.join()`.
        def line_txt_generator(line):
            return " ".join(
                [word_box.content for word_box in line.word_boxes]
            )

        def page_txt_generator(line_boxes):
            return "\n".join(
                [line_txt_generator(line_box) for line_box in line_boxes]
            )

        for page_idx in range(0, doc_nb_pages):
            line_boxes = self.page_get_boxes_by_url(doc_url, page_idx)
            if line_boxes is None:
                continue
            out.append(page_txt_generator(line_boxes))

    def page_get_boxes_by_url(self, doc_url, page_idx):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        with self.core.call_success("fs_open", page_url) as file_desc:
            box_builder = pyocr.builders.LineBoxBuilder()
            boxes = box_builder.read_file(file_desc)
            if len(boxes) > 0:
                return boxes
        with self.core.call_success("fs_open", page_url) as file_desc:
            # fallback: old format: word boxes
            # shouldn't be used anymore ...
            box_builder = pyocr.builders.WordBoxBuilder()
            boxes = box_builder.read_file(file_desc)
            if len(boxes) > 0:
                LOGGER.warning(
                    "Doc %s (page %d) uses old box format",
                    doc_url, page_idx
                )
                return boxes

    def page_set_boxes_by_url(self, doc_url, page_idx, boxes):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        with self.core.call_success("fs_open", page_url, 'w') as file_desc:
            pyocr.builders.LineBoxBuilder().write_file(file_desc, boxes)

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
