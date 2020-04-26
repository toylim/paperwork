import itertools
import logging
import math

import openpaperwork_core
import openpaperwork_core.deps


GI_AVAILABLE = False
GLIB_AVAILABLE = False
POPPLER_AVAILABLE = False

try:
    import gi
    GI_AVAILABLE = True
except (ImportError, ValueError):
    pass

if GI_AVAILABLE:
    try:
        from gi.repository import Gio
        GLIB_AVAILABLE = True
    except (ImportError, ValueError):
        pass

    try:
        gi.require_version('Poppler', '0.18')
        from gi.repository import Poppler
        POPPLER_AVAILABLE = True
    except (ImportError, ValueError):
        pass


LOGGER = logging.getLogger(__name__)

PDF_FILENAME = 'doc.pdf'

PDF_RENDER_FACTOR = 4


def minmax_rects(rects):
    (mx1, my1, mx2, my2) = (math.inf, math.inf, 0, 0)
    for rectangle in rects:
        ((x1, y1), (x2, y2)) = (
            (int(rectangle.x1 * PDF_RENDER_FACTOR),
             int(rectangle.y2 * PDF_RENDER_FACTOR)),
            (int(rectangle.x2 * PDF_RENDER_FACTOR),
             int(rectangle.y1 * PDF_RENDER_FACTOR))
        )
        (x1, x2) = (min(x1, x2), max(x1, x2))
        (y1, y2) = (min(y1, y2), max(y1, y2))
        mx1 = min(mx1, x1)
        my1 = min(my1, y1)
        mx2 = max(mx2, x2)
        my2 = max(my2, y2)
    rect = ((mx1, my1), (mx2, my2))
    return rect


class PdfWordBox(object):
    def __init__(self, content, position):
        self.content = content
        self.position = minmax_rects(position)

    def __str__(self):
        return "{{ .position={}, .content={} }}".format(
            self.position, str(self.content)
        )

    def __repr__(self):
        return str(self)


class PdfLineBox(object):
    def __init__(self, word_boxes, position):
        self.word_boxes = word_boxes
        self.position = minmax_rects(position)

    def __str__(self):
        return "{{ .position={}, .word_boxes={} }}".format(
            self.position, str(self.word_boxes)
        )

    def __repr__(self):
        return str(self)

    def _get_content(self):
        return " ".join([w.content for w in self.word_boxes])

    content = property(_get_content)


class PdfPageMapping(object):
    MAPPING_FILE = "pdf_map.csv"
    SEPARATOR = ","

    def __init__(self, plugin, doc_url):
        self.plugin = plugin
        self.core = plugin.core
        self.doc_url = doc_url
        self.mapping = {}
        self.reverse_mapping = {}
        self.map_url = self.core.call_success(
            "fs_join", self.doc_url, self.MAPPING_FILE
        )
        self.last_change = None
        self.nb_pages_offset = 0

    def load(self):
        self.mapping = {}
        self.reverse_mapping = {}

        if self.core.call_success("fs_exists", self.map_url) is None:
            return
        self.last_change = self.core.call_success("fs_getmtime", self.map_url)
        with self.core.call_success("fs_open", self.map_url, "r") as fd:
            # drop the first line
            lines = fd.readlines()[1:]
            for line in lines:
                (orig_page_idx, target_page_idx) = line.split(",", 1)
                orig_page_idx = int(orig_page_idx)
                target_page_idx = int(target_page_idx)
                self.mapping[orig_page_idx] = target_page_idx
                if target_page_idx > 0:
                    self.mapping[target_page_idx] = orig_page_idx
                else:
                    self.nb_pages_offset -= 1

    def save(self):
        if self.core.call_success("fs_isdir", self.doc_url) is None:
            return
        with self.core.call_success("fs_open", self.map_url, "w") as fd:
            fd.write("original_page_index,target_page_index\n")
            for (orig_page_idx, target_page_idx) in self.mapping.items():
                if orig_page_idx == target_page_idx:
                    continue
                fd.write("{},{}\n".format(orig_page_idx, target_page_idx))
        self.last_change = self.core.call_success("fs_getmtime", self.map_url)

    def has_original_page_idx(self, original_page_idx):
        if original_page_idx not in self.mapping:
            return True
        return self.mapping[original_page_idx] >= 0

    def get_original_page_idx(self, target_page_idx):
        if target_page_idx not in self.reverse_mapping:
            return target_page_idx
        original_page_idx = self.reverse_mapping[target_page_idx]
        LOGGER.info("Applying pdf pagw mapping: {} --> {}".format(
            original_page_idx, target_page_idx
        ))
        return original_page_idx

    def get_target_page_hash(self, target_page_idx):
        if target_page_idx not in self.reverse_mapping:
            return target_page_idx
        original_page_idx = self.reverse_mapping[target_page_idx]
        return hash(original_page_idx)

    def delete_target_page(self, target_page_idx):
        LOGGER.info(
            "Deleting page %d from PDF %s",
            target_page_idx, self.doc_url
        )

        original_page_idx = self.get_original_page_idx(target_page_idx)
        self.mapping[original_page_idx] = -1
        if target_page_idx in self.reverse_mapping:
            self.reverse_mapping.pop(target_page_idx)
        self.nb_pages_offset -= 1

        nb_pages = self.plugin.doc_get_nb_pages_by_url(
            self.doc_url, mapping=False
        )
        for page_idx in range(original_page_idx + 1, nb_pages):
            # anything beyong target_page_idx will move --> we create the
            # mapping if they don't already exist
            if page_idx in self.mapping:
                continue
            self.mapping[page_idx] = page_idx
            self.reverse_mapping[page_idx] = page_idx

        for (original, target) in list(self.mapping.items()):
            if target >= target_page_idx:
                LOGGER.info(
                    "Page %d (original) ; target: %d --> %d",
                    original, target, target - 1
                )
                self.reverse_mapping.pop(target)
                self.mapping[original] = target - 1
                self.reverse_mapping[target - 1] = original

    def __hash__(self):
        h = 0
        for (k, v) in self.mapping.items():
            if k == v:
                continue
            h ^= (k << 10) ^ v
        return h


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.cache_hash = {}
        self.cache_nb_pages = {}
        self.cache_mappings = {}

    def get_interfaces(self):
        return [
            "chkdeps",
            "doc_hash",
            "doc_pdf_import",
            "doc_pdf_url",
            "doc_text",
            "doc_type",
            "page_boxes",
            "page_img",
            "page_paper",
            'pages',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'fs',
                'defaults': ['openpaperwork_gtk.fs.gio'],
            },
            {
                'interface': 'mainloop',
                'defaults': ['openpaperwork_gtk.mainloop.glib'],
            },
        ]

    def chkdeps(self, out: dict):
        if not GI_AVAILABLE:
            out['gi'].update(openpaperwork_core.deps.GI)
        if not GLIB_AVAILABLE:
            out['glib'].update(openpaperwork_core.deps.GLIB)
        if not POPPLER_AVAILABLE:
            out['poppler'].update(openpaperwork_core.deps.POPPLER)

    def _get_pdf_url(self, doc_url):
        if doc_url.endswith(".pdf"):
            return doc_url
        pdf_url = doc_url + "/" + PDF_FILENAME
        if self.core.call_success("fs_exists", pdf_url) is None:
            return None
        return pdf_url

    def _get_page_mapping(self, doc_url):
        if doc_url in self.cache_mappings:
            return self.cache_mappings[doc_url]
        mapping = PdfPageMapping(self, doc_url)
        mapping.load()
        self.cache_mappings[doc_url] = mapping
        return mapping

    def _open_pdf(self, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return (None, None)
        gio_file = Gio.File.new_for_uri(pdf_url)
        doc = Poppler.Document.new_from_gfile(gio_file, password=None)
        self.core.call_all("on_objref_track", doc)
        return (pdf_url, doc)

    def is_doc(self, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        return True

    def doc_get_pdf_url_by_url(self, doc_url):
        return self._get_pdf_url(doc_url)

    def doc_get_hash_by_url(self, out: list, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return
        mapping = self._get_page_mapping(doc_url)
        out.append(hash(mapping))

        # cache the hash of doc.pdf to speed up imports
        cache_key = "hash_{}".format(doc_url)
        if cache_key not in self.cache_hash:
            h = self.core.call_success("fs_hash", pdf_url)
            self.cache_hash[cache_key] = h
        out.append(self.cache_hash[cache_key])

    def page_get_hash_by_url(self, out: list, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return
        mapping = self._get_page_mapping(doc_url)
        out.append(mapping.get_target_page_hash(page_idx))

        # cache the hash of doc.pdf to speed up imports
        cache_key = "hash_{}".format(doc_url)
        if cache_key not in self.cache_hash:
            h = self.core.call_success("fs_hash", pdf_url)
            self.cache_hash[cache_key] = h
        out.append(self.cache_hash[cache_key])

    def doc_get_mtime_by_url(self, out: list, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mapping = self._get_page_mapping(doc_url)
        if mapping.last_change is not None:
            out.append(mapping.last_change)

        mtime = self.core.call_success("fs_get_mtime", pdf_url)
        if mtime is None:
            return None
        out.append(mtime)

    def _doc_get_nb_pages_by_url(self, doc_url):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None
        nb_pages = pdf.get_n_pages()
        return nb_pages

    def doc_get_nb_pages_by_url(self, doc_url, mapping=True):
        if doc_url in self.cache_nb_pages:
            r = self.cache_nb_pages[doc_url]
        else:
            # Poppler is not thread-safe
            r = self.core.call_success(
                "mainloop_execute", self._doc_get_nb_pages_by_url, doc_url
            )
            if r is not None:
                self.cache_nb_pages[doc_url] = r
        if r is not None and mapping:
            mapping = self._get_page_mapping(doc_url)
            r += mapping.nb_pages_offset
        return r

    def page_get_img_url(self, doc_url, page_idx, write=False):
        if write:
            return None
        nb_pages = self.doc_get_nb_pages_by_url(doc_url)
        if nb_pages is None or page_idx >= nb_pages:
            return None
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        # same URL used in browsers
        pdf_url = self._get_pdf_url(doc_url)
        return "{}#page={}".format(pdf_url, str(page_idx + 1))

    @staticmethod
    def _custom_split(input_str, input_rects, splitter):
        # turn text and layout from Poppler into boxes
        assert(len(input_str) == len(input_rects))
        input_el = zip(input_str, input_rects)
        for (is_split, group) in itertools.groupby(
                    input_el,
                    lambda x: splitter(x[0])
                ):
            if is_split:
                continue
            letters = ""
            rects = []
            for (letter, rect) in group:
                letters += letter
                rects.append(rect)
            yield(letters, rects)

    def _doc_get_text_by_url(self, out: list, doc_url, mapping):
        task = "pdf_get_text_by_url({})".format(doc_url)
        self.core.call_all("on_perfcheck_start", task)

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            self.core.call_all("on_perfcheck_stop", task)
            return

        for page_idx in range(0, pdf.get_n_pages()):
            if not mapping.has_original_page_idx(page_idx):
                continue
            page = pdf.get_page(page_idx)
            txt = page.get_text()
            txt = txt.strip()
            if txt == "":
                continue
            out.append(txt)
        self.core.call_all(
            "on_perfcheck_stop", task, nb_pages=pdf.get_n_pages()
        )
        return True

    def doc_get_text_by_url(self, out: list, doc_url):
        mapping = self._get_page_mapping(doc_url)
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute",
            self._doc_get_text_by_url, out, doc_url, mapping
        )

    def _page_has_text_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return

        page = pdf.get_page(page_idx)
        if page is None:
            return

        return len(page.get_text().strip()) > 0

    def page_has_text_by_url(self, doc_url, page_idx):
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute", self._page_has_text_by_url, doc_url, page_idx
        )

    def _page_get_boxes_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return

        pdf_page = pdf.get_page(page_idx)
        if pdf_page is None:
            return

        txt = pdf_page.get_text()
        if txt.strip() == "":
            return None

        layout = pdf_page.get_text_layout()
        if not layout[0]:
            return None
        layout = layout[1]

        line_boxes = []
        for (line, line_rects) in self._custom_split(
                    txt, layout, lambda x: x == "\n"
                ):
            words = []
            for (word, word_rects) in self._custom_split(
                        line, line_rects, lambda x: x.isspace()
                    ):
                word_box = PdfWordBox(word, word_rects)
                words.append(word_box)
            line_boxes.append(PdfLineBox(words, line_rects))
        return line_boxes

    def page_get_boxes_by_url(self, doc_url, page_idx):
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute", self._page_get_boxes_by_url, doc_url, page_idx
        )

    def doc_pdf_import(self, src_file_uri):
        # check the PDF is readable before messing the content of the
        # work directory
        gio_file = Gio.File.new_for_uri(src_file_uri)
        Poppler.Document.new_from_gfile(gio_file, password=None)

        (doc_id, doc_url) = self.core.call_success("storage_get_new_doc")
        pdf_url = self.core.call_success("fs_join", doc_url, PDF_FILENAME)

        self.core.call_success("fs_mkdir_p", doc_url)
        self.core.call_success("fs_copy", src_file_uri, pdf_url)
        return (doc_id, doc_url)

    def page_delete_by_url(self, doc_url, page_idx):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return (None, None)
        mapping = self._get_page_mapping(doc_url)
        mapping.delete_target_page(page_idx)
        mapping.save()

    def _page_get_paper_size_by_url(self, doc_url, page_idx):
        if doc_url in self.cache_nb_pages:
            if page_idx >= self.cache_nb_pages[doc_url]:
                return None

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None

        page = pdf.get_page(page_idx)
        if page is None:
            return

        size = page.get_size()

        # points --> inches: / 72
        # inches --> millimeters (i18n unit): * 25.4
        return (
            size[0] / 72.0 * 25.4,
            size[0] / 72.0 * 25.4,
        )

    def page_get_paper_size_by_url(self, doc_url, page_idx):
        mapping = self._get_page_mapping(doc_url)
        page_idx = mapping.get_original_page_idx(page_idx)
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute",
            self._page_get_paper_size_by_url, doc_url, page_idx
        )

    def page_move_by_url(
                self,
                source_doc_url, source_page_idx,
                dest_doc_url, dest_page_idx
            ):
        if self.is_doc(source_doc_url):
            LOGGER.warning(
                "Cannot move page from PDF file (doc=%s)", source_doc_url
            )
