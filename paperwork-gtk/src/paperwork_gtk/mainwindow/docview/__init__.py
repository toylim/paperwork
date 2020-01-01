import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None
        self.page_container = None

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

        scroll = self.widget_tree.get_object("docview_scroll")

        self.page_container = self.core.call_success(
            "gtk_widget_flowlayout_new", spacing=(20, 20)
        )
        self.page_container.set_visible(True)

        scroll.add(self.page_container)

        self.core.call_all(
            "mainwindow_add", side="right", name="docview", prio=10000,
            header=self.widget_tree.get_object("docview_header"),
            body=self.widget_tree.get_object("docview_body"),
        )

    def docview_get_headerbar(self):
        return self.widget_tree.get_object("docview_header")

    def docview_get_body(self):
        return self.widget_tree.get_object("docview_body")
