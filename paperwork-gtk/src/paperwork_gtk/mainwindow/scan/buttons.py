import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'gtk_scan_buttons',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
            {
                'interface': 'gtk_docview',
                'defaults': ['paperwork_gtk.mainwindow.docview'],
            },
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.scan", "buttons.css"
        )

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.scan", "buttons.glade"
        )

        headerbar = self.core.call_success("docview_get_headerbar")
        headerbar.pack_start(self.widget_tree.get_object("scan_buttons"))
