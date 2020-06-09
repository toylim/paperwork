import logging

import openpaperwork_core


LOGGER = logging.getLogger(__name__)


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.windows = []
        self.widget_tree = None

    def get_interfaces(self):
        return [
            'gtk_shortcuts',
            'gtk_window_listener',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def on_gtk_window_opened(self, window):
        self.windows.append(window)

    def on_gtk_window_closed(self, window):
        self.windows.remove(window)

    def gtk_show_shortcuts(self):
        LOGGER.info("Showing shortcuts")
        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.shortcutswin", "shortcutswin.glade"
        )
        window = self.widget_tree.get_object("shortcuts")
        window.set_transient_for(self.windows[-1])
        window.show_all()
