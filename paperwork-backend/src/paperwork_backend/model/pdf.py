import itertools
import logging

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
    (mx1, my1, mx2, my2) = (6553600000, 6553600000, 0, 0)
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


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.cache = {}

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
        pdf_url = doc_url + "/" + PDF_FILENAME
        if self.core.call_success("fs_exists", pdf_url) is None:
            return None
        return pdf_url

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

        # cache the hash to speed up imports
        cache_key = "hash_{}".format(doc_url)
        if cache_key not in self.cache:
            h = self.core.call_success("fs_hash", pdf_url)
            self.cache[cache_key] = h
        out.append(self.cache[cache_key])

    def page_get_hash_by_url(self, out: list, doc_url, page_idx):
        return self.doc_get_hash_by_url(out, doc_url)

    def doc_get_mtime_by_url(self, out: list, doc_url):
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        mtime = self.core.call_success("fs_get_mtime", pdf_url)
        if mtime is None:
            return None
        out.append(mtime)

    def page_get_mtime_by_url(self, out: list, doc_url, page_idx):
        return self.doc_get_mtime_by_url(out, doc_url)

    def _doc_get_nb_pages_by_url(self, doc_url):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None
        return pdf.get_n_pages()

    def doc_get_nb_pages_by_url(self, doc_url):
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute", self._doc_get_nb_pages_by_url, doc_url
        )

    def page_get_img_url(self, doc_url, page_idx, write=False):
        if write:
            return None
        pdf_url = self._get_pdf_url(doc_url)
        if pdf_url is None:
            return None
        # same URL used in browsers
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

    def _doc_get_text_by_url(self, out: list, doc_url):
        task = "pdf_get_text_by_url({})".format(doc_url)
        self.core.call_all("on_perfcheck_start", task)

        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            self.core.call_all("on_perfcheck_stop", task)
            return

        for page_idx in range(0, pdf.get_n_pages()):
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
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute", self._doc_get_text_by_url, out, doc_url
        )

    def _page_has_text_by_url(self, doc_url, page_idx):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return
        return len(pdf.get_page(page_idx).get_text().strip()) > 0

    def page_has_text_by_url(self, doc_url, page_idx):
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute", self._page_has_text_by_url, doc_url, page_idx
        )

    def _page_get_boxes_by_url(self, doc_url, page_idx):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return

        pdf_page = pdf.get_page(page_idx)

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
        if self.is_doc(doc_url):
            LOGGER.warning(
                "Cannot delete page from PDF file (doc=%s)", doc_url
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

    def _page_get_paper_size_by_url(self, doc_url, page_idx):
        (pdf_url, pdf) = self._open_pdf(doc_url)
        if pdf is None:
            return None

        page = pdf.get_page(page_idx)
        size = page.get_size()

        # points --> inches: / 72
        # inches --> millimeters (i18n unit): * 25.4
        return (
            size[0] / 72.0 * 25.4,
            size[0] / 72.0 * 25.4,
        )

    def page_get_paper_size_by_url(self, doc_url, page_idx):
        # Poppler is not thread-safe
        return self.core.call_success(
            "mainloop_execute",
            self._page_get_paper_size_by_url, doc_url, page_idx
        )
