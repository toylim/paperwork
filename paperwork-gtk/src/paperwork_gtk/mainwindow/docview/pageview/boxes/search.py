import logging
import re

import openpaperwork_core
import paperwork_backend.util


LOGGER = logging.getLogger(__name__)

MIN_WORD_LENGTH = 3
SPLIT = r"\W+"


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.re_split = re.compile(SPLIT)
        self.keywords = set()

    def get_interfaces(self):
        return ['search_listener']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_pageview',
                'defaults': ['paperwork_gtk.mainwindow.docview.pageview'],
            },
            {
                'interface': 'gtk_pageview_boxes',
                'defaults': [
                    'paperwork_gtk.mainwindow.docview.pageview.boxes'
                ],
            },
        ]

    def on_search_start(self, query):
        query = self.re_split.split(
            paperwork_backend.util.strip_accents(query)
        )
        self.keywords = {
            keyword.lower() for keyword in query
            if len(keyword) >= MIN_WORD_LENGTH
        }
        self.core.call_all("pageview_refresh_all")

    def on_search_results(self, docs):
        pass

    def on_page_draw(self, cairo_ctx, page):
        if len(self.keywords) <= 0:
            return

        boxes = self.core.call_success(
            "pageview_get_boxes_by_id", page.doc_id, page.page_idx
        )
        if boxes is None:
            return

        for line_box in boxes:
            for word_box in line_box.word_boxes:
                word = paperwork_backend.util.strip_accents(word_box.content)
                for w in self.re_split.split(word):
                    w = w.lower()
                    if w not in self.keywords:
                        continue
                    self.core.call_all(
                        "page_draw_box",
                        cairo_ctx, page, word_box.position,
                        (0.0, 1.0, 0.0), border_width=2
                    )
