import collections
import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.progressbar = None
        self.stack = collections.OrderedDict()

    def get_interfaces(self):
        return ['gtk_statusbar']

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
        ]

    def init(self, core):
        super().init(core)

        self.core.call_success(
            "gtk_load_css",
            "paperwork_gtk.mainwindow.statusbar", "statusbar.css"
        )

        widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow.statusbar", "statusbar.glade"
        )
        if widget_tree is None:
            # init must still work so 'chkdeps' is still available
            LOGGER.error("Failed to load widget tree")
            return
        self.progressbar = widget_tree.get_object("global_progressbar")

        mainwindow = self.core.call_success("mainwindow_get_main_container")
        mainwindow.pack_end(
            self.progressbar, expand=False, fill=True, padding=0
        )

    def on_progress(self, upd_type, progress, description=None):
        if description is None:
            description = ""

        if progress >= 1.0:
            if upd_type in self.stack:
                self.stack.pop(upd_type)
        else:
            self.stack[upd_type] = (progress, description)

        if len(self.stack) <= 0:
            self.progressbar.set_text("")
            self.progressbar.set_fraction(0.0)
            self.progressbar.set_tooltip_text("")
            return

        upd_type = next(reversed(self.stack))
        (progress, description) = self.stack[upd_type]

        self.progressbar.set_text(description)
        self.progressbar.set_tooltip_text(description)
        self.progressbar.set_fraction(progress)
