import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.page_info = None
        self.nb_pages = None
        self.current_page = None
        self.nb_pages = None

    def get_interfaces(self):
        return ['gtk_docview_pageinfo']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.docview.pageinfo", "pageinfo.glade"
        )
        if self.widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return

        self.page_info = self.widget_tree.get_object("page_info")
        self.current_page = self.widget_tree.get_object(
            "page_current_nb"
        )
        self.current_page.connect("activate", self._change_page)
        self.nb_pages = self.widget_tree.get_object("page_total")

        button = self.widget_tree.get_object("page_prev")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all(
                "doc_goto_previous_page"
            )
        )
        button = self.widget_tree.get_object("page_next")
        button.connect(
            "clicked",
            lambda *args, **kwargs: self.core.call_all("doc_goto_next_page")
        )

        self.core.call_success("docview_get_body").add_overlay(self.page_info)

    def _change_page(self, *args, **kwargs):
        txt = self.current_page.get_text()
        if txt == "":
            return
        self.core.call_all("doc_goto_page", int(txt) - 1)

    def doc_open(self, doc_id, doc_url):
        nb_pages = self.core.call_success("doc_get_nb_pages_by_url", doc_url)
        if nb_pages is None:
            LOGGER.warning("Failed to get the number of pages in %s", doc_id)
            nb_pages = 0

        self.nb_pages.set_text(f"/ {nb_pages}")
        self.page_info.set_visible(True)

    def on_page_shown(self, page_idx):
        txt = str(page_idx + 1)
        if txt != self.current_page.get_text():
            self.current_page.set_text(txt)

    def page_info_add_left(self, widget):
        self.widget_tree.get_object("page_prevnext").pack_end(
            widget, expand=False, fill=True, padding=0
        )
        return True
