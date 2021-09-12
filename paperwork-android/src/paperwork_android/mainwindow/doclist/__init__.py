import kivy.lang.builder

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    PRIORITY = 100

    def __init__(self):
        super().__init__()
        self.root = None

    def get_interfaces(self):
        return [
            'doclist',
            'kivy_mainwindow_component',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'kivy',
                'defaults': ['paperwork_android.kivy'],
            },
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
            {
                'interface': 'mainwindow',
                'defaults': ['paperwork_android.mainwindow.window'],
            },
        ]

    def kivy_load_mainwindow(self, mainwindow):
        self.root = kivy.lang.builder.Builder.load_file(
            self.core.call_success(
                "fs_unsafe",
                self.core.call_success(
                    "resources_get_file",
                    "paperwork_android.mainwindow.doclist", "doclist.kv"
                )
            )
        )

        mainwindow.add_widget('doclist', self.root)
