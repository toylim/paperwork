import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.scroll = None
        self.page_container = None
        self.pages = []
        self.page_widgets = {}
        self.active_page_idx = 0
        self._last_scroll = 0  # to avoid multiple calls

    def get_interfaces(self):
        return [
            'gtk_docview',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_mainwindow',
                'defaults': ['paperwork_gtk.mainwindow.window'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_widget_flowlayout',
                'defaults': ['paprwork_gtk.widget.flowlayout'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview", "docview.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.scroll = self.widget_tree.get_object("docview_scroll")

        self.page_container = self.core.call_success(
            "gtk_widget_flowlayout_new", spacing=(20, 20),
            scrollbars=self.scroll
        )
        self.page_container.connect(
            "widget_visible", self._upd_current_page_idx
        )
        self.page_container.connect(
            "widget_hidden", self._upd_current_page_idx
        )
        self.page_container.set_visible(True)

        self.scroll.add(self.page_container)

        self.core.call_all(
            "mainwindow_add", side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_body")

    def doc_open(self, doc_id, doc_url):
        self._last_scroll = -1
        self.page_widgets = {}
        self.pages = []

        for child in self.page_container.get_children():
            self.page_container.remove(child)

        self.core.call_all(
            "doc_open_components",
            self.pages, doc_id, doc_url, self.page_container
        )
        for page in self.pages:
            page.connect("size_obtained", self._on_page_size_obtained)

        self.doc_goto_page(0)

    def _on_page_size_obtained(self, page):
        self.page_widgets[page.widget] = page
        self.page_container.add(page.widget)
        if page.page_idx == self.active_page_idx:
            self.doc_goto_page(self.active_page_idx)

    def on_page_shown(self, page_idx):
        LOGGER.info("Active page %d", page_idx)
        self.active_page_idx = page_idx

    def _upd_current_page_idx(self, *args, **kwargs):
        # figure out the current page: the current page is one the in the
        # middle of the window
        p_scroll = (0, self.scroll.get_vadjustment().get_value())

        if p_scroll[1] == self._last_scroll:
            return
        self._last_scroll = p_scroll[1]

        p_size = self.scroll.get_allocation()

        p = (
            (p_size.width / 2) + p_scroll[0],
            (p_size.height / 2) + p_scroll[1]
        )
        widget = self.page_container.get_widget_at(p[0], p[1])

        if widget is None:
            # fall back on the top of the screen (there may not be enough pages
            # to fill the window)
            p = ((p_size.width / 2) + p_scroll[0], p_scroll[1])
            widget = self.page_container.get_widget_at(p[0], p[1])

        if widget is None:
            # really no pages
            return

        page_idx = self.page_widgets[widget].page_idx
        if self.active_page_idx != page_idx:
            self.core.call_all("on_page_shown", page_idx)

    def doc_goto_previous_page(self):
        self.doc_goto_page(self.active_page_idx - 1)

    def doc_goto_next_page(self):
        self.doc_goto_page(self.active_page_idx + 1)

    def doc_goto_page(self, page_idx):
        if len(self.pages) <= 0:
            self.scroll.get_vadjustment().set_value(0)
            self.core.call_all("on_page_shown", 0)
            return

        if page_idx < 0:
            page_idx = 0
        if page_idx >= len(self.pages):
            page_idx = len(self.pages) - 1

        LOGGER.info("Going to page %d", page_idx)

        self.core.call_all("on_page_shown", page_idx)

        widget = self.pages[page_idx].widget
        if widget is None:
            return

        w_height = self.page_container.get_widget_position(widget)[1]
        if self.scroll.get_vadjustment().get_value() != w_height:
            self.scroll.get_vadjustment().set_value(w_height)
            self._last_scroll = w_height
