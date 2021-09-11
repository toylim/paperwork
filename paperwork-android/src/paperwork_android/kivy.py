import kivy
import kivy.lang.builder

import kivymd
import kivymd.app

from openpaperwork_core import PluginBase

import paperwork_android.util


class PaperworkApp(kivymd.app.MDApp):
    def __init__(self, plugin, **kwargs):
        super().__init__(**kwargs)
        self._root = None
        self.plugin = plugin

    def build(self):
        self.root = kivy.lang.builder.Builder.load_file(
            self.plugin.core.call_success(
                "fs_unsafe",
                self.plugin.core.call_success(
                    "resources_get_file",
                    "paperwork_android", "kivy.kv"
                )
            )
        )
        assert(self.root is not None)

        self.plugin.core.call_all("kivy_load")

        return self.root

    @paperwork_android.util.async_cb
    async def run(self):
        await self.async_run()


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.app = None

    def get_interfaces(self):
        return [
            'kivy',
        ]

    def get_deps(self):
        return [
            {
                'interface': 'resources',
                'defaults': ['paperwork_android.resources'],
            },
        ]

    def init(self, core):
        super().init(core)
        kivy.require("2.0.0")
        self.app = PaperworkApp(self)

    def on_initialized(self):
        self.app.run()

    def kivy_get_app(self):
        return self.app

    def kivy_get_root(self):
        return self.app.root

    def kivy_add_root_screen(self, screen):
        self.app.root.add_widget(screen)
