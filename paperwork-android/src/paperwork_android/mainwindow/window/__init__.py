import kivy
import kivy.lang.builder

import openpaperwork_core


class Plugin(openpaperwork_core.PluginBase):
    def __init__(self):
        super().__init__()
        self.root = None

    def get_interfaces(self):
        return [
            'mainwindow',
            'kivy_build',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
        ]

    def kivy_load(self):
        self.root = kivy.lang.builder.Builder.load_file(
            self.core.call_success(
                "fs_unsafe",
                self.core.call_success(
                    "resources_get_file",
                    "paperwork_android.mainwindow.window", "window.kv"
                )
            )
        )
        self.core.call_all("kivy_add_root_screen", self.root)
