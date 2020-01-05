import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.page_info = None

    def get_interfaces(self):
        return [
            'gtk_docview_pageinfo',
        ]

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
        self.core.call_success("docview_get_body").add_overlay(self.page_info)

    def doc_open(self, doc_id, doc_url):
        self.page_info.set_visible(True)
