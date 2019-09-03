import logging

import pyocr
import pyocr.builders

import openpaperwork_core


LOGGER = logging.getLogger(__name__)

PAGE_FILENAME_FMT = "paper.{}.words"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def get_interfaces(self):
        return [
            "doc_text",
            "page_boxes",
        ]

    def get_deps(self):
        return {
            'interfaces': [
                ('fs', ['paperwork_backend.fs.gio']),
            ]
        }

    def doc_get_mtime_by_url(self, out: list, doc_url):
        doc_nb_pages = self.core.call_success("doc_get_nb_pages", doc_url)

        page_idx = 0
        for page_idx in range(0, doc_nb_pages):
            page_url = doc_url + "/" + PAGE_FILENAME_FMT.format(page_idx + 1)
            if self.core.call_success("fs_exists", page_url) is None:
                continue
            out.append(self.core.call_success("fs_get_mtime", page_url))

    def doc_get_text_by_url(self, out: list, doc_url):
        doc_nb_pages = self.core.call_success("doc_get_nb_pages", doc_url)

        # The following is ugly to read, but generating the whole text from
        # word boxes is a CPU-expensive process that happens often when
        # Paperwork starts and therefore it deserves some optimizations.
        # The fact is that the fastest way to concatenate
        # strings together with Python is `str.join()`.
        line_txt_generator = lambda line: " ".join(
            [word_box.content for word_box in line.word_boxes]
        )
        page_txt_generator = lambda line_boxes: "\n".join(
            [line_txt_generator(line_box) for line_box in line_boxes]
        )
        for page_idx in range(0, doc_nb_pages):
            line_boxes = self.page_get_boxes_by_url(doc_url, page_idx)
            if line_boxes is None:
                continue
            out.append(page_txt_generator(line_boxes))

    def page_get_boxes_by_url(self, doc_url, page_idx):
        page_url = doc_url + "/" + PAGE_FILENAME_FMT.format(page_idx + 1)
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
                logger.warning(
                    "Doc %s (page %d) uses old box format",
                    doc_url, page_idx
                )
                return boxes
