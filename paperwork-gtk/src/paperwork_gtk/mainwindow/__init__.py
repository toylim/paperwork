import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        self.core = None
        self.widget_tree = None

    def get_interfaces(self):
        return ['gtk_main_window']

    def get_deps(self):
        return [
            {
                'interface': 'gtk_resources',
                'defaults': ['openpaperwork_gtk.resources'],
            },
        ]

    def init(self, core):
        self.core = core

        self.widget_tree = self.core.call_success(
            "gtk_load_widget_tree",
            "paperwork_gtk.mainwindow", "mainwindow.glade"
        )

    def on_initialized(self):
        self.widget_tree.get_object("mainWindow").set_visible(True)
