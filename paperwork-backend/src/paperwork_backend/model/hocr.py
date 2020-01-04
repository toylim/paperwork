import logging
import xml.etree.cElementTree as etree

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

        for page_idx in range(0, doc_nb_pages):
            text = self.page_get_text_by_url(doc_url, page_idx)
            if text is None:
                continue
            out.append(text)

    def page_has_text_by_url(self, doc_url, page_idx):
        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )
        if self.core.call_success("fs_exists", page_url) is None:
            return None
        return True

    def page_get_text_by_url(self, doc_url, page_idx):
        task = "hocr_load_page_text({} p{})".format(doc_url, page_idx)
        self.core.call_all("on_perfcheck_start", task)

        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )

        file_desc = self.core.call_success("fs_open", page_url)
        if file_desc is None:
            self.core.call_all("on_perfcheck_stop", task)
            return None

        with file_desc:
            txt = file_desc.read().strip()

        try:
            tree = etree.XML(txt)
            txt = etree.tostring(tree, encoding='utf-8', method='text')
            if isinstance(txt, bytes):
                txt = txt.decode('utf-8')
            return txt
        except etree.ParseError as exc:
            LOGGER.warning(
                "%s contains invalid XML (%s). Will try with HTML parser",
                page_url, exc
            )

        def line_txt_generator(line):
            return " ".join(
                [word_box.content for word_box in line.word_boxes]
            )

        line_boxes = self.page_get_boxes_by_url(doc_url, page_idx)
        if line_boxes is None:
            return None
        return "\n".join(
            [line_txt_generator(line_box) for line_box in line_boxes]
        )

    def page_get_boxes_by_url(self, doc_url, page_idx):
        task = "hocr_load_page_boxes({} p{})".format(doc_url, page_idx)
        self.core.call_all("on_perfcheck_start", task)

        page_url = self.core.call_success(
            "fs_join", doc_url, PAGE_FILENAME_FMT.format(page_idx + 1)
        )

        file_desc = self.core.call_success("fs_open", page_url)
        if file_desc is None:
            self.core.call_all("on_perfcheck_stop", task)
            return None

        with file_desc:
            box_builder = pyocr.builders.LineBoxBuilder()
            boxes = box_builder.read_file(file_desc)
            if len(boxes) > 0:
                self.core.call_all("on_perfcheck_stop", task)
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
                self.core.call_all("on_perfcheck_stop", task)
                return boxes

        self.core.call_all("on_perfcheck_stop", task)

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
